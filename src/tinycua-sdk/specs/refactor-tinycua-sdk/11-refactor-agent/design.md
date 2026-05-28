# Stage 11 — Design: Refactor Agent

## Overview

Refactor the `Agent` class to be stateless and fully runnable. Introduce `LLMModel` and `BackendConfig`, remove obsolete parameters, simplify the loop to only `BaseLoop`.

## Architecture

```
Agent (public API)
  ├── AgentConfig (Pydantic model — serialization)
  ├── AgentDefinition (base properties — name, instructions)
  ├── AgentExecutor (run/stream logic)
  │     └── BaseLoop (agent execution loop)
  ├── LLMModel (Pydantic model — LLM endpoint config)
  └── BackendConfig (Pydantic model — local/remote config)
```

## Design Decisions

### Why LLMModel?

1. **Value object**: Pure data, no I/O, no persistence.
2. **Model-specific tuning**: `system_prompt` lives here because different models interpret prompts differently.
3. **Swappable**: Change models without changing agent logic.

### Why BackendConfig?

1. **Explicit**: `backend=BackendConfig(kind=BackendKind.REMOTE)` is clearer than `mode="remote"`.
2. **Extensible**: Can add fields (url, api_key, headers) without changing Agent constructor.

### Why Only BaseLoop?

1. **Minimal SDK**: The SDK provides one simple loop. Consumers subclass for custom behavior.
2. **ReAct is an example**: The ReAct pattern is demonstrated in examples, not built into the framework.
3. **No magic strings**: No `"react"` string resolution — loops are objects.

## Files to Modify

| File | Changes |
|------|---------|
| `agent/agent.py` | New constructor, add_tools, add_skills, from_config, run |
| `agent/executor.py` | Remove remote execution, session/memory references |
| `agent/definition.py` | Remove obsolete fields (system_prompt, model, provider, etc.) |
| `agent/config.py` | Update AgentConfig — add LLMModel, BackendConfig |
| `agent/loop.py` | Remove ReactLoop, keep only BaseLoop |
| `agent/loop_resolver.py` | Simplify to only resolve BaseLoop instances |
| `agent/validator.py` | Remove "react" from valid loop types |
| `agent/templates.py` | Update to use new config structure |
| `agent/llm_model.py` | **New file** — LLMModel value object |
| `agent/backend_kind.py` | **New file** — BackendConfig, BackendKind |

## Constructor (Target)

```python
class Agent(AgentExecutor):
    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        llm_model: LLMModel = LLMModel(),
        tools: list[Tool] | None = None,
        skills: list[Skill] | None = None,
        policy: AgentPolicy | None = None,
        backend: BackendConfig | None = None,
        sub_agents: list[Agent] | None = None,
        max_depth: int = 3,
        loop: BaseLoop | None = None,
        strip_thinking: bool | list[str] | None = None,
    ):
        self.config = AgentConfig(
            name=name,
            instructions=instructions,
            llm_model=llm_model,
            policy=policy or AgentPolicy(),
            backend=backend or BackendConfig(),
            max_depth=max_depth,
            loop=loop,
            strip_thinking=strip_thinking,
        )
        self._tools = list(tools or [])
        self._skills = list(skills or [])
        self._sub_agents = list(sub_agents or [])
```

## New Classes

### LLMModel

```python
class LLMModel(BaseModel):
    """Immutable LLM endpoint configuration."""
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
    def from_dict(cls, data: dict[str, Any]) -> "LLMModel":
        return cls(**data)
```

### BackendConfig

```python
class BackendKind(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"

class BackendConfig(BaseModel):
    """Where the agent should run."""
    model_config = ConfigDict(frozen=True)
    
    kind: BackendKind = BackendKind.LOCAL
    url: str | None = None
    api_key: SecretStr = SecretStr("")
    headers: dict[str, str] = Field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendConfig":
        return cls(**data)
```

### BaseLoop (Refactored)

```python
class BaseLoop:
    """Minimal base class for agent execution loops.
    
    The SDK provides only this base class. Consumers subclass it
    for custom behavior (e.g., ReAct, Plan-and-Execute, etc.).
    """
    
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
    
    async def run(self, agent: Agent, messages: list[dict], tools: list[Tool]) -> str:
        """Execute the agent loop.
        
        Args:
            agent: The agent being run.
            messages: Full message history including system prompt.
            tools: Tools available to the agent.
        
        Returns:
            The final response string.
        """
        # Default implementation: single LLM call
        for i in range(self.max_iterations):
            response = await agent._call_llm(messages)
            # Check for tool calls
            tool_calls = _extract_tool_calls(response)
            if not tool_calls:
                return response
            # Execute tool calls and append results
            for call in tool_calls:
                result = _execute_tool_call(call, tools)
                messages.append({"role": "tool", "content": result})
        return response
```

### AgentConfig (Updated)

```python
class AgentConfig(BaseModel):
    name: str = "assistant"
    instructions: str = ""
    llm_model: LLMModel = Field(default_factory=LLMModel)
    tools: list[Tool] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    policy: AgentPolicy = Field(default_factory=AgentPolicy)
    backend: BackendConfig = Field(default_factory=BackendConfig)
    sub_agents: list[Agent] = Field(default_factory=list)
    max_depth: int = 3
    loop: BaseLoop | None = None
    strip_thinking: bool | list[str] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        return cls(**data)
```

## Method Implementations

### add_tools()

```python
def add_tools(self, tools: Tool | list[Tool]) -> None:
    """Add tools to the agent.
    
    Accepts a single Tool or a list of Tools.
    """
    if isinstance(tools, Tool):
        tools = [tools]
    self._tools.extend(tools)
```

### add_skills()

```python
def add_skills(self, skills: Skill | list[Skill]) -> None:
    """Add skills to the agent.
    
    Accepts a single Skill or a list of Skills.
    """
    if isinstance(skills, Skill):
        skills = [skills]
    self._skills.extend(skills)
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
    """Run the agent on a query.
    
    Args:
        query: The user query.
        messages: Optional conversation history.
        instructions: Optional override for agent instructions.
        stream: If True, return an async iterator of chunks.
        trace: If True, print execution trace.
        verbose: If True, print verbose output.
    
    Returns:
        Response string (or async iterator if stream=True).
    """
    # Build system prompt
    system = self.config.llm_model.system_prompt
    task_instructions = instructions or self.config.instructions
    if task_instructions:
        system += f"\n\nTask instructions: {task_instructions}"
    
    # Build messages
    full_messages = [{"role": "system", "content": system}]
    if messages:
        full_messages.extend(messages)
    full_messages.append({"role": "user", "content": query})
    
    # Run loop
    loop = self.config.loop or BaseLoop()
    if stream:
        return loop.run_stream(self, full_messages, self._tools)
    return await loop.run(self, full_messages, self._tools)
```

### from_config()

```python
@classmethod
def from_config(cls, config: str | Path | dict[str, Any]) -> Agent:
    """Create an agent from a configuration.
    
    Args:
        config: Path to YAML/JSON file, or a dict.
    
    Returns:
        Agent instance.
    """
    if isinstance(config, (str, Path)):
        config = _load_yaml_or_json(config)
    
    agent_config = AgentConfig.from_dict(config)
    
    # Resolve tools (names → Tool instances)
    tools = []
    for t in config.get("tools", []):
        if isinstance(t, str):
            tools.append(_resolve_tool_by_name(t))  # Consumer provides resolver
        elif isinstance(t, dict):
            tools.append(Tool.from_dict(t))
        elif isinstance(t, Tool):
            tools.append(t)
    
    # Resolve skills (dicts → Skill instances)
    skills = []
    for s in config.get("skills", []):
        if isinstance(s, dict):
            skills.append(Skill.from_dict(s))
        elif isinstance(s, Skill):
            skills.append(s)
    
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

### to_config()

```python
def to_config(self) -> dict[str, Any]:
    """Serialize the agent to a configuration dict."""
    return {
        "name": self.config.name,
        "instructions": self.config.instructions,
        "llm_model": self.config.llm_model.to_dict(),
        "tools": [t.to_config() for t in self._tools],
        "skills": [s.to_dict() for s in self._skills],
        "policy": self.config.policy.to_dict(),
        "backend": self.config.backend.to_dict(),
        "max_depth": self.config.max_depth,
        "strip_thinking": self.config.strip_thinking,
    }
```

## Prompt Construction

At runtime, the agent constructs the final prompt from:

1. `LLMModel.system_prompt` — model-specific behavior tuning
2. `Agent.instructions` — task-specific directive
3. `user_input` — runtime query

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
- [ ] `ReactLoop` is removed; only `BaseLoop` remains.
- [ ] `resolve_loop()` only accepts `None`, `BaseLoop` instances, or `dict` with `max_iterations`.
- [ ] New unit tests from Stage 02 pass.

## Dependencies

- **Requires**: Stage 01, 02, 03, 04, 05, 07, 08, 09, 10.
- **Blocks**: Stage 12 (Config refactor depends on Agent changes).
