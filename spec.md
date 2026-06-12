# Feature Specification: Retry, Validation, and Monitor Hook

**Status**: Draft
**Created**: 2026-06-13
**Last Updated**: 2026-06-13
**Subproject(s) Affected**: tinycua (src/tinycua)
**Milestone**: 4.3 — Retry, Validation, and Monitor Hook
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

> **Path convention**: All paths in this document (e.g., `docs/design/loops/node.md`, `config/node_config.py`) are relative to the `tinycua` subproject root (`src/tinycua/`). For example, `docs/design/loops/node.md` maps to `src/tinycua/docs/design/loops/node.md`.

---

## Problem Statement _(mandatory)_

- **Goals**: Complete the retry, validation, and monitor hook contracts so that invalid node output is retried with assistant-role continuations, validation errors are surfaced correctly, retry exhaustion is handled per policy, and an optional transient `NodeMonitor`/`AgentMonitor` hook provides observability into node lifecycle without creating durable queue nodes.
- **Gaps**: The `NodeRetryPolicy` dataclass, `validate_output()`, `build_retry_continuation()`, and basic retry loop exist in `ProcessNode.__call__()` (Milestone 1.5). However:
  - The retry loop in `ProcessNode.__call__()` does not call the monitor hook at lifecycle trigger points.
  - There is no `NodeMonitor` or `AgentMonitor` protocol/interface defined.
  - The retry exhaustion behavior for `record_failure` and `route_failure` is not fully wired — the loop continues with the last response but does not write failure state to the node session or propagate according to `PropagationRule.failure`.
  - `DecisionNode.__call__()` does not implement retry/validation at all — it performs a two-step analysis+classification flow without validating the classification output or retrying on invalid labels.
  - Custom `validation_fn` and `retry_continuation_builder` callables from `NodeRetryPolicy` are not invoked in the retry loop.
- **Non-Goals**:
  - Implementing HITL (human-in-the-loop) interrupt/resume UX.
  - Implementing streaming lifecycle events (covered in Milestone 4.4).
  - Modifying `tinycua-sdk` public APIs.
  - Implementing the full `AgentState` lifecycle output model (partially covered here for failure recording).
- **Constraints**:
  - Must not modify `tinycua-sdk` public APIs.
  - Retry prompts MUST be assistant-role continuations (per `docs/design/loops/node.md`).
  - Monitor hook invocations MUST be transient — not queue nodes, no sessions, not written to `chat_history` or `session_context` unless the owning node explicitly records a derived message.
  - Must honor existing `NodeRetryPolicy` fields: `max_attempts`, `required_tool_calls`, `required_output_schema`, `validation_fn`, `retry_continuation_builder`, `on_retry_exhausted`.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A TinyCUA node executes an LLM call that produces invalid output (missing required tool call, output does not match schema, or custom validation fails). The node retries with an assistant-role continuation message containing the validation error. If retries are exhausted, the node handles the failure according to its `on_retry_exhausted` policy (`raise`, `record_failure`, or `route_failure`). An optional monitor hook observes each lifecycle trigger point (before LLM call, after result, after retry exhaustion) and can return an assistant-role continuation or no-op.

### Acceptance Scenarios

1. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=3, required_tool_calls=["task_update"])`, **When** the LLM call returns a response without the `task_update` tool call, **Then** the node retries up to 3 times, appending an assistant-role retry continuation with the validation error after each failed attempt.

2. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=2)` and a custom `validation_fn` that rejects responses containing "I don't know", **When** the LLM returns "I don't know", **Then** the node retries once more with an assistant-role continuation, and if the second attempt also fails, handles exhaustion per policy.

3. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=2, on_retry_exhausted="raise")`, **When** retry is exhausted, **Then** a `NodeExecutionError` is raised.

4. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=2, on_retry_exhausted="record_failure")`, **When** retry is exhausted, **Then** failure state is written to the node session and propagation occurs according to `PropagationRule.failure`.

5. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=2, on_retry_exhausted="route_failure")`, **When** retry is exhausted and the node defines a failure route in `on_complete()`, **Then** the failure route is called; otherwise behavior falls back to `record_failure`.

6. **Given** a node with a configured `NodeMonitor` hook, **When** the node executes, **Then** the monitor is called: (a) before the LLM call with node id, session id, attempt number, resolved tools, and messages; (b) after the LLM result with the raw result and validation status; (c) after retry exhaustion with the final error.

7. **Given** a `NodeMonitor` hook that returns an assistant-role continuation message, **When** the node retries, **Then** the monitor's continuation is included in the retry message flow.

8. **Given** a `DecisionNode` (e.g., `QueryAnalystNode`) with `NodeRetryPolicy(max_attempts=2)`, **When** the classification call returns an invalid/unknown label, **Then** the node retries the classification step with an assistant-role continuation.

9. **Given** a node with `NodeRetryPolicy(max_attempts=3, required_output_schema=SomeSchema)`, **When** the LLM response content does not parse as valid JSON matching the schema, **Then** the node retries with an assistant-role continuation indicating the schema mismatch.

10. **Given** a node with `NodeRetryPolicy(max_attempts=1)` (no retries), **When** the first attempt fails validation, **Then** the exhaustion policy is applied immediately without retry.

### Edge Cases

- What happens when `max_attempts=0`? (No retries — validation failure goes straight to exhaustion handling.)
- What happens when the monitor hook raises an exception? (Log the error and continue without the hook's continuation — monitor failures must not break node execution.)
- What happens when `retry_continuation_builder` returns an empty string? (Use a default generic retry message.)
- What happens when `validation_fn` returns `None`? (Treat as validation passed — no errors from custom validation.)
- What happens when a `DecisionNode` classification returns a label not in `classification_labels`? (Treat as invalid — retry with clarification.)

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: `ProcessNode.__call__()` MUST invoke `validate_output(response)` after each LLM call and retry with an assistant-role continuation when validation fails.
- **FR-002**: Retry continuations MUST be assistant-role messages containing the validation error details and attempt count.
- **FR-003**: When `retry_policy.validation_fn` is set, it MUST be called during `validate_output()` and its errors merged into the `ValidationResult`.
- **FR-004**: When `retry_policy.retry_continuation_builder` is set, it MUST be used instead of the default `build_retry_continuation()` to produce the retry message.
- **FR-005**: On retry exhaustion with `on_retry_exhausted="raise"`, a `NodeExecutionError` MUST be raised.
- **FR-006**: On retry exhaustion with `on_retry_exhausted="record_failure"`, failure state MUST be written to the node session and propagated according to `PropagationRule.failure`.
- **FR-007**: On retry exhaustion with `on_retry_exhausted="route_failure"`, the node's failure route from `on_complete()` MUST be called if defined; otherwise fall back to `record_failure` behavior.
- **FR-008**: `DecisionNode.__call__()` MUST validate the classification output (verify label is in `classification_labels`) and retry the classification step when invalid.
- **FR-009**: An optional `NodeMonitor` protocol/interface MUST be defined with trigger points: before LLM call, after LLM result, after retry exhaustion.
- **FR-010**: `NodeMonitor` hook invocations MUST be transient — not queue nodes, no sessions, not written to `chat_history` or `session_context`.
- **FR-011**: Monitor hook exceptions MUST be caught and logged without breaking node execution.
- **FR-012**: Monitor hooks MAY return an assistant-role continuation message that enters the retry message flow.
- **FR-013**: `AgentMonitor` (optional) MUST provide a higher-level hook that wraps node-level monitor behavior for observability across the entire loop.
- **FR-014**: `NodeRetryPolicy.max_attempts=0` MUST result in no retries — validation failure goes straight to exhaustion handling.

### Key Entities

- **NodeRetryPolicy**: Configuration dataclass controlling retry behavior, validation, and exhaustion. Already exists in `config/node_config.py`.
- **ValidationResult**: Dataclass with `is_valid: bool` and `errors: list[str]`. Already exists in `config/types.py`.
- **ValidationError**: Exception type for validation failures. Already exists in `config/types.py`.
- **NodeExecutionError**: Exception for node execution failures. Already exists in `loops/node.py`.
- **NodeMonitor** (NEW): Protocol/interface for transient node lifecycle observation.
- **AgentMonitor** (NEW): Protocol/interface for loop-level lifecycle observation.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Retry loop works**: Invalid node output triggers retry with assistant-role continuation messages up to `max_attempts`.
- [ ] **Custom validation works**: `validation_fn` is called during `validate_output()` and its errors are merged into the result.
- [ ] **Custom continuation builder works**: `retry_continuation_builder` produces the retry message when set.
- [ ] **Exhaustion handling works**: `raise` raises `NodeExecutionError`, `record_failure` writes failure state and propagates, `route_failure` calls the failure route or falls back.
- [ ] **DecisionNode classification retry works**: Invalid classification labels trigger retry with assistant-role continuation.
- [ ] **Monitor hook protocol defined**: `NodeMonitor` protocol/interface exists with before/after/exhaustion trigger points.
- [ ] **Monitor hook is transient**: Hook invocations do not create sessions or write to chat_history/session_context.
- [ ] **Monitor hook exceptions are caught**: Hook failures are logged and do not break node execution.
- [ ] **Monitor continuations enter retry flow**: Hook-returned continuations are included in retry messages.
- [ ] **Tests pass**: Unit tests for retry loop, validation, exhaustion, DecisionNode retry, and monitor hook behavior.

---

## Testing Plan _(mandatory)_

### Unit Tests

- [ ] Test `ProcessNode` retry loop: valid output passes on first attempt, invalid output retries up to max_attempts.
- [ ] Test `validate_output()` with `required_tool_calls` — missing tool triggers retry.
- [ ] Test `validate_output()` with `required_output_schema` — invalid JSON triggers retry.
- [ ] Test `validate_output()` with custom `validation_fn` — custom errors merged into result.
- [ ] Test `build_retry_continuation()` with default builder and custom `retry_continuation_builder`.
- [ ] Test exhaustion behavior: `raise` raises `NodeExecutionError`, `record_failure` writes failure state, `route_failure` calls failure route.
- [ ] Test `max_attempts=0` — no retries, immediate exhaustion.
- [ ] Test `DecisionNode` classification validation — invalid label triggers retry.
- [ ] Test `NodeMonitor` hook called at correct trigger points with correct arguments.
- [ ] Test `NodeMonitor` hook exception handling — logged and does not break execution.
- [ ] Test `NodeMonitor` hook continuation message enters retry flow.

### Integration Tests

- [ ] Test end-to-end retry through `TinyCUALoop._execute_node()` — node retries and eventually succeeds or exhausts.
- [ ] Test monitor hook observing a full node execution cycle (before → after → exhaust if applicable).
- [ ] Test `DecisionNode` retry through the loop — classification retried on invalid label.

### Manual Tests _(if applicable)_

- [ ] Verify that a node with retry configured can recover from transient LLM failures by retrying with context.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| NodeRetryPolicy dataclass | Done | Milestone 1.2 |
| validate_output() basic implementation | Done | Milestone 1.5 |
| build_retry_continuation() basic implementation | Done | Milestone 1.5 |
| ProcessNode retry loop | Done | Milestone 1.5 (basic) |
| Custom validation_fn invocation | TODO | Wire into validate_output() |
| Custom retry_continuation_builder invocation | TODO | Wire into retry loop |
| record_failure exhaustion behavior | TODO | Write failure state + propagate |
| route_failure exhaustion behavior | TODO | Call on_complete failure route |
| DecisionNode classification validation | TODO | Validate label in classification_labels |
| NodeMonitor protocol/interface | TODO | Define trigger points and args |
| AgentMonitor protocol/interface | TODO | Loop-level observation |
| Monitor hook integration in retry loop | TODO | Call hooks at lifecycle points |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **Should `NodeMonitor` be a Protocol (structural typing) or an abstract base class?**
   - **Owner**: @VJyzCELERY
   - **Status**: Discussion
   - **Proposed Answer**: Use a Protocol for flexibility — allows any object with the right methods to serve as a monitor without inheritance.

2. **Should `AgentMonitor` wrap `NodeMonitor` or be independent?**
   - **Owner**: @VJyzCELERY
   - **Status**: Discussion
   - **Proposed Answer**: `AgentMonitor` wraps `NodeMonitor` — the loop calls `AgentMonitor.on_node_*()` which delegates to the configured `NodeMonitor` if present.

---

## Review Checklist

- [ ] No implementation details beyond what the design docs specify
- [ ] All mandatory sections completed
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
- [ ] Exit criteria match Milestone 4.3 from the roadmap issue
