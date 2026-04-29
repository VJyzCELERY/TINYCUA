# SDK Stateless Refactor — Design Document

## Architecture

### Package Layout (Target)

```
tinycua_sdk/
  __init__.py
  agent/
    __init__.py
    agent.py              # Agent class (runnable, stateless)
    config.py             # AgentConfig, AgentPolicy
    definition.py         # AgentDefinition (base properties)
    executor.py           # AgentExecutor (run/stream logic)
    loop.py               # Agent loop implementation
    llm_model.py          # LLMModel value object
    backend_kind.py       # BackendConfig, BackendKind
    templates.py          # Pre-built templates
    hooks.py              # Execution hooks (ephemeral callbacks)
  tools/
    __init__.py
    decorators.py         # @tool decorator, Tool dataclass
    schema.py             # JSON-schema generation
    parser.py             # Source parsing
    resolver.py           # Dependency resolution (pure functions)
    mcp.py                # MCP integration
    cua/                  # CUA sub-package
    native/               # Built-in generic tools
      __init__.py
      context_tools.py    # Context utilities (stateless)
  skills/
    __init__.py
    models.py             # Skill dataclass
    registry.py           # SkillRegistry (explicit instance)
    loader.py             # Skill loader from filesystem/config
    improver.py           # Skill improvement logic
    cache.py              # Ephemeral skill cache (not persistent)
  core/
    __init__.py
    config.py             # SDKConfig (framework config only)
```

### Deleted Packages

- `session/` — consumer concern
- `memory/` — consumer concern
- `modeling/` — consumer concern
- `storage/` — consumer concern
- `clients/` — consumer concern
- `cli/` — separate consumer package
- `utils/session.py` — deleted
- `core/registry.py` — deleted (ToolRegistry singleton)
- `tools/memory.py` — deleted (MemoryBackend)
- `tools/memory_tools.py` — deleted (memory-dependent tools)
- `skills/backend.py` — deleted (SkillBackend)

## Component Design

### Agent

The `Agent` class is the primary SDK interface. It is:
- **Runnable**: `agent.run(query)` works immediately.
- **Stateless**: No internal message history, no session, no memory.
- **Composable**: Tools and skills can be added after construction.
- **Serializable**: `to_config()` / `from_config()` round-trip.

```python
class Agent(AgentExecutor):
    def __init__(self, ...):
        # Fully hydrate from parameters. No database lookups.
        self.config = AgentConfig(...)
        self._tools = list(tools or [])
        self._skills = list(skills or [])
        # ...

    def add_tools(self, tools: Tool | list[Tool]) -> None:
        if isinstance(tools, Tool):
            tools = [tools]
        self._tools.extend(tools)

    def add_skills(self, skills: Skill | list[Skill]) -> None:
        if isinstance(skills, Skill):
            skills = [skills]
        self._skills.extend(skills)

    def to_config(self) -> dict[str, Any]:
        return {
            "name": self.config.name,
            "instructions": self.config.instructions,
            "llm_model": self.config.llm_model.to_dict(),
            "tools": [t.to_config() for t in self._tools],
            "skills": [s.to_dict() for s in self._skills],
            # ...
        }

    @classmethod
    def from_config(cls, config: str | Path | dict[str, Any]) -> Agent:
        if isinstance(config, (str, Path)):
            config = _load_yaml_or_json(config)
        agent_config = AgentConfig.from_dict(config)
        tools = [_resolve_tool(t) for t in config.get("tools", [])]
        skills = [_resolve_skill(s) for s in config.get("skills", [])]
        return cls(
            name=agent_config.name,
            instructions=agent_config.instructions,
            llm_model=agent_config.llm_model,
            tools=tools,
            skills=skills,
            # ...
        )

    async def run(self, query, messages=None, instructions=None,
                  stream=False, trace=False, verbose=False):
        # Build prompt: LLMModel.system_prompt + Agent.instructions + query
        # Execute loop with tools
        # Return str or AsyncIterator[str]
```

### LLMModel

Pure Pydantic model. No I/O, no persistence methods.

```python
class LLMModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = "openai-compatible"
    model_name: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: SecretStr = SecretStr("")
    max_context: int = 128_000
    temperature: float = 1.0
    system_prompt: str = "You are a helpful assistant."

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMModel:
        return cls(**data)
```

**Why `system_prompt` is here:** Different models (GPT-4, Claude, Qwen, Llama) interpret behavioral instructions differently. Keeping `system_prompt` on `LLMModel` allows consumers to tune behavior per model without changing agent logic.

### Tool

The `@tool` decorator returns a `Tool` instance directly. No global registry.

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    _fn: Callable | None = field(default=None, repr=False)
    _source: str | None = field(default=None, repr=False)
    _external_dependencies: list[str] = field(default_factory=list)
    _tool_dependencies: list[dict] = field(default_factory=list)
    _version: str | None = field(default=None, repr=False)

    def to_config(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def to_bundle(self) -> dict[str, Any]:
        return {
            **self.to_config(),
            "source": self._source,
            "external_dependencies": self._external_dependencies,
            "tool_dependencies": self._tool_dependencies,
            "version": self._version,
        }

    def invoke(self, **kwargs: Any) -> Any:
        if self._fn is None:
            raise RuntimeError(f"Tool {self.name} has no function")
        return self._fn(**kwargs)
```

### SkillRegistry

Non-singleton, explicit instantiation. No filesystem I/O.

```python
class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self, category: str | None = None) -> list[Skill]:
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return skills
```

### Skill Markdown Parser

Skills are defined as Markdown text. The SDK provides a parser; the consumer decides how to obtain the text (file, DB, inline string, etc.).

```python
class Skill:
    # ... existing fields ...

    @classmethod
    def load(cls, text: str) -> Skill:
        """Parse a skill definition from Markdown text.

        Args:
            text: Markdown content following the SKILL.md format.

        Returns:
            Skill instance.
        """
        # Parse frontmatter (YAML between --- markers)
        # Parse sections: # Name, ## Description, ## Instructions, ## Tools, etc.
        ...
```

**Example SKILL.md format:**
```markdown
---
name: coder
category: development
tools:
  - read_file
  - write_file
  - bash
---

# Coder

## Description
Write clean, efficient code.

## Instructions
When asked to write code:
1. Plan the solution first
2. Write clean, documented code
3. Include error handling
```

**Consumer-side loading:**
```python
# From file (consumer decides)
with open("./skills/coder.md") as f:
    skill = Skill.load(f.read())

# From database (consumer decides)
row = db.query("SELECT markdown FROM skills WHERE name = 'coder'")
skill = Skill.load(row.markdown)

# Inline (no file needed)
skill = Skill.load("""
---
name: helper
---
# Helper
## Description
A simple helper skill.
""")
```

### BackendConfig

Describes where the agent should run. Pure value object.

```python
class BackendKind(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"

class BackendConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: BackendKind = BackendKind.LOCAL
    url: str | None = None
    api_key: SecretStr = SecretStr("")
    headers: dict[str, str] = Field(default_factory=dict)
```

## Prompt Construction

At runtime, the agent constructs the final prompt from:

1. `LLMModel.system_prompt` — model-specific behavior tuning
2. `Agent.instructions` — task-specific directive
3. `user_input` — runtime query

Example:
```python
system = agent.llm_model.system_prompt
if agent.instructions:
    system += f"\n\nTask instructions: {agent.instructions}"

messages = [
    {"role": "system", "content": system},
    # ... consumer-provided message history ...
    {"role": "user", "content": query},
]
```

## Configuration Serialization

All SDK objects support round-trip serialization via plain dicts.

### AgentConfig
```python
class AgentConfig(BaseModel):
    name: str = "assistant"
    instructions: str = ""
    llm_model: LLMModel = Field(default_factory=LLMModel)
    tools: list[Tool] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    policy: AgentPolicy = Field(default_factory=AgentPolicy)
    backend: BackendConfig = Field(default_factory=BackendConfig)
    sub_agents: list[Agent] = Field(default_factory=list)
    max_depth: int = 3
    loop: Any = None
    strip_thinking: bool | list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentConfig:
        return cls(**data)
```

### SDKConfig
```python
class SDKConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    loop: LoopConfig = Field(default_factory=LoopConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    backend_url: str = "http://localhost:8000"
```

## Migration Strategy

See `ROADMAP.md` for the complete staged implementation plan. Each stage has its own folder under `specs/refactor-tinycua-sdk/{code}-{title}/` with detailed specifications.

**High-level flow:**
1. **Stage 01** — Remove legacy tests & examples
2. **Stage 02** — Write new unit tests (success criteria)
3. **Stages 03-12** — Incremental implementation (delete modules, refactor frameworks, refactor agent/config)
4. **Stage 13** — Create new examples
5. **Stage 14** — Create integration tests

All stages are designed to be testable independently where possible.

## Risks

| Risk | Mitigation |
|------|-----------|
| Breaking changes for existing consumers | Clear migration guide, version bump (major release) |
| Consumers lose built-in session/memory | Document that consumers must implement their own; provide examples |
| Tests deleted without replacement | Ensure core framework tests remain and pass |
| Config files in old format break | `from_config()` should raise clear errors for obsolete fields |

## Appendix: Consumer Implementation Example

```python
# host_app/main.py
from tinycua_sdk import Agent, LLMModel, tool, Skill

# Define tools
@tool
def search(query: str) -> str:
    return f"Results for {query}"

# Load skill from Markdown file (consumer handles filesystem)
with open("./skills/coder.md") as f:
    coder = Skill.load(f.read())

# Or inline
researcher = Skill.load("""
---
name: researcher
category: research
tools:
  - search
---
# Researcher
## Description
Research topics thoroughly.
## Instructions
Find accurate information from reliable sources.
""")

# Create agent
agent = Agent(
    llm_model=LLMModel(
        base_url="http://localhost:1234/v1",
        model_name="qwen3.5-9b",
        system_prompt="You are a helpful research assistant.",
    ),
    instructions="Answer questions concisely.",
    tools=[search],
    skills=[coder, researcher],
)

# Run
import asyncio
response = asyncio.run(agent.run("What is quantum computing?"))
print(response)
```
