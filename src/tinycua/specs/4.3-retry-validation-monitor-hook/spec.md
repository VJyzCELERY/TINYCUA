# Feature Specification: Retry, Validation, and Monitor Hook

**Status**: Draft
**Created**: 2026-06-12
**Last Updated**: 2026-06-12
**Subproject(s) Affected**: tinycua (core)
**Milestone**: 4.3 — Retry, Validation, and Monitor Hook

---

## Problem Statement _(mandatory)_

- **Goals**: Provide node-level retry with output validation, required tool-call verification, and an optional transient monitor hook so nodes can self-correct invalid output and the loop can observe node lifecycle without durable side effects.
- **Gaps**: The current `NodeRetryPolicy` dataclass and `ProcessNode.__call__` retry loop exist as a basic skeleton, but the monitor hook (`NodeMonitor`/`AgentMonitor`) is not implemented. The retry continuation builder, `on_retry_exhausted` behaviors (`record_failure`, `route_failure`), and the three monitor trigger points (before LLM call, after result, after exhaustion) are not wired into the loop. There is no formal validation pipeline beyond the basic `validate_output()` stub.
- **Non-Goals**: HITL interrupt/resume UX, streaming/transcript events (Milestone 4.4), tool scoping (Milestone 4.2 — already done), propagation rules (Milestone 4.1 — already done). This milestone focuses exclusively on retry orchestration, output validation, and the transient monitor hook.
- **Constraints**: Must not modify tinycua-sdk public APIs. Must integrate with existing `NodeRetryPolicy`, `ValidationResult`, `ValidationError`, `ProcessNode.__call__`, and `TinyCUALoop._execute_node` without breaking them. Monitor hooks must be transient — they do not create sessions or write to chat_history/session_context.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

When a node's LLM output fails validation (missing required tool calls, schema mismatch, or custom validation failure), the retry loop appends an assistant-role continuation message with the error details and re-invokes the LLM. If retries are exhausted, the loop records failure state to the node session and propagates according to `on_retry_exhausted`. Optionally, a `NodeMonitor` hook is called at three trigger points to observe lifecycle events and optionally inject correction continuations.

### Acceptance Scenarios

1. **Given** a node with `required_tool_calls=["execute_task"]`, **When** the LLM response does not include that tool call, **Then** the validation fails and a retry continuation is appended.
2. **Given** a node with `required_output_schema=TaskResult`, **When** the LLM response content is not valid JSON matching the schema, **Then** the validation fails and a retry is triggered.
3. **Given** a node with `validation_fn` that returns `ValidationResult(is_valid=False, errors=["missing field"])`, **When** the custom validator runs, **Then** the retry loop treats it as a validation failure.
4. **Given** a node with `retry_continuation_builder`, **When** a retry is triggered, **Then** the custom builder produces the retry continuation message instead of the default.
5. **Given** a node with `on_retry_exhausted="raise"`, **When** all attempts fail, **Then** a `NodeExecutionError` is raised.
6. **Given** a node with `on_retry_exhausted="record_failure"`, **When** all attempts fail, **Then** failure state is written to the node session and propagation uses `PropagationRule.failure`.
7. **Given** a node with `on_retry_exhausted="route_failure"`, **When** all attempts fail, **Then** the node's failure route handler is called if defined, otherwise falls back to `record_failure`.
8. **Given** a `NodeMonitor` hook registered on the loop, **When** a node is about to make an LLM call, **Then** the monitor is invoked with node id, session id, attempt number, resolved tools, and messages.
9. **Given** a `NodeMonitor` hook, **When** a node receives an LLM result (before retry handling), **Then** the monitor is invoked with the raw result and validation error (if any).
10. **Given** a `NodeMonitor` hook, **When** retry is exhausted, **Then** the monitor is invoked before failure propagation with the final error.
11. **Given** a monitor hook that returns an assistant-role continuation message, **When** the loop receives it, **Then** the continuation enters the retry message flow.
12. **Given** a monitor hook that returns `None`, **When** the loop receives it, **Then** no additional message is injected (no-op).

### Edge Cases

- What happens when `max_attempts=0`? → No retries; validation failure is treated as exhaustion on the first attempt.
- What happens when `max_attempts=1`? → One LLM call; if it fails validation, exhaustion is triggered immediately.
- What happens when the monitor hook raises an exception? → The exception is caught and logged; the node continues its normal retry/exhaustion flow.
- What happens when both `required_tool_calls` and `required_output_schema` are set? → Both are checked; either failing triggers a retry.
- What happens when `validation_fn` returns `None`? → Validation is treated as passing (no-op).
- What happens when `retry_continuation_builder` is `None`? → The default `build_retry_continuation()` from `Node` is used.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST implement retry orchestration in `ProcessNode.__call__` that loops up to `NodeRetryPolicy.max_attempts` times, calling LLM and validating output on each attempt.
- **FR-002**: System MUST validate output on each attempt by checking `required_tool_calls`, `required_output_schema`, and `validation_fn` from `NodeRetryPolicy`.
- **FR-003**: System MUST append an assistant-role retry continuation message (from `build_retry_continuation()` or `retry_continuation_builder`) when validation fails and more attempts remain.
- **FR-004**: System MUST handle retry exhaustion according to `on_retry_exhausted`: `"raise"` raises `NodeExecutionError`, `"record_failure"` writes failure state to session and propagates, `"route_failure"` calls the node's failure route if defined.
- **FR-005**: System MUST support `NodeMonitor` as an optional transient hook with three trigger points: (1) before LLM call, (2) after LLM result before validation/retry handling, (3) after retry exhaustion before failure propagation.
- **FR-006**: System MUST pass node id, session id, attempt number, resolved tools, LLM-bound messages, raw result or validation error, and stream mode to monitor hook invocations.
- **FR-007**: System MUST allow monitor hooks to return an assistant-role continuation message that enters the retry message flow, or `None` for no-op.
- **FR-008**: System MUST NOT write monitor hook invocations to chat_history or session_context unless the owning node explicitly records a derived message.
- **FR-009**: System MUST catch monitor hook exceptions and log them without disrupting node execution.
- **FR-010**: System MUST use `retry_continuation_builder` when provided, falling back to `Node.build_retry_continuation()` when not.

### Key Entities _(include if feature involves data)_

- **NodeRetryPolicy**: Controls retry behavior — max_attempts, required_tool_calls, required_output_schema, validation_fn, retry_continuation_builder, on_retry_exhausted.
- **ValidationResult**: Output of validation — is_valid bool, errors list.
- **ValidationError**: Exception type carrying validation error details for retry continuations.
- **NodeMonitor**: Optional transient hook interface with `on_before_llm_call`, `on_after_llm_result`, `on_after_exhaustion` methods.
- **AgentMonitor**: Optional transient hook interface for loop-level observation (wraps NodeMonitor).

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Retry loop works**: ProcessNode.__call__ retries up to max_attempts when validation fails.
- [ ] **Required tool-call validation**: Missing required tool calls trigger retry.
- [ ] **Output schema validation**: Invalid JSON / schema mismatch triggers retry.
- [ ] **Custom validation**: validation_fn is called and its result respected.
- [ ] **Retry continuation messages**: Assistant-role continuation with error details is appended on retry.
- [ ] **Custom continuation builder**: retry_continuation_builder is used when provided.
- [ ] **Exhaustion: raise**: NodeExecutionError raised on exhaustion when on_retry_exhausted="raise".
- [ ] **Exhaustion: record_failure**: Failure state written to session and propagated on exhaustion.
- [ ] **Exhaustion: route_failure**: Failure route called if defined, otherwise falls back to record_failure.
- [ ] **Monitor hook: before LLM call**: Hook invoked with node id, session id, attempt, tools, messages.
- [ ] **Monitor hook: after LLM result**: Hook invoked with result and validation error (if any).
- [ ] **Monitor hook: after exhaustion**: Hook invoked before failure propagation.
- [ ] **Monitor hook continuation**: Returned continuation enters retry message flow.
- [ ] **Monitor hook no-op**: None return is a no-op.
- [ ] **Monitor hook exception safety**: Exceptions are caught and logged without disrupting execution.
- [ ] **Monitor hook transient**: Invocations are not written to chat_history/session_context.
- [ ] **Tests pass**: Unit and integration tests validate retry, validation, and monitor behavior.

---

## Traceability

| Scenario | Requirements Exercised |
|----------|----------------------|
| 1. Missing required tool call | FR-001, FR-002, FR-003 |
| 2. Invalid output schema | FR-001, FR-002, FR-003 |
| 3. Custom validation failure | FR-001, FR-002, FR-003 |
| 4. Custom continuation builder | FR-010, FR-003 |
| 5. Exhaustion: raise | FR-004 |
| 6. Exhaustion: record_failure | FR-004 |
| 7. Exhaustion: route_failure | FR-004 |
| 8. Monitor before LLM call | FR-005, FR-006 |
| 9. Monitor after LLM result | FR-005, FR-006 |
| 10. Monitor after exhaustion | FR-005, FR-006 |
| 11. Monitor continuation injection | FR-007 |
| 12. Monitor no-op | FR-007 |
| 13. Monitor exception safety | FR-009 |
| 14. Monitor transient (no side effects) | FR-008 |

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_retry_loop_max_attempts`: Retry loop iterates up to max_attempts.
- `test_retry_loop_stops_on_valid_output`: Loop stops when validation passes.
- `test_required_tool_calls_validation`: Missing required tool call triggers retry.
- `test_required_output_schema_validation`: Invalid JSON triggers retry.
- `test_custom_validation_fn`: Custom validator result is respected.
- `test_validation_fn_none_returns_valid`: None validation_fn is treated as valid.
- `test_retry_continuation_message`: Assistant-role continuation is appended on retry.
- `test_custom_retry_continuation_builder`: Custom builder is used when provided.
- `test_exhaustion_raise`: NodeExecutionError raised on exhaustion.
- `test_exhaustion_record_failure`: Failure state written to session on exhaustion.
- `test_exhaustion_route_failure`: Failure route called when defined.
- `test_exhaustion_route_failure_fallback`: Falls back to record_failure when no route.
- `test_exhaustion_with_max_attempts_zero`: First attempt treated as exhaustion.
- `test_monitor_before_llm_call`: Monitor invoked before LLM call with correct args.
- `test_monitor_after_llm_result`: Monitor invoked after LLM result.
- `test_monitor_after_exhaustion`: Monitor invoked after retry exhaustion.
- `test_monitor_continuation_injection`: Returned continuation enters retry flow.
- `test_monitor_noop_none`: None return is a no-op.
- `test_monitor_exception_safety`: Exception caught and logged, node continues.
- `test_monitor_not_recorded_to_session`: Monitor invocations not in chat_history/session_context.
- `test_node_retry_policy_creation`: NodeRetryPolicy instantiation with all fields.
- `test_node_retry_policy_max_attempts_validation`: Negative max_attempts raises ValueError.

### Integration Tests

- `test_retry_e2e_with_validation`: End-to-end: node fails validation → retry → eventually passes or exhausts.
- `test_retry_with_monitor_hook`: End-to-end: monitor observes all three trigger points during retry.
- `test_retry_exhaustion_record_failure_e2e`: End-to-end: exhaustion records failure and propagates.
- `test_retry_with_tinycua_loop`: TinyCUALoop._execute_node uses retry and monitor hooks.

### Manual Tests _(if applicable)_

- Run a minimal two-node queue with a node configured to fail validation on first attempt and verify retry continuation appears in session.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| NodeRetryPolicy dataclass | Exists | In node_config.py — needs review for completeness |
| ProcessNode retry loop | Exists | In node.py — needs monitor hook integration |
| validate_output() | Exists | In node.py — needs review for all validation paths |
| build_retry_continuation() | Exists | In node.py — needs review |
| NodeMonitor hook interface | TODO | New — needs creation |
| AgentMonitor hook interface | TODO | New — needs creation |
| Monitor trigger points in loop | TODO | New — needs wiring into TinyCUALoop |
| on_retry_exhausted: record_failure | Partial | Needs propagation integration |
| on_retry_exhausted: route_failure | TODO | Needs failure route handler |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **Should NodeMonitor be a protocol or an abstract base class?**
   - **Owner**: @VJyzCELERY
   - **Target**: TBD
   - **Status**: Proposed
   - **Proposed Answer**: Protocol — lighter weight, allows duck-typing and simple callable hooks.

2. **Should AgentMonitor be a separate interface or compose NodeMonitor?**
   - **Owner**: @VJyzCELERY
   - **Target**: TBD
   - **Status**: Proposed
   - **Proposed Answer**: Compose — AgentMonitor wraps NodeMonitor and adds loop-level observation.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
