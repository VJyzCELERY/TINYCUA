# Tasks: Stage 2 Agent Configuration and Creation

Implementation tasks for Stage 2 Agent Configuration and Creation. Check off items as completed.

## Implementation Phase

- [x] Update AgentPolicy and AgentConfig models in `tinycua_sdk/agent/config.py` to match v2 spec fields and defaults <!-- id: 0 -->
- [x] Implement `AgentConfig.to_config()` to serialize nested models per spec <!-- id: 1 -->
- [x] Remove v1 `AgentDefinition` and update references to use `AgentConfig` <!-- id: 2 -->
- [x] Update `Agent` constructor signature and defaults in `tinycua_sdk/agent/agent.py` <!-- id: 3 -->
- [x] Add `Agent` proxies and `add_tools` / `add_skills` mutation helpers <!-- id: 4 -->
- [x] Simplify `AgentExecutor` to config holder with cancel stub and NotImplemented `run` <!-- id: 5 -->

## Testing Phase

- [x] Update `tests/integration/goals/test_gs_02_agent_creation.py` to cover v2 requirements <!-- id: 6 -->
- [x] Run `pytest -v tests/integration/goals/test_gs_02_agent_creation.py` <!-- id: 7 -->

## Verification Phase

- [x] Run `goals/getting-started/02_agent_creation.py` and confirm expected output <!-- id: 8 -->
- [x] Confirm `Agent().to_config()` includes nested serialization for llm, tools, skills, policy <!-- id: 9 -->

## Documentation Phase

- [x] Update any affected migration notes if present <!-- id: 10 -->

## Review and Merge

- [x] Perform a local review of the changes against spec requirements <!-- id: 11 -->
- [x] Create a pull request <!-- id: 12 -->
- [x] Address review feedback <!-- id: 13 -->
- [ ] Merge to main branch <!-- id: 14 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement-plan` to execute these tasks*
*Last updated: 2026-05-06*
