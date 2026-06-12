# Tasks: Retry, Validation, and Monitor Hook

Implementation tasks for Milestone 4.3 — Retry, Validation, and Monitor Hook. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests in `tests/integration/test_retry_integration.py` (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Validation and Retry Completion

- [ ] Wire `retry_continuation_builder` into `ProcessNode.__call__()` retry loop — use custom builder when set, default builder otherwise <!-- id: 2 -->
  - [ ] Add `_build_retry_text(self, error, attempt) -> str` helper method
  - [ ] Replace direct `self.build_retry_continuation()` call in retry loop with `_build_retry_text()`
- [ ] Implement `_handle_exhaustion(self, policy, validation, max_attempts)` method <!-- id: 3 -->
  - [ ] Handle `raise` policy — raise `NodeExecutionError` with error details
  - [ ] Handle `record_failure` policy — call `_record_failure()`
  - [ ] Handle `route_failure` policy — call `_call_failure_route()`, fallback to `_record_failure()` if no route
- [ ] Implement `_record_failure(self, validation, max_attempts)` method <!-- id: 4 -->
  - [ ] Create `SessionContextEntry` with `segment="output"` and failure metadata
  - [ ] Append to `self.session.session_context`
  - [ ] Log failure details
- [ ] Implement `_call_failure_route(self) -> bool` method <!-- id: 5 -->
  - [ ] Check if `on_complete()` defines a failure route
  - [ ] Call the failure route if defined, return `True`
  - [ ] Return `False` if no failure route defined

### Phase 2 — DecisionNode Classification Retry

- [ ] Add classification validation in `DecisionNode.__call__()` <!-- id: 6 -->
  - [ ] After `_classification_call()`, check if label matches any in `classification_labels`
  - [ ] If invalid, treat as validation failure (create `ValidationResult` with error)
- [ ] Add classification retry loop in `DecisionNode.__call__()` <!-- id: 7 -->
  - [ ] Wrap classification step in retry loop using `retry_policy.max_attempts`
  - [ ] Use same `_build_retry_text()` and `_handle_exhaustion()` as ProcessNode
  - [ ] Record analysis output on success

### Phase 3 — Monitor Hook Protocol

- [ ] Define `NodeMonitor` Protocol in `tinycua/config/types.py` <!-- id: 8 -->
  - [ ] Add `@runtime_checkable` decorator
  - [ ] Add `on_before_node_call()` method signature
  - [ ] Add `on_after_node_call()` method signature
  - [ ] Add `on_retry_exhausted()` method signature
- [ ] Define `AgentMonitor` Protocol in `tinycua/config/types.py` <!-- id: 9 -->
  - [ ] Same method signatures as `NodeMonitor`
  - [ ] Documentation notes delegation to `NodeMonitor`
- [ ] Add `monitor: NodeMonitor | None = None` field to `NodeConfigBase` <!-- id: 10 -->

### Phase 4 — Monitor Hook Integration

- [ ] Implement `_safe_call(hook_method, *args, **kwargs)` helper <!-- id: 11 -->
  - [ ] Wrap call in try/except
  - [ ] Log exceptions at debug level
  - [ ] Return None on exception
- [ ] Wire monitor hooks into `ProcessNode.__call__()` and `DecisionNode.__call__()` <!-- id: 12 -->
  - [ ] Call `monitor.on_before_node_call()` before each LLM call
  - [ ] Call `monitor.on_after_node_call()` after each validation failure
  - [ ] Call `monitor.on_retry_exhausted()` before exhaustion handling
  - [ ] Incorporate monitor continuations (if hook returns string, append to messages)
- [ ] Add `agent_monitor: AgentMonitor | None = None` parameter to `TinyCUALoop.__init__()` signature and store as `self.agent_monitor` <!-- id: 13 -->
- [ ] Wire `agent_monitor` in `TinyCUALoop._execute_node()` <!-- id: 14 -->
  - [ ] Call `agent_monitor.on_before_node_call()` before LLM call
  - [ ] Call `agent_monitor.on_after_node_call()` after response
  - [ ] Do NOT call `node.monitor` directly — all monitor calls go through `agent_monitor`

## Testing Phase

> **Note**: Unit tests below are listed here for tracking, but should be written alongside their corresponding implementation tasks (TDD-style) — not after all implementation is complete.

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 15 -->
- [ ] Write unit tests for `validate_output()` with custom `validation_fn` in `tests/unit/test_retry_validation.py` <!-- id: 16 -->
  - [ ] Test valid validation result (is_valid=True)
  - [ ] Test invalid validation result (is_valid=False, errors merged)
  - [ ] Test `validation_fn` raising exception
  - [ ] Test `validation_fn` returning None (treated as pass)
- [ ] Write unit tests for `_build_retry_text()` with custom builder in `tests/unit/test_retry_validation.py` <!-- id: 17 -->
  - [ ] Test default builder produces standard message
  - [ ] Test custom builder produces custom message
  - [ ] Test custom builder returning empty string (fallback to default)
- [ ] Write unit tests for `_handle_exhaustion()` in `tests/unit/test_retry_validation.py` <!-- id: 18 -->
  - [ ] Test `raise` raises `NodeExecutionError`
  - [ ] Test `record_failure` writes to session
  - [ ] Test `route_failure` calls failure route
  - [ ] Test `route_failure` fallback to `record_failure` when no route
- [ ] Write unit tests for `DecisionNode` classification retry in `tests/unit/test_decision_node_retry.py` <!-- id: 19 -->
  - [ ] Test valid label accepted on first attempt
  - [ ] Test invalid label triggers retry
  - [ ] Test exhaustion raises error or records failure
- [ ] Write unit tests for `NodeMonitor` hook in `tests/unit/test_monitor_hook.py` <!-- id: 20 -->
  - [ ] Test hook called at correct trigger points
  - [ ] Test hook called with correct arguments
  - [ ] Test hook exception caught and logged
  - [ ] Test hook continuation message enters retry flow
- [ ] Write unit tests for `AgentMonitor` delegation in `tests/unit/test_monitor_hook.py` <!-- id: 21 -->
  - [ ] Test `AgentMonitor` delegates to `NodeMonitor` if configured
  - [ ] Test `AgentMonitor` works without `NodeMonitor`
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 22 -->

## Verification Phase

- [ ] Verify monitor hooks do not write to `chat_history` or `session_context` <!-- id: 23 -->
- [ ] Verify `record_failure` propagation works with configured `PropagationRule.failure` <!-- id: 24 -->
- [ ] Verify `max_attempts=0` results in 1 attempt with immediate exhaustion <!-- id: 25 -->

## Documentation Phase

- [ ] Update status tracker in `spec.md` — mark completed items <!-- id: 26 -->
- [ ] Update `design.md` implementation phases — mark completed phases <!-- id: 27 -->

## Review and Merge

- [ ] Create pull request <!-- id: 28 -->
- [ ] Address review feedback <!-- id: 29 -->
- [ ] Merge to main branch <!-- id: 30 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-13*
