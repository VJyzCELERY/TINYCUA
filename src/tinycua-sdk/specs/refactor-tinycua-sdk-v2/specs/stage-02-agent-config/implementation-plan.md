# Implementation: Stage 2 Agent Configuration and Creation

Implement the v2 Agent configuration model and constructor behavior so agents can be instantiated and configured (but not executed) exactly per spec, including serialization and obsolete-parameter rejection.

## Context

- **Spec Reference**: `src/tinycua-sdk/specs/refactor-tinycua-sdk-v2/specs/stage-02-agent-config/spec.md`
- **Design Reference**: `src/tinycua-sdk/specs/refactor-tinycua-sdk-v2/specs/stage-02-agent-config/design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Proposed Changes

### Agent Configuration Models

#### [MODIFY] `src/tinycua-sdk/tinycua_sdk/agent/config.py`

- **Define AgentPolicy**: Keep behavior-only fields (`max_tool_calls`, `parallel_tool_calls`) with defaults and frozen config.
- **Define AgentConfig**: Single source of truth for v2 fields (`name`, `instructions`, `llm_model`, `tools`, `skills`, `policy`, `metadata`, `loop`, `tool_permissions`, `approval_workflow`).
- **Implement serialization**: `to_config()` returns a plain dict with nested serialization of `llm_model`, `tools`, `skills`, and `policy`.

#### [DELETE] `src/tinycua-sdk/tinycua_sdk/agent/definition.py`

- **Remove v1 AgentDefinition**: Collapse into `AgentConfig` as per design and eliminate obsolete v1 fields.

### Agent Public API

#### [MODIFY] `src/tinycua-sdk/tinycua_sdk/agent/agent.py`

- **Constructor update**: Match v2 signature and defaults, instantiate `LanguageModel()` and `AgentPolicy()` when absent, and fill empty lists/dicts.
- **Obsolete param rejection**: Reject obsolete kwargs with `TypeError` including the removed parameter name.
- **Config storage**: Build `AgentConfig` and pass to `AgentExecutor`.
- **Convenience proxies**: Properties for core config fields plus `add_tools`, `add_skills`, and `to_config` methods.

#### [MODIFY] `src/tinycua-sdk/tinycua_sdk/agent/executor.py`

- **Simplify executor**: Store config, keep `cancel` and `is_cancelled`, and raise `NotImplementedError` in `run` (execution deferred to Stage 3).

### Tests and Fixtures

#### [MODIFY] `src/tinycua-sdk/tests/integration/goals/test_gs_02_agent_creation.py`

- **Align with v2 spec**: Ensure tests cover minimal creation, named agent, policy, metadata, obsolete params, dynamic add, and serialization.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| AgentConfig | Modify | Becomes the single, full config model for v2 |
| AgentDefinition | Remove | Eliminated in favor of AgentConfig |
| Agent | Modify | New constructor and proxy surface per v2 |
| AgentExecutor | Modify | Simplified config holder with cancel stub |

## Data Model Changes

```python
class AgentPolicy(BaseModel):
    max_tool_calls: int = 10
    parallel_tool_calls: bool = True


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

## API Changes

### Modified API Surface

| Area | Change |
|------|--------|
| Agent constructor | New signature with v2 defaults and obsolete param rejection |
| Agent API | `add_tools`, `add_skills`, `to_config` added/updated |

## Verification Plan

### Automated Tests

- [ ] Run `pytest -v tests/integration/goals/test_gs_02_agent_creation.py`

### Manual Verification

- [ ] Run `goals/getting-started/02_agent_creation.py` and confirm expected output

### Performance Considerations

- [ ] Not applicable (config-only changes)

## Dependencies

### External Dependencies

- None

### Internal Dependencies

- [ ] Stage 3 will provide `BaseLoop` and `ApprovalWorkflow` types referenced by config

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Incomplete v1 cleanup | Medium | Remove AgentDefinition and update imports to AgentConfig |
| Serialization mismatch | High | Mirror spec in `to_config()` and validate via integration test |
| Obsolete param handling too strict/loose | Medium | Use explicit allowlist of removed params and test TypeError messages |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-06*
