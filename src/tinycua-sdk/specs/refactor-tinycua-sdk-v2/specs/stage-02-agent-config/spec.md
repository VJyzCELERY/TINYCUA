# Stage 2: Agent Configuration & Creation — Specification

**Status**: Draft | In Progress | Complete
**Created**: 2026-05-02
**Last Updated**: 2026-05-02
**Subproject(s) Affected**: tinycua-sdk

## Objective
An `Agent` can be instantiated and configured with all v2 parameters, but cannot yet execute. The constructor shape, config model, and serialization of config must match the spec exactly.

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
    **kwargs,
):
```

**Default behavior:**
- If `llm_model` is `None`, create `LanguageModel()` with defaults.
- If `policy` is `None`, create `AgentPolicy()` with defaults.
- If `tools` is `None`, use empty list.
- If `skills` is `None`, use empty list.
- If `metadata` is `None`, use empty dict.
- If `tool_permissions` is `None`, use empty dict.

**Obsolete parameter rejection:**
- Any keyword in `kwargs` that matches an obsolete parameter name raises `TypeError` with a clear message.
- Obsolete names: `system_prompt`, `model`, `provider`, `base_url`, `api_key`, `mode`, `backend_url`, `backend_api_key`, `backend_headers`, `agent_id`, `planning_prompt`, `short_term_memory`, `long_term_memory`, `session_id`, `sub_agents`, `max_depth`, `strip_thinking`, `backend`.

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

- [ ] Obsolete Parameters Rejected - tests/integration/goals/test_gs_02_agent_creation.py - PASS - `print('PASS')`
  Description: Passing obsolete params raises `TypeError`.

- [ ] Dynamic add_tools / add_skills - tests/integration/goals/test_gs_02_agent_creation.py - PASS - `print('PASS')`
  Description: Tools and skills can be added after creation.

- [ ] to_config Serializes - tests/integration/goals/test_gs_02_agent_creation.py - PASS - `print('PASS')`
  Description: `to_config()` returns a dict with all fields.

- [ ] Integration Test Pass - tests/integration/goals/test_gs_02_agent_creation.py - 1 passed, 0 failed - pytest -v

## Integration Test File
- `tests/integration/goals/test_gs_02_agent_creation.py`
