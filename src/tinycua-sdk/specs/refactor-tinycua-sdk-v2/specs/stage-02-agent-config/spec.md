# Stage 2: Agent Configuration & Creation — Specification

**Status**: Draft | In Progress | Complete
**Created**: 2026-05-02
**Last Updated**: 2026-05-02
**Subproject(s) Affected**: tinycua-sdk

## Objective
An `Agent` can be instantiated and configured with all parameters, but cannot yet execute. The constructor shape, config model, and serialization of config must match the spec exactly.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

## Reference
- [`goals/getting-started/02_agent_creation.py`](../goals/getting-started/02_agent_creation.py)

## Requirements

### R-2.1: AgentPolicy

Behavior-only settings. No LLM inference parameters.

```python
class AgentPolicy(BaseModel):
    max_tool_calls: int = 10
    parallel_tool_calls: bool = True
```

**Removed from v1:** `temperature` (lives on `LanguageModel` only).

### R-2.2: AgentConfig

```python
class AgentConfig(BaseModel):
    name: str = "assistant"
    instructions: str = ""
    llm_model: LanguageModel
    tools: list[Tool] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    policy: AgentPolicy = Field(default_factory=AgentPolicy)
    metadata: dict = Field(default_factory=dict)
    loop: BaseLoop | None = None
    tool_permissions: dict[str, Literal["allow", "ask", "deny"]] = Field(default_factory=dict)
    approval_workflow: ApprovalWorkflow | None = None
```

### R-2.3: Agent Constructor

```python
def __init__(
    self,
    name: str = "assistant",
    instructions: str = "",
    llm_model: LanguageModel | None = None,
    tools: list[Tool] | None = None,
    skills: list[Skill] | None = None,
    policy: AgentPolicy | None = None,
    metadata: dict | None = None,
    loop: BaseLoop | None = None,
    tool_permissions: dict[str, Literal["allow", "ask", "deny"]] | None = None,
    approval_workflow: ApprovalWorkflow | None = None,
):
```

**Default behavior:**
- If `llm_model` is `None`, create `LanguageModel()` with defaults.
- If `policy` is `None`, create `AgentPolicy()` with defaults.
- If `tools` is `None`, use empty list.
- If `skills` is `None`, use empty list.
- If `metadata` is `None`, use empty dict.
- If `tool_permissions` is `None`, use empty dict.

**Constructor is clean:** No backward-compatibility validation. Unknown keyword arguments produce Python's standard `TypeError`.

### R-2.4: Dynamic Composition

- `add_tools(tool_or_list: Tool | list[Tool]) -> None` — appends to `self.config.tools`.
- `add_skills(skill_or_list: Skill | list[Skill]) -> None` — appends to `self.config.skills`.
- Both mutate in place.

### R-2.5: Config Serialization

- `to_config() -> dict` — returns a plain dict representation of the agent's configuration. Includes nested serialization of `llm_model`, `tools`, `skills`, `policy`.

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] Minimal Agent Creation - tests/integration/goals/test_gs_02_agent_creation.py - PASS - `print('PASS')`
  Description: `Agent()` with no args creates a valid agent.

- [ ] Named Agent with Instructions - tests/integration/goals/test_gs_02_agent_creation.py - PASS - `print('PASS')`
  Description: Agent with custom name and instructions.

- [ ] Agent with Policy - tests/integration/goals/test_gs_02_agent_creation.py - PASS - `print('PASS')`
  Description: Policy settings are stored correctly.

- [ ] Agent with Metadata - tests/integration/goals/test_gs_02_agent_creation.py - PASS - `print('PASS')`
  Description: Consumer-defined metadata is preserved.

- [ ] Dynamic add_tools / add_skills - tests/integration/goals/test_gs_02_agent_creation.py - PASS - `print('PASS')`
  Description: Tools and skills can be added after creation.

- [ ] to_config Serializes - tests/integration/goals/test_gs_02_agent_creation.py - PASS - `print('PASS')`
  Description: `to_config()` returns a dict with all fields.

- [ ] Integration Test Pass - tests/integration/goals/test_gs_02_agent_creation.py - 1 passed, 0 failed - pytest -v

## Integration Test File
- `tests/integration/goals/test_gs_02_agent_creation.py`
