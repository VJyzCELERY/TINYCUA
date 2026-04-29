# Stage 11 — Refactor Agent

## Objective

Refactor the `Agent` class to be stateless and fully runnable. Introduce `LLMModel` and `BackendConfig`, remove obsolete parameters.

## Files to Modify

| File | Changes |
|------|---------|
| `agent/agent.py` | Update constructor, add `add_tools()`, `add_skills()`, `from_config()`, `run()` |
| `agent/executor.py` | Remove remote execution, session/memory references |
| `agent/definition.py` | Remove obsolete fields |
| `agent/config.py` | Update `AgentConfig` |
| `agent/llm_model.py` | **New file** — `LLMModel` value object |
| `agent/backend_kind.py` | **New file** — `BackendConfig`, `BackendKind` |
| `agent/templates.py` | Update templates to use new config structure |
| `agent/loop.py` | **Remove `ReactLoop`** — keep only `BaseLoop` |
| `agent/loop_resolver.py` | Simplify to only resolve `BaseLoop` instances |
| `agent/validator.py` | Remove `"react"` from valid loop types |

## Constructor Changes

### BEFORE
```python
Agent(
    name="assistant",
    instructions="",
    system_prompt="You are a helpful assistant.",
    model="gpt-4o-mini",
    provider="openai",
    base_url=None,
    api_key=None,
    tools=None,
    skills=None,
    policy=None,
    mode="local",
    backend_url=None,
    backend_api_key=None,
    backend_headers=None,
    agent_id=None,
    sub_agents=None,
    max_depth=3,
    loop=None,
    planning_prompt=None,
    short_term_memory=None,
    long_term_memory=None,
)
```

### AFTER
```python
Agent(
    name="assistant",
    instructions="",
    llm_model=LLMModel(),
    tools=None,
    skills=None,
    policy=None,
    backend=BackendConfig(),
    sub_agents=None,
    max_depth=3,
    loop=None,  # BaseLoop instance or None (defaults to BaseLoop())
    strip_thinking=None,
)
```

## Loop Refactor

The built-in `ReactLoop` is **removed** from the framework. The SDK provides only `BaseLoop` — a minimal, extensible base class.

### `agent/loop.py` (Target)
```python
class BaseLoop:
    """Minimal base class for agent execution loops."""
    
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
    
    async def run(self, agent, messages, tools):
        """Execute the loop. To be overridden by subclasses."""
        ...

def resolve_loop(loop_config: Any) -> BaseLoop:
    """Resolve loop config to a BaseLoop instance.
    
    Only accepts:
    - None → returns BaseLoop()
    - BaseLoop instance → returns as-is
    - dict with {"max_iterations": int} → returns BaseLoop(**kwargs)
    
    Raises ValueError for string types ("react", etc.) or unknown configs.
    """
    ...
```

### Removed
- `ReactLoop` class
- `VALID_LOOP_TYPES` set (or reduced to only `"default"`)
- String-based loop resolution (`"react"`)

## New Classes

### LLMModel
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
```

### BackendConfig
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

## Method Changes

### add_tools()
```python
def add_tools(self, tools: Tool | list[Tool]) -> None:
    if isinstance(tools, Tool):
        tools = [tools]
    self.config.tools.extend(tools)
```

### add_skills()
```python
def add_skills(self, skills: Skill | list[Skill]) -> None:
    if isinstance(skills, Skill):
        skills = [skills]
    self.config.skills.extend(skills)
```

### run()
```python
async def run(
    self,
    query: str,
    messages: list[dict[str, Any]] | None = None,
    instructions: str | None = None,
    stream: bool = False,
    trace: bool = False,
    verbose: bool = False,
) -> str | AsyncIterator[str]:
    # Build prompt from llm_model.system_prompt + agent.instructions
    # Execute BaseLoop
    # Return str or async iterator
```

### from_config()
```python
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
        policy=agent_config.policy,
        backend=agent_config.backend,
        max_depth=agent_config.max_depth,
        loop=agent_config.loop or BaseLoop(),
        strip_thinking=agent_config.strip_thinking,
    )
```

## Prompt Construction

At runtime:
```python
system = self.llm_model.system_prompt
if self.instructions:
    system += f"\n\nTask instructions: {self.instructions}"

messages = [
    {"role": "system", "content": system},
    # ... consumer-provided message history ...
    {"role": "user", "content": query},
]
```

## Acceptance Criteria

- [ ] `Agent` constructor accepts only the new parameter set.
- [ ] `Agent` rejects old parameters (`system_prompt`, `model`, `provider`, etc.).
- [ ] `LLMModel` is a pure value object with `system_prompt`.
- [ ] `BackendConfig` is a pure value object.
- [ ] `Agent.add_tools()` accepts single or list.
- [ ] `Agent.add_skills()` accepts single or list.
- [ ] `Agent.run()` returns `str` or `AsyncIterator[str]`.
- [ ] `Agent.from_config()` works with dict, JSON file, and YAML file.
- [ ] `Agent.to_config()` produces serialization-friendly dict.
- [ ] `ReactLoop` is removed from `agent/loop.py`.
- [ ] `BaseLoop` is the only loop class in the framework.
- [ ] `resolve_loop()` only accepts `None`, `BaseLoop` instances, or `dict` with `max_iterations`.
- [ ] New unit tests from Stage 02 pass.

## Dependencies

- **Requires**: Stage 01, 02, 03, 04, 05, 07, 08, 09, 10
