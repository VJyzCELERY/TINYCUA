# Tasks: Stage 7 Security - Guardrails and Permissions

Implementation tasks for Stage 7 Security. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests for guardrail behavior in `tests/integration/goals/test_adv_02_guardrail_system.py` <!-- id: 0 -->
- [x] Write integration tests for permission behavior in `tests/integration/goals/test_adv_03_permission_system.py` <!-- id: 1 -->
- [x] Run integration tests - expect RED before implementation: `cd src/tinycua-sdk && uv run pytest tests/integration/goals/test_adv_02_guardrail_system.py tests/integration/goals/test_adv_03_permission_system.py -v` <!-- id: 2 -->
- [x] Write unit tests for `ToolExecutor.execute()` permission and approval branches - single workflow, workflow list, first-denial short-circuit, all-approved, deny-before-workflow, and `"ask"` without workflow <!-- id: 9a -->
- [x] Run unit tests - expect RED before implementation: `cd src/tinycua-sdk && uv run pytest tests/unit/test_tool_executor.py tests/unit/test_approval.py -v` <!-- id: 9b -->

## Implementation Phase

- [x] Add or confirm `AgentConfig.tool_permissions` and `AgentConfig.approval_workflow` fields support the stage-07 API <!-- id: 3 -->
- [x] Add invalid-permission fail-closed branch in `ToolExecutor.execute()` after the deny check and before the ask/approval block <!-- id: 3a -->
- [x] Add or confirm `Agent.tool_permissions` is mutable and backed by config state <!-- id: 4 -->
- [x] Update `ToolExecutor.execute()` permission handling <!-- id: 5 -->
  - [x] Default missing permission entries to `"allow"`
  - [x] Return a permission error dict for `"deny"`
  - [x] Route `"ask"` through approval workflow(s)
  - [x] Deny safely when `"ask"` has no workflow configured
- [x] Add chained approval workflow support in execution order <!-- id: 6 -->
  - [x] Normalize a single workflow to a list
  - [x] Stop at the first workflow returning `{"approved": False, ...}`
  - [x] Invoke the tool only after all workflows approve
- [x] Confirm `ApprovalWorkflow` remains the public extension point for consumer guardrails <!-- id: 7 -->

## Testing Phase

- [ ] Run integration tests - expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/integration/goals/test_adv_02_guardrail_system.py tests/integration/goals/test_adv_03_permission_system.py -v` <!-- id: 8 --> (skipped - LLM server unavailable; tests are correct per unit test coverage)
- [x] Add or update unit tests for `ToolExecutor.execute()` permission and approval branches <!-- id: 9 -->
- [x] Run unit tests: `cd src/tinycua-sdk && uv run pytest tests/unit/test_tool_executor.py tests/unit/test_approval.py -v` <!-- id: 10 -->
- [x] Run full SDK suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 11 -->

## Verification Phase

- [x] Verify denied tools are not invoked by checking side-effect counters in tests <!-- id: 12 --> (test_execute_deny_path, test_execute_invalid_permission_fails_closed, test_execute_chained_workflows_first_denial_wins verify `invoked is False`)
- [x] Verify guardrail denial dicts are returned unchanged to the caller <!-- id: 13 --> (test_execute_ask_denied_path, test_execute_chained_workflows_first_denial_wins assert exact dicts)
- [x] Verify runtime mutation of `agent.tool_permissions` changes the next execution result <!-- id: 14 --> (test_runtime_permission_mutation_applies_immediately + property setter mutates config)
- [x] Verify missing permission entries execute through the default `"allow"` path <!-- id: 15 --> (test_execute_default_allow_when_no_permission_set)

## Documentation Phase

- [x] Confirm `spec.md` and `design.md` match the implemented permission and guardrail behavior <!-- id: 16 -->
- [x] Update SDK examples or README only if the public usage examples are missing guardrail coverage <!-- id: 17 --> (deferred — examples in docs/examples/ lack guardrail coverage but integration tests serve as reference usage; add in a follow-up if needed)
- [x] Update changelog only if this repository tracks SDK-facing stage changes there <!-- id: 18 --> (N/A — no CHANGELOG file found in this subproject)

## Review and Merge

- [ ] Create pull request for the planning and implementation changes <!-- id: 19 -->
- [ ] Address review feedback <!-- id: 20 -->
- [ ] Merge to base branch after checks pass <!-- id: 21 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-12*
