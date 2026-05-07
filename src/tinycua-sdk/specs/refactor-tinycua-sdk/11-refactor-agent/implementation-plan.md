# Implementation: Stage 11 — Refactor Agent

Refactor the `Agent` class to be stateless and fully runnable. Introduce `LLMModel` and `BackendConfig` value objects, remove obsolete parameters, and simplify the execution loop to only `BaseLoop`.

## Context

- **Spec Reference**: [spec.md](spec.md)
- **Design Reference**: [design.md](design.md)
- **Priority**: P0
- **Estimated Effort**: L

## Proposed Changes

### New Value Objects

#### [NEW] `agent/llm_model.py`

- **[Description]**: Create `LLMModel` Pydantic model as an immutable value object for LLM endpoint configuration.
- **[Fields]**: `provider`, `model_name`, `base_url`, `api_key` (SecretStr), `max_context`, `temperature`, `system_prompt`.
- **[Rationale]**: Centralizes model-specific configuration; `system_prompt` lives here because different models interpret prompts differently.

#### [NEW] `agent/backend_kind.py`

- **[Description]**: Create `BackendKind` enum (`LOCAL`, `REMOTE`) and `BackendConfig` Pydantic model.
- **[Fields]**: `kind`, `url`, `api_key` (SecretStr), `headers`.
- **[Rationale]**: Makes local vs. remote execution explicit and extensible without changing the `Agent` constructor.

### Agent Core Refactor

#### [MODIFY] `agent/agent.py`

- **[Description of change]**: Replace constructor parameter set. Remove: `system_prompt`, `model`, `provider`, `base_url`, `api_key`, `mode`, `backend_url`, `backend_api_key`, `backend_headers`, `agent_id`, `planning_prompt`, `short_term_memory`, `long_term_memory`. Add: `llm_model` (LLMModel), `backend` (BackendConfig), `strip_thinking`. Add methods: `add_tools()`, `add_skills()`, `from_config()`, `run()`, `to_config()`.
- **[Rationale]**: Makes `Agent` stateless, fully runnable, and eliminates obsolete remote execution / memory parameters.
- **[Breaking changes]**: Old constructor signatures are no longer accepted.

#### [MODIFY] `agent/config.py`

- **[Description of change]**: Update `AgentConfig` Pydantic model to include `llm_model: LLMModel`, `backend: BackendConfig`, `loop: BaseLoop | None`, and `strip_thinking`.
- **[Rationale]**: Serialization layer must reflect the new runtime structure.

#### [MODIFY] `agent/definition.py`

- **[Description of change]**: Remove obsolete fields such as `system_prompt`, `model`, `provider`, `base_url`, etc.
- **[Rationale]**: These values now live inside `LLMModel`.

### Execution Layer

#### [MODIFY] `agent/executor.py`

- **[Description of change]**: Remove remote execution paths, session/memory references, and old parameter wiring.
- **[Rationale]**: Agent is now local-first and stateless; remote concerns belong to `BackendConfig` consumers.

#### [MODIFY] `agent/loop.py`

- **[Description of change]**: Remove `ReactLoop`. Keep only `BaseLoop` with `max_iterations` and an async `run(agent, messages, tools)` method.
- **[Rationale]**: SDK provides a minimal, extensible base. ReAct is demonstrated in examples, not built into the framework.

#### [MODIFY] `agent/loop_resolver.py`

- **[Description of change]**: Simplify `resolve_loop()` to only accept `None`, `BaseLoop` instances, or `dict` with `max_iterations`.
- **[Rationale]**: No more string-based loop resolution (e.g., `"react"`).

#### [MODIFY] `agent/validator.py`

- **[Description of change]**: Remove `"react"` from valid loop types.
- **[Rationale]**: Only `BaseLoop` / `"default"` is valid now.

### Templates

#### [MODIFY] `agent/templates.py`

- **[Description of change]**: Update templates to read from `llm_model.system_prompt` and new config structure.
- **[Rationale]**: Prompt construction now sources system prompt from `LLMModel`.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `LLMModel` | New | Immutable value object for LLM endpoint config (incl. `system_prompt`) |
| `BackendConfig` | New | Immutable value object for local/remote backend config |
| `BackendKind` | New | Enum: `LOCAL`, `REMOTE` |
| `Agent` | Modify | New constructor, new methods (`add_tools`, `add_skills`, `run`, `from_config`, `to_config`) |
| `AgentConfig` | Modify | Adds `llm_model`, `backend`, `loop`, `strip_thinking` |
| `AgentDefinition` | Modify | Removes obsolete fields |
| `AgentExecutor` | Modify | Removes remote execution and session/memory references |
| `BaseLoop` | Modify | Kept as the only loop class; default single-call + tool loop |
| `ReactLoop` | Remove | Removed from the framework |
| `loop_resolver` | Modify | Only resolves `None`, `BaseLoop`, or `dict` with `max_iterations` |
| `validator` | Modify | Drops `"react"` from valid loop types |
| `templates` | Modify | Updated to use new config structure |

## Data Model Changes

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


class BackendKind(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


class BackendConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: BackendKind = BackendKind.LOCAL
    url: str | None = None
    api_key: SecretStr = SecretStr("")
    headers: dict[str, str] = Field(default_factory=dict)


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
```

## API Changes

### New Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `Agent.add_tools` | `(tools: Tool \| list[Tool]) -> None` | Append tool(s) to the agent |
| `Agent.add_skills` | `(skills: Skill \| list[Skill]) -> None` | Append skill(s) to the agent |
| `Agent.run` | `async (query, messages=None, instructions=None, stream=False, trace=False, verbose=False) -> str \| AsyncIterator[str]` | Execute the agent loop |
| `Agent.from_config` | `@classmethod (config: str \| Path \| dict) -> Agent` | Instantiate from file or dict |
| `Agent.to_config` | `() -> dict[str, Any]` | Serialize to dict |

### Modified Constructor

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

### Removed Parameters

- `system_prompt` → now inside `LLMModel`
- `model`, `provider`, `base_url`, `api_key` → now inside `LLMModel`
- `mode`, `backend_url`, `backend_api_key`, `backend_headers` → now inside `BackendConfig`
- `agent_id`, `planning_prompt`, `short_term_memory`, `long_term_memory` → removed

## Verification Plan

### Automated Tests

- [ ] Unit tests for `LLMModel` creation and serialization
- [ ] Unit tests for `BackendConfig` creation and serialization
- [ ] Unit tests for `Agent` constructor with new parameters
- [ ] Unit tests verifying `Agent` rejects old parameters
- [ ] Unit tests for `Agent.add_tools()` (single and list)
- [ ] Unit tests for `Agent.add_skills()` (single and list)
- [ ] Unit tests for `Agent.run()` returning `str` and `AsyncIterator[str]`
- [ ] Unit tests for `Agent.from_config()` with dict, JSON file, and YAML file
- [ ] Unit tests for `Agent.to_config()` producing serialization-friendly dict
- [ ] Unit tests confirming `ReactLoop` is removed and `BaseLoop` is the only loop
- [ ] Unit tests for `resolve_loop()` accepting only `None`, `BaseLoop`, or `dict` with `max_iterations`

### Manual Verification

- [ ] Run new unit tests from Stage 02 and confirm they pass
- [ ] Verify prompt construction uses `llm_model.system_prompt` + `instructions`

## Rollout Strategy

1. **Phase 1** (New value objects): Implement `LLMModel` and `BackendConfig` with tests.
2. **Phase 2** (Agent refactor): Update `Agent`, `AgentConfig`, `AgentDefinition`, `AgentExecutor`.
3. **Phase 3** (Loop simplification): Remove `ReactLoop`, update `loop_resolver` and `validator`.
4. **Phase 4** (Integration): Update `templates.py`, wire `from_config`/`to_config`, run full test suite.

## Dependencies

### Internal Dependencies

- [ ] Depends on: Stage 01, 02, 03, 04, 05, 07, 08, 09, 10
- [ ] Blocks: Stage 12 (Config refactor depends on Agent changes)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking changes to `Agent` constructor break downstream consumers | High | Ensure clear migration path documented; old parameters explicitly rejected with helpful errors |
| `from_config` tool/skill resolution depends on external registries | Medium | Keep resolution logic pluggable (`_resolve_tool_by_name`) and fallback gracefully |
| Removal of `ReactLoop` may affect users relying on built-in ReAct | Medium | Document that ReAct should be implemented as a `BaseLoop` subclass or via examples |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
