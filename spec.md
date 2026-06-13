# Feature Specification: Retry, Validation, Monitor Hook, and Streaming Events

**Status**: Draft
**Created**: 2026-06-13
**Last Updated**: 2026-06-13
**Subproject(s) Affected**: tinycua (src/tinycua)
**Milestone**: 4.3 — Retry, Validation, and Monitor Hook; 4.4 — Streaming and Transcript Events
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

> **Path convention**: All paths in this document (e.g., `docs/design/loops/node.md`, `config/node_config.py`) are relative to the `tinycua` subproject root (`src/tinycua/`). For example, `docs/design/loops/node.md` maps to `src/tinycua/docs/design/loops/node.md`.

---

## Problem Statement _(mandatory)_

### Milestone 4.3 — Retry, Validation, and Monitor Hook

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

### Milestone 4.4 — Streaming and Transcript Events

- **Goals**: Provide streaming support across all TinyCUA nodes and lifecycle event hooks that record enough data for WildClawBench transcript export, so callers can observe real-time execution progress and debug agent behavior.
- **Gaps**: Today, `TinyCUALoop` has basic streaming in `_run_stream()` that yields raw LLM events, but lacks: (1) structured lifecycle event models for node start/end/error, (2) node metadata enrichment in stream events, (3) configurable event emission via `NodeStreamPolicy`, and (4) a transcript-ready event format that WildClawBench can consume.
- **Non-Goals**: Production-grade CLI/TUI streaming UX, HITL interrupt/resume, real-time WebSocket transport, or modifying the SDK `BaseLoop` contract.
- **Constraints**: Must preserve SDK `BaseLoop` contract (`stream=True` returns async iterator of event dicts, `stream=False` returns final string). Must not require SDK API changes. Must work with local model endpoints.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario — Retry, Validation, and Monitor Hook

A TinyCUA node executes an LLM call that produces invalid output (missing required tool call, output does not match schema, or custom validation fails). The node retries with an assistant-role continuation message containing the validation error. If retries are exhausted, the node handles the failure according to its `on_retry_exhausted` policy (`raise`, `record_failure`, or `route_failure`). An optional monitor hook observes each lifecycle trigger point (before LLM call, after result, after retry exhaustion) and can return an assistant-role continuation or no-op.

### Acceptance Scenarios — Retry, Validation, and Monitor Hook

1. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=3, required_tool_calls=["task_update"])`, **When** the LLM call returns a response without the `task_update` tool call, **Then** the node retries up to 3 times, appending an assistant-role retry continuation with the validation error after each failed attempt.

2. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=2)` and a custom `validation_fn` that rejects responses containing "I don't know", **When** the LLM returns "I don't know", **Then** the node retries once more with an assistant-role continuation, and if the second attempt also fails, handles exhaustion per policy.

3. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=2, on_retry_exhausted="raise")`, **When** retry is exhausted, **Then** a `NodeExecutionError` is raised.

4. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=2, on_retry_exhausted="record_failure")`, **When** retry is exhausted, **Then** failure state is written to the node session. If `PropagationRule.failure` is configured (not `"none"`), failure state is also propagated according to it; otherwise failure state is recorded but not propagated.

5. **Given** a `ProcessNode` with `NodeRetryPolicy(max_attempts=2, on_retry_exhausted="route_failure")`, **When** retry is exhausted and the node defines a failure route in `on_complete()`, **Then** the failure route is called; otherwise behavior falls back to `record_failure`.

6. **Given** a node with a configured `NodeMonitor` hook, **When** the node executes, **Then** the monitor is called: (a) before the LLM call with node id, session id, attempt number, resolved tools, and messages; (b) after the LLM result with the raw result and validation status; (c) after retry exhaustion with the final error.

7. **Given** a `NodeMonitor` hook that returns an assistant-role continuation message, **When** the node retries, **Then** the monitor's continuation is included in the retry message flow.

8. **Given** a `DecisionNode` (e.g., `QueryAnalystNode`) with `NodeRetryPolicy(max_attempts=2)`, **When** the classification call returns an invalid/unknown label, **Then** the node retries the classification step with an assistant-role continuation.

9. **Given** a node with `NodeRetryPolicy(max_attempts=3, required_output_schema=SomeSchema)`, **When** the LLM response content does not parse as valid JSON matching the schema, **Then** the node retries with an assistant-role continuation indicating the schema mismatch.

10. **Given** a node with `NodeRetryPolicy(max_attempts=0)` (no retries), **When** the first attempt fails validation, **Then** the exhaustion policy is applied immediately without retry.

### Primary Scenario — Streaming and Transcript Events

A benchmark harness (WildClawBench) runs a TinyCUA agent with `stream=True`. As the agent processes through nodes (QueryAnalyst → Worker → TaskExecutor → ResultReviewer → ResponseNode), the harness receives structured lifecycle events: node started, LLM call made, tool executed, node completed, and final response synthesized. These events are serialized to JSONL for post-run transcript analysis and grading.

### Acceptance Scenarios — Streaming and Transcript Events

1. **Given** `stream=False`, **When** `TinyCUALoop.run()` completes, **Then** the return value is a `str` containing the final response content.
2. **Given** `stream=True`, **When** `TinyCUALoop.run()` is called, **Then** the return value is an `AsyncIterator[dict]` yielding stream events.
3. **Given** `stream=True` and `NodeStreamPolicy.include_node_metadata=True`, **When** a node executes, **Then** stream events include `node_id`, `node_type`, and `attempt` metadata fields.
4. **Given** `stream=True` and `NodeStreamPolicy.emit_internal_events=True`, **When** a node lifecycle transition occurs, **Then** a lifecycle event is emitted (e.g., `node.started`, `node.completed`, `node.error`).
5. **Given** `stream=True` and `NodeStreamPolicy.final_response_only=True`, **When** an intermediate node executes, **Then** its LLM/tool events are suppressed from the user-visible stream.
6. **Given** a completed run, **When** transcript events are collected, **Then** they can be serialized to JSONL and contain enough data for WildClawBench transcript export.

### Edge Cases

- What happens when `max_attempts=0`? (Exactly 1 attempt, no retries — validation failure goes straight to exhaustion handling.)
- What happens when the monitor hook raises an exception? (Log the error and continue without the hook's continuation — monitor failures must not break node execution.)
- What happens when `retry_continuation_builder` returns an empty string? (Use a default generic retry message with error details and attempt count.)
- What happens when `validation_fn` returns `None`? (Treat as validation passed — no errors from custom validation.)
- What happens when a `DecisionNode` classification returns a label not in `classification_labels`? (Treat as invalid — retry with clarification.)
- What happens when `validation_fn` raises an unexpected exception? (Treat as validation failure — log the exception and retry with the error details.)
- What happens when `stream=True` but the LLM endpoint does not support streaming? Fallback to collecting full response then yielding a single `response.completed` event.
- How does the system handle stream cancellation? The async iterator should stop yielding and clean up resources.
- What is the behavior with empty/null node output during streaming? Emit a `node.completed` event with `content=""` and `finish_reason="empty"`.

---

## Requirements _(mandatory)_

### Functional Requirements

#### Retry, Validation, and Monitor Hook (Milestone 4.3)

- **FR-001**: `ProcessNode.__call__()` MUST invoke `validate_output(response)` after each LLM call and retry with an assistant-role continuation when validation fails.
- **FR-002**: Retry continuations MUST be assistant-role messages containing the validation error details and attempt count.
- **FR-003**: When `retry_policy.validation_fn` is set, it MUST be called during `validate_output()` and its errors merged into the `ValidationResult`.
- **FR-004**: When `retry_policy.retry_continuation_builder` is set, it MUST be used instead of the default `build_retry_continuation()` to produce the retry message.
- **FR-005**: On retry exhaustion with `on_retry_exhausted="raise"`, a `NodeExecutionError` MUST be raised.
- **FR-006**: On retry exhaustion with `on_retry_exhausted="record_failure"`, failure state MUST be written to the node session. If `PropagationRule.failure` is configured, failure state MUST also be propagated according to it; otherwise failure state is recorded but not propagated.
- **FR-007**: On retry exhaustion with `on_retry_exhausted="route_failure"`, the node's failure route from `on_complete()` MUST be called if defined; otherwise fall back to `record_failure` behavior.
- **FR-008**: `DecisionNode.__call__()` MUST validate the classification output (verify label is in `classification_labels`) and retry the classification step when invalid.
- **FR-009**: An optional `NodeMonitor` protocol/interface MUST be defined with trigger points: before LLM call, after LLM result, after retry exhaustion.
- **FR-010**: `NodeMonitor` hook invocations MUST be transient — not queue nodes, no sessions, not written to `chat_history` or `session_context`.
- **FR-011**: Monitor hook exceptions MUST be caught and logged without breaking node execution.
- **FR-012**: Monitor hooks MAY return an assistant-role continuation message that enters the retry message flow. **Deferred**: Continuation appending is not implemented; return values are discarded. Follow-up milestone.
- **FR-013**: `AgentMonitor` (optional) MUST provide a higher-level hook that wraps node-level monitor behavior for observability across the entire loop. **Known limitation**: `NodeMonitor` only fires when a node is called directly (`node(input)`), not through `TinyCUALoop._execute_node()`. `AgentMonitor` is the loop-level hook and fires in both paths. See Technical Decision #7 in design.md.
- **FR-014**: `NodeRetryPolicy.max_attempts=0` MUST result in exactly 1 attempt (no retries) — validation failure goes straight to exhaustion handling.

#### Streaming and Transcript Events (Milestone 4.4)

- **FR-015**: System MUST support `stream=True` across all node executions, returning an async iterator of event dicts.
- **FR-016**: System MUST support `stream=False` returning a final string response (non-streamed final string behavior).
- **FR-017**: System MUST emit lifecycle events at node boundaries: `node.started`, `node.llm_call`, `node.completed`, `node.error`, `node.retry`.
- **FR-018**: Stream events MUST include node metadata (`node_id`, `node_type`, `attempt`) when `NodeStreamPolicy.include_node_metadata=True`.
- **FR-019**: System MUST suppress intermediate node LLM/tool events when `NodeStreamPolicy.final_response_only=True`, emitting only ResponseNode events.
- **FR-020**: System MUST emit internal lifecycle events when `NodeStreamPolicy.emit_internal_events=True`.
- **FR-021**: Transcript events MUST be serializable to JSONL format for WildClawBench compatibility.
- **FR-022**: System MUST preserve the SDK `BaseLoop` contract: `stream=True` yields event dicts, `stream=False` returns string.

### Key Entities _(include if feature involves data)_

- **NodeRetryPolicy**: Configuration dataclass controlling retry behavior, validation, and exhaustion. Already exists in `config/node_config.py`.
- **ValidationResult**: Dataclass with `is_valid: bool` and `errors: list[str]`. Already exists in `config/types.py`.
- **ValidationError**: Exception type for validation failures. Already exists in `config/types.py`.
- **NodeExecutionError**: Exception for node execution failures. Already exists in `loops/node.py`.
- **NodeMonitor** (NEW): Protocol/interface for transient node lifecycle observation.
- **AgentMonitor** (NEW): Protocol/interface for loop-level lifecycle observation.
- **StreamEvent**: A structured event dict yielded during streaming, containing event type, node metadata, content delta, and timestamp.
- **LifecycleEvent**: A subclass of StreamEvent for node lifecycle transitions (started, completed, error, retry).
- **TranscriptRecord**: A serializable event record containing all data needed for WildClawBench transcript export.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

> **Note**: Items below are checked off as implementation progresses. All items must
> be checked before merge.

> **Deferred to Implementation**: The items below cannot be verified until the
> corresponding code is written. They are intentionally left unchecked at the
> spec/design review stage and will be checked off during implementation.

### Retry, Validation, and Monitor Hook (Milestone 4.3)

- [x] **Retry loop works**: Invalid node output triggers retry with assistant-role continuation messages up to `max_attempts`.
- [x] **Custom validation works**: `validation_fn` is called during `validate_output()` and its errors are merged into the result.
- [x] **Custom continuation builder works**: `retry_continuation_builder` produces the retry message when set.
- [x] **Exhaustion handling works**: `raise` raises `NodeExecutionError`, `record_failure` writes failure state and propagates, `route_failure` calls the failure route or falls back.
- [x] **DecisionNode classification retry works**: Invalid classification labels trigger retry with assistant-role continuation.
- [x] **Monitor hook protocol defined**: `NodeMonitor` protocol/interface exists with before/after/exhaustion trigger points.
- [x] **Monitor hook is transient**: Hook invocations do not create sessions or write to chat_history/session_context.
- [x] **Monitor hook exceptions are caught**: Hook failures are logged and do not break node execution.
- [x] **Monitor continuations enter retry flow**: Hook-returned continuations are included in retry messages.
- [x] **Tests pass**: Unit tests for retry loop, validation, exhaustion, DecisionNode retry, and monitor hook behavior.

### Streaming and Transcript Events (Milestone 4.4)

- [ ] **stream=False returns string**: `TinyCUALoop.run(stream=False)` returns a `str` with the final response.
- [ ] **stream=True returns async iterator**: `TinyCUALoop.run(stream=True)` returns an `AsyncIterator[dict]`.
- [ ] **Lifecycle events emitted**: Node lifecycle transitions emit structured events with type, node_id, and timestamp.
- [ ] **Node metadata in events**: Stream events include `node_id`, `node_type`, `attempt` when policy enabled.
- [ ] **final_response_only suppresses intermediate events**: Intermediate node LLM/tool events are not emitted when policy enabled.
- [ ] **Transcript serialization**: Collected events can be serialized to JSONL and parsed back without data loss.
- [ ] **Backward compatibility**: Existing non-streaming tests continue to pass unchanged.

---

## Testing Plan _(mandatory)_

> **Deferred to Implementation**: The test items below cannot be written or verified
> until the corresponding code is implemented. They are intentionally left unchecked
> at the spec/design review stage and will be checked off during implementation.

### Unit Tests

#### Retry, Validation, and Monitor Hook (Milestone 4.3)

- [x] Test `ProcessNode` retry loop: valid output passes on first attempt, invalid output retries up to max_attempts.
- [x] Test `validate_output()` with `required_tool_calls` — missing tool triggers retry.
- [x] Test `validate_output()` with `required_output_schema` — invalid JSON triggers retry.
- [x] Test `validate_output()` with custom `validation_fn` — custom errors merged into result.
- [x] Test `build_retry_continuation()` with default builder and custom `retry_continuation_builder`.
- [x] Test exhaustion behavior: `raise` raises `NodeExecutionError`, `record_failure` writes failure state, `route_failure` calls failure route.
- [x] Test `max_attempts=0` — no retries, immediate exhaustion.
- [x] Test `DecisionNode` classification validation — invalid label triggers retry.
- [x] Test `NodeMonitor` hook called at correct trigger points with correct arguments.
- [x] Test `NodeMonitor` hook exception handling — logged and does not break execution.
- [x] Test `NodeMonitor` hook continuation message enters retry flow.

#### Streaming and Transcript Events (Milestone 4.4)

- Test `stream=False` returns string from `TinyCUALoop.run()`.
- Test `stream=True` returns async iterator yielding event dicts.
- Test lifecycle events are emitted at node boundaries.
- Test `NodeStreamPolicy.include_node_metadata` controls metadata inclusion.
- Test `NodeStreamPolicy.final_response_only` suppresses intermediate events.
- Test `NodeStreamPolicy.emit_internal_events` controls internal event emission.
- Test transcript events are JSON-serializable.
- Test stream cancellation stops event emission cleanly.

### Integration Tests

#### Retry, Validation, and Monitor Hook (Milestone 4.3)

> **Deferred to Implementation**: Integration tests require the full retry/validation/monitor
> pipeline to be wired before they can be executed. These items will be checked off
> once the implementation is complete and tests are run.

- [x] Test end-to-end retry through `TinyCUALoop._execute_node()` — node retries and eventually succeeds or exhausts.
- [x] Test monitor hook observing a full node execution cycle (before → after → exhaust if applicable).
- [x] Test `DecisionNode` retry through the loop — classification retried on invalid label.

#### Streaming and Transcript Events (Milestone 4.4)

- Test end-to-end streaming through a multi-node queue (QueryAnalyst → Worker → ResponseNode).
- Test transcript event collection produces valid JSONL output.
- Test streaming with real LLM mock that yields partial deltas.

### Manual Tests _(if applicable)_

- [ ] Verify that a node with retry configured can recover from transient LLM failures by retrying with context.
- Verify stream events visually in a test harness that prints events as they arrive.

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
| StreamEvent model | TODO | Structured event dict with type, node_id, timestamp |
| LifecycleEvent hooks | TODO | node.started, node.completed, node.error, node.retry |
| NodeStreamPolicy enforcement | TODO | Apply final_response_only, emit_internal_events |
| TranscriptRecord serialization | TODO | JSONL-compatible event records |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **Should `NodeMonitor` be a Protocol (structural typing) or an abstract base class?**
   - **Owner**: @VJyzCELERY
   - **Status**: RESOLVED — Use a Protocol for flexibility — allows any object with the right methods to serve as a monitor without inheritance. (Resolved in design.md Technical Decision #1)
   - **Proposed Answer**: Use a Protocol for flexibility — allows any object with the right methods to serve as a monitor without inheritance.

2. **Should `AgentMonitor` wrap `NodeMonitor` or be independent?**
   - **Owner**: @VJyzCELERY
   - **Status**: RESOLVED — `AgentMonitor` and `NodeMonitor` are independent hooks. The loop calls `AgentMonitor.on_*()` for loop-level observation; the node calls its own `NodeMonitor` via `self.config.monitor`. Both fire when configured — neither wraps or forwards to the other. (Resolved in design.md Technical Decision #6)
   - **Proposed Answer**: `AgentMonitor` and `NodeMonitor` are independent hooks. The loop calls `AgentMonitor.on_*()` for loop-level observation; the node calls its own `NodeMonitor` via `self.config.monitor`. Both fire when configured — neither wraps or forwards to the other.

3. **Event dict schema standardization**
   - **Owner**: @tinycua-team
   - **Target**: 2026-06-20
   - **Status**: Resolved
   - **Decision**: Follow OpenAI Responses API event format where possible (`type`, `delta`, `item`) for compatibility.

---

## Review Checklist

- [x] No implementation details beyond what the design docs specify
- [x] All mandatory sections completed
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
- [x] Exit criteria match Milestones 4.3 and 4.4 from the roadmap issue
