# Tasks: Stage 7 Security - Guardrails and Permissions

Implementation tasks for Stage 7 Security. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for guardrail behavior in `tests/integration/goals/test_adv_02_guardrail_system.py` <!-- id: 0 -->
- [ ] Write integration tests for permission behavior in `tests/integration/goals/test_adv_03_permission_system.py` <!-- id: 1 -->
- [ ] Run integration tests - expect RED before implementation: `cd src/tinycua-sdk && uv run pytest tests/integration/goals/test_adv_02_guardrail_system.py tests/integration/goals/test_adv_03_permission_system.py -v` <!-- id: 2 -->

## Implementation Phase

- [ ] Add or confirm `AgentConfig.tool_permissions` and `AgentConfig.approval_workflow` fields support the stage-07 API <!-- id: 3 -->
- [ ] Add or confirm `Agent.tool_permissions` is mutable and backed by config state <!-- id: 4 -->
- [ ] Update `ToolExecutor.execute()` permission handling <!-- id: 5 -->
  - [ ] Default missing permission entries to `"allow"`
  - [ ] Return a permission error dict for `"deny"`
  - [ ] Route `"ask"` through approval workflow(s)
  - [ ] Deny safely when `"ask"` has no workflow configured
- [ ] Add chained approval workflow support in execution order <!-- id: 6 -->
  - [ ] Normalize a single workflow to a list
  - [ ] Stop at the first workflow returning `{"approved": False, ...}`
  - [ ] Invoke the tool only after all workflows approve
- [ ] Confirm `ApprovalWorkflow` remains the public extension point for consumer guardrails <!-- id: 7 -->

## Testing Phase

- [ ] Run integration tests - expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/integration/goals/test_adv_02_guardrail_system.py tests/integration/goals/test_adv_03_permission_system.py -v` <!-- id: 8 -->
- [ ] Add or update unit tests for `ToolExecutor.execute()` permission and approval branches <!-- id: 9 -->
- [ ] Run unit tests: `cd src/tinycua-sdk && uv run pytest tests/unit/test_tool_executor.py tests/unit/test_approval.py -v` <!-- id: 10 -->
- [ ] Run full SDK suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 11 -->

## Verification Phase

- [ ] Verify denied tools are not invoked by checking side-effect counters in tests <!-- id: 12 -->
- [ ] Verify guardrail denial dicts are returned unchanged to the caller <!-- id: 13 -->
- [ ] Verify runtime mutation of `agent.tool_permissions` changes the next execution result <!-- id: 14 -->
- [ ] Verify missing permission entries execute through the default `"allow"` path <!-- id: 15 -->

## Documentation Phase

- [ ] Confirm `spec.md` and `design.md` match the implemented permission and guardrail behavior <!-- id: 16 -->
- [ ] Update SDK examples or README only if the public usage examples are missing guardrail coverage <!-- id: 17 -->
- [ ] Update changelog only if this repository tracks SDK-facing stage changes there <!-- id: 18 -->

## Review and Merge

- [ ] Create pull request for the planning and implementation changes <!-- id: 19 -->
- [ ] Address review feedback <!-- id: 20 -->
- [ ] Merge to base branch after checks pass <!-- id: 21 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-12*
