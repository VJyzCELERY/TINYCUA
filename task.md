# Tasks: Retry, Validation, Monitor Hook, and Streaming Events

Implementation tasks for Milestones 4.3 and 4.4. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for retry, validation, and monitor hook in `tests/integration/test_retry_integration.py` <!-- id: 0 -->
- [ ] Write integration tests for streaming and transcript events <!-- id: 1 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

### Phase 1 — Validation and Retry Completion

- [ ] Wire `retry_continuation_builder` into `ProcessNode.__call__()` retry loop — use custom builder when set, default builder otherwise <!-- id: 3 -->
  - [ ] Add `_build_retry_text(self, error, attempt) -> str` helper method
  - [ ] Replace direct `self.build_retry_continuation()` call in retry loop with `_build_retry_text()`
- [ ] Implement `_handle_exhaustion(self, policy, validation, max_attempts)` method <!-- id: 4 -->
  - [ ] Handle `raise` policy — raise `NodeExecutionError` with error details
  - [ ] Handle `record_failure` policy — call `_record_failure()`
  - [ ] Handle `route_failure` policy — call `_call_failure_route()`, fallback to `_record_failure()` if no route
- [ ] Implement `_record_failure(self, validation, max_attempts)` method <!-- id: 5 -->
  - [ ] Create `SessionContextEntry` with `segment="output"` and failure metadata
  - [ ] Append to `self.session.session_context`
  - [ ] Log failure details
- [ ] Implement `_call_failure_route(self) -> bool` method <!-- id: 6 -->
  - [ ] Check if `on_complete()` defines a failure route
  - [ ] Call the failure route if defined, return `True`
  - [ ] Return `False` if no failure route defined

### Phase 2 — DecisionNode Classification Retry

- [ ] Add classification validation in `DecisionNode.__call__()` <!-- id: 7 -->
  - [ ] After `_classification_call()`, check if label matches any in `classification_labels`
  - [ ] If invalid, treat as validation failure (create `ValidationResult` with error)
- [ ] Add classification retry loop in `DecisionNode.__call__()` <!-- id: 8 -->
  - [ ] Wrap classification step in retry loop using `retry_policy.max_attempts`
  - [ ] Use same `_build_retry_text()` and `_handle_exhaustion()` as ProcessNode
  - [ ] Record analysis output on success

### Phase 3 — Monitor Hook Protocol

- [ ] Define `NodeMonitor` Protocol in `tinycua/config/types.py` <!-- id: 9 -->
  - [ ] Add `@runtime_checkable` decorator
  - [ ] Add `on_before_node_call()` method signature
  - [ ] Add `on_after_node_call()` method signature
  - [ ] Add `on_retry_exhausted()` method signature
- [ ] Define `AgentMonitor` Protocol in `tinycua/config/types.py` <!-- id: 10 -->
  - [ ] Same method signatures as `NodeMonitor`
  - [ ] Documentation notes delegation to `NodeMonitor`
- [ ] Add `monitor: NodeMonitor | None = None` field to `NodeConfigBase` <!-- id: 11 -->

### Phase 4 — Monitor Hook Integration

- [ ] Implement `_safe_call(hook_method, *args, **kwargs)` helper <!-- id: 12 -->
  - [ ] Wrap call in try/except
  - [ ] Log exceptions at debug level
  - [ ] Return None on exception
- [ ] Wire monitor hooks into `ProcessNode.__call__()` and `DecisionNode.__call__()` <!-- id: 13 -->
  - [ ] Call `monitor.on_before_node_call()` before each LLM call
  - [ ] Call `monitor.on_after_node_call()` after each validation failure
  - [ ] Call `monitor.on_retry_exhausted()` before exhaustion handling
  - [ ] Incorporate monitor continuations (if hook returns string, append to messages)
- [ ] Add `agent_monitor: AgentMonitor | None = None` parameter to `TinyCUALoop.__init__()` signature and store as `self.agent_monitor` <!-- id: 14 -->
- [ ] Wire `agent_monitor` in `TinyCUALoop._execute_node()` <!-- id: 15 -->
  - [ ] Call `agent_monitor.on_before_node_call()` before LLM call
  - [ ] Call `agent_monitor.on_after_node_call()` after response
  - [ ] Do NOT call `node.monitor` directly — all monitor calls go through `agent_monitor`

### Phase 5 — Streaming and Transcript Events

- [ ] Create `StreamEvent` and `LifecycleEvent` models in `tinycua/models/stream_event.py` <!-- id: 16 -->
  - [ ] Define `StreamEvent` dataclass with type, node_id, node_type, timestamp, metadata fields
  - [ ] Define `LifecycleEvent` dataclass extending StreamEvent with attempt, content, finish_reason
  - [ ] Implement `make_lifecycle_event()` factory function
  - [ ] Implement `enrich_stream_event()` helper function
  - [ ] Export new models from `tinycua/models/__init__.py`
- [ ] Add `TranscriptRecord` type to `tinycua/config/types.py` <!-- id: 17 -->
  - [ ] Define `TranscriptRecord` dataclass with event, run_id, session_id, sequence fields
- [ ] Modify `TinyCUALoop._run_stream()` to emit lifecycle events <!-- id: 18 -->
  - [ ] Emit `node.started` event before `agent._call_llm()` call
  - [ ] Emit `node.completed` event after LLM call completes successfully
  - [ ] Emit `node.error` event on exception during node execution
  - [ ] Add `attempt` tracking for retry scenarios
- [ ] Apply `NodeStreamPolicy.final_response_only` filtering <!-- id: 19 -->
  - [ ] Suppress intermediate node LLM/tool events when policy enabled
  - [ ] Only emit events from ResponseNode when final_response_only=True
- [ ] Apply `NodeStreamPolicy.include_node_metadata` enrichment <!-- id: 20 -->
  - [ ] Enrich events with node_id, node_type, attempt when policy enabled
  - [ ] Skip metadata enrichment when policy disabled
- [ ] Apply `NodeStreamPolicy.emit_internal_events` control <!-- id: 21 -->
  - [ ] Emit lifecycle events only when emit_internal_events=True
  - [ ] Suppress lifecycle events when emit_internal_events=False

## Testing Phase

> **Note**: Unit tests below are listed here for tracking, but should be written alongside their corresponding implementation tasks (TDD-style) — not after all implementation is complete.

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 22 -->
- [ ] Write unit tests for `validate_output()` with custom `validation_fn` in `tests/unit/test_retry_validation.py` <!-- id: 23 -->
  - [ ] Test valid validation result (is_valid=True)
  - [ ] Test invalid validation result (is_valid=False, errors merged)
  - [ ] Test `validation_fn` raising exception
  - [ ] Test `validation_fn` returning None (treated as pass)
- [ ] Write unit tests for `_build_retry_text()` with custom builder in `tests/unit/test_retry_validation.py` <!-- id: 24 -->
  - [ ] Test default builder produces standard message
  - [ ] Test custom builder produces custom message
  - [ ] Test custom builder returning empty string (fallback to default)
- [ ] Write unit tests for `_handle_exhaustion()` in `tests/unit/test_retry_validation.py` <!-- id: 25 -->
  - [ ] Test `raise` raises `NodeExecutionError`
  - [ ] Test `record_failure` writes to session
  - [ ] Test `route_failure` calls failure route
  - [ ] Test `route_failure` fallback to `record_failure` when no route
- [ ] Write unit tests for `DecisionNode` classification retry in `tests/unit/test_decision_node_retry.py` <!-- id: 26 -->
  - [ ] Test valid label accepted on first attempt
  - [ ] Test invalid label triggers retry
  - [ ] Test exhaustion raises error or records failure
- [ ] Write unit tests for `NodeMonitor` hook in `tests/unit/test_monitor_hook.py` <!-- id: 27 -->
  - [ ] Test hook called at correct trigger points
  - [ ] Test hook called with correct arguments
  - [ ] Test hook exception caught and logged
  - [ ] Test hook continuation message enters retry flow
- [ ] Write unit tests for independent `AgentMonitor` and `NodeMonitor` hook behavior in `tests/unit/test_monitor_hook.py` <!-- id: 28 -->
  - [ ] Test `AgentMonitor` fires when configured (loop-level)
  - [ ] Test `NodeMonitor` fires when configured (node-level)
  - [ ] Test both fire independently when both configured
- [ ] Write unit tests for `StreamEvent` model creation and validation <!-- id: 29 -->
  - [ ] Test StreamEvent fields are set correctly
  - [ ] Test LifecycleEvent inherits from StreamEvent correctly
  - [ ] Test make_lifecycle_event() creates valid events
  - [ ] Test enrich_stream_event() adds metadata correctly
- [ ] Write unit tests for `NodeStreamPolicy` enforcement <!-- id: 30 -->
  - [ ] Test final_response_only suppresses intermediate events
  - [ ] Test include_node_metadata adds metadata to events
  - [ ] Test emit_internal_events controls lifecycle emission
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 31 -->

## Verification Phase

- [ ] Verify monitor hooks do not write to `chat_history` or `session_context` <!-- id: 32 -->
- [ ] Verify `record_failure` propagation works with configured `PropagationRule.failure` <!-- id: 33 -->
- [ ] Verify `max_attempts=0` results in 1 attempt with immediate exhaustion <!-- id: 34 -->
- [ ] Verify stream=False returns string (backward compatibility) <!-- id: 35 -->
- [ ] Verify stream=True returns async iterator with correct event structure <!-- id: 36 -->
- [ ] Verify lifecycle events appear at correct node boundaries <!-- id: 37 -->
- [ ] Verify JSONL serialization roundtrip preserves all event data <!-- id: 38 -->

## Documentation Phase

- [ ] Update status tracker in `spec.md` — mark completed items <!-- id: 39 -->
- [ ] Update `design.md` implementation phases — mark completed phases <!-- id: 40 -->
- [ ] Update docstrings for modified `_run_stream()` method <!-- id: 41 -->
- [ ] Add module docstring for `stream_event.py` <!-- id: 42 -->

## Review and Merge

- [ ] Create pull request <!-- id: 43 -->
- [ ] Address review feedback <!-- id: 44 -->
- [ ] Merge to main branch <!-- id: 45 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-13*
