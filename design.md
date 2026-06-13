# Design Document: Retry, Validation, Monitor Hook, and Streaming Events

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-13

---

## Overview

This design covers two related milestones:

1. **Milestone 4.3 — Retry, Validation, and Monitor Hook**: Completes the retry, validation, and monitor hook contracts for TinyCUA nodes. The `NodeRetryPolicy` dataclass and basic retry loop exist (Milestone 1.5), but custom validation functions, custom continuation builders, full exhaustion handling, DecisionNode classification validation, and the transient `NodeMonitor`/`AgentMonitor` hook are not yet wired. This design fills those gaps.

2. **Milestone 4.4 — Streaming and Transcript Events**: Adds structured streaming support and lifecycle event hooks to TinyCUALoop, enabling real-time execution observation and WildClawBench-compatible transcript export. The implementation extends the existing `_run_stream()` method with lifecycle event emission, introduces a `StreamEvent` model for structured event dicts, and applies `NodeStreamPolicy` controls to filter events per node configuration.

---

## Architecture

### Component Overview

```
TinyCUALoop._execute_node(node, agent, tools, ...)
  │
  ├── node.ensure_session(root_session)
  ├── messages = _build_node_messages(node, ...)
  ├── resolved_tools = node.config.tool_policy.resolve_tools(tools)
  │
  ├── AgentMonitor.on_before_node_call(node, messages, tools, attempt)
  │
  ├── response = agent._call_llm(messages, resolved_tools)
  │
  ├── validation = node.validate_output(response)
  │     ├── check required_tool_calls
  │     ├── check required_output_schema
  │     └── call validation_fn (if set)
  │
  ├── if valid → break
  │
  ├── AgentMonitor.on_after_node_call(node, response, validation_result)
  │
  ├── if invalid:
  │     ├── build retry continuation (custom or default)
  │     ├── append continuation to messages
  │     └── loop back to LLM call
  │
  ├── if exhausted:
  │     ├── AgentMonitor.on_retry_exhausted(node, error)
  │     └── handle per on_retry_exhausted policy
  │           ├── raise → NodeExecutionError
  │           ├── record_failure → write failure state + propagate
  │           └── route_failure → call on_complete failure route
  │
  ├── node.record_output(response)
  ├── node.propagate()
  └── node.on_complete(queue, response)

TinyCUALoop.run(stream=True)
  → _run_stream()
      → for each node:
          → emit node.started lifecycle event
          → emit node.llm_call lifecycle event (before _call_llm)
          → agent._call_llm(stream=True)
              → yield LLM delta events (with node metadata enrichment)
          → emit node.completed lifecycle event
      → yield all events through AsyncIterator

StreamEvent (model)
  ← LifecycleEvent (node boundaries)

LLM/tool events are plain dicts with `type` field discrimination
  (e.g., `response.output_text.delta`, `response.function_call`)

NodeStreamPolicy
  → controls: final_response_only, emit_internal_events, include_node_metadata
```

### Affected Components

> **Path convention**: All paths are relative to `src/tinycua/tinycua/`.

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/config/types.py` | Modified | Add `NodeMonitor` and `AgentMonitor` protocols, `TranscriptRecord` type |
| `tinycua/loops/node.py` | Modified | Wire `validation_fn`, `retry_continuation_builder`, exhaustion behavior; add monitor hook calls |
| `tinycua/loops/tinycua_loop.py` | Modified | Accept optional `AgentMonitor`, pass to node execution; lifecycle event emission in `_run_stream()` |
| `tinycua/models/stream_event.py` | New | StreamEvent, LifecycleEvent models |
| `tinycua/config/node_config.py` | No change | NodeStreamPolicy already exists |
| `tests/unit/test_retry_validation.py` | New | Unit tests for retry, validation, exhaustion, monitor hook |
| `tests/unit/test_decision_node_retry.py` | New | Unit tests for DecisionNode classification retry |
| `tests/unit/test_monitor_hook.py` | New | Unit tests for monitor hook behavior |
| `tests/integration/test_retry_integration.py` | New | Integration tests for retry through the loop |

---

## Data Model

### NodeMonitor Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class NodeMonitor(Protocol):
    """Transient hook for node lifecycle observation.

    All methods are optional — implement only what you need.
    Monitor invocations are transient: they do not create sessions,
    do not write to chat_history or session_context.
    """

    def on_before_node_call(
        self,
        node_id: str,
        session_id: str,
        attempt: int,
        messages: list[dict],
        resolved_tools: list,
    ) -> str | None:
        """Called before a node LLM call.

        Args:
            node_id: The node being executed.
            session_id: The node's session ID.
            attempt: Current attempt number (1-indexed).
            messages: LLM-bound messages.
            resolved_tools: Tools available for this call. At the node level
                this is always an empty list (``[]``); actual resolved tools
                are passed to ``AgentMonitor.on_before_node_call`` at the
                loop level.

        Returns:
            Optional assistant-role continuation message to include
            in the retry flow, or None for no-op.
        """
        ...

    def on_after_node_call(
        self,
        node_id: str,
        session_id: str,
        attempt: int,
        result: "LLMResult",
        validation_result: "ValidationResult",
    ) -> str | None:
        """Called after a node LLM call, before retry handling.

        Args:
            node_id: The node that was executed.
            session_id: The node's session ID.
            attempt: Current attempt number (1-indexed).
            result: The raw LLM result.
            validation_result: Validation outcome.

        Returns:
            Optional assistant-role continuation message, or None.
        """
        ...

    def on_retry_exhausted(
        self,
        node_id: str,
        session_id: str,
        error: "ValidationError",
        attempts: int,
    ) -> str | None:
        """Called after retry exhaustion, before failure handling.

        Args:
            node_id: The node that exhausted retries.
            session_id: The node's session ID.
            error: The final validation error.
            attempts: Total attempts made.

        Returns:
            Optional assistant-role continuation message, or None.
        """
        ...
```

### AgentMonitor Protocol

```python
@runtime_checkable
class AgentMonitor(Protocol):
    """Loop-level observation hook for all node executions.

    Independent from NodeMonitor: the loop calls AgentMonitor hooks,
    and nodes call their own NodeMonitor hooks. Both fire when
    configured — neither wraps or forwards to the other.
    """

    def on_before_node_call(
        self,
        node_id: str,
        session_id: str,
        attempt: int,
        messages: list[dict],
        resolved_tools: list,
    ) -> str | None:
        ...

    def on_after_node_call(
        self,
        node_id: str,
        session_id: str,
        attempt: int,
        result: "LLMResult",
        validation_result: "ValidationResult",
    ) -> str | None:
        ...

    def on_retry_exhausted(
        self,
        node_id: str,
        session_id: str,
        error: "ValidationError",
        attempts: int,
    ) -> str | None:
        ...
```

### Failure State Recording

When `on_retry_exhausted="record_failure"`, the node writes failure state to its session:

```python
# In ProcessNode.__call__(), after retry exhaustion:
from tinycua.models.session_context_entry import SessionContextEntry

failure_entry = SessionContextEntry(
    content=f"[RETRY_EXHAUSTED] Node {self.node_id} failed after {max_attempts} attempts. "
            f"Errors: {'; '.join(validation.errors)}",
    segment="output",
)
self.session.session_context.append(failure_entry)

# Propagate failure if a propagation rule is configured
if self.config.propagation and self.config.propagation.failure != "none":
    self.propagate()
```

### New Entities (Streaming)

```python
# StreamEvent — base event dict yielded during streaming
StreamEvent:
    type: str                    # "node.started", "node.completed", "response.output_text.delta", etc.
    node_id: str | None          # ID of the node producing this event
    node_type: str | None        # "ProcessNode", "DecisionNode", etc.
    timestamp: float             # time.time() when event was created
    metadata: dict               # additional context (attempt, route_label, etc.)

# LifecycleEvent — node boundary events
LifecycleEvent(StreamEvent):
    type: Literal["node.started", "node.llm_call", "node.completed", "node.error", "node.retry"]
    attempt: int                 # current attempt number (1-based)
    content: str | None          # final content for completed/error events
    finish_reason: str | None    # "completed", "error", "retry", "empty"

# TranscriptRecord — serializable event for WildClawBench export
TranscriptRecord:
    event: StreamEvent           # the original event
    run_id: str                  # unique run identifier
    session_id: str              # root session ID
    sequence: int                # monotonically increasing sequence number
```

### Schema Changes

- No changes to existing data structures. `NodeStreamPolicy` already has the required fields.
- New `StreamEvent` and `LifecycleEvent` models are additive.

---

## API / Interface Contracts

### Enhanced ProcessNode.__call__()

> **Note**: Monitor hooks are invoked independently by two sites: the
> loop calls `AgentMonitor.on_*()` for loop-level observation, and the
> node calls its own `NodeMonitor` via `self.config.monitor`. Both fire
> when configured. See Technical Decision #6.
>
> **Deferred**: Continuation return values from monitor hooks are not
> currently appended to the retry message flow. The return values from
> `on_before_node_call` and `on_after_node_call` are discarded. This
> feature is deferred to a follow-up milestone. Use NodeMonitor hooks
> for logging/observation only.

```python
class ProcessNode(Node):
    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute with retry, validation, and monitor hooks."""
        messages = self.build_messages(self.session, input)
        retry_policy = self.config.retry_policy
        max_attempts = max(retry_policy.max_attempts, 1)  # 0 → 1 attempt (no retry)

        last_response = None
        for attempt in range(1, max_attempts + 1):
            # Fire NodeMonitor before-hook
            if self.config.monitor is not None:
                self._safe_call(
                    self.config.monitor.on_before_node_call,
                    self.node_id,
                    self.session.session_id,
                    attempt,
                    messages,
                    [],
                )

            last_response = self._call_llm(messages)

            # Validate
            validation = self.validate_output(last_response)

            if validation.is_valid:
                break

            # Fire NodeMonitor after-hook (validation failed)
            if self.config.monitor is not None:
                self._safe_call(
                    self.config.monitor.on_after_node_call,
                    self.node_id,
                    self.session.session_id,
                    attempt,
                    last_response,
                    validation,
                )

            if attempt < max_attempts:
                # Build retry continuation
                error = ValidationError("; ".join(validation.errors))
                retry_text = self._build_retry_text(error, attempt)
                messages.append({"role": "assistant", "content": retry_text})
            else:
                # Exhausted — handle per policy
                self._handle_exhaustion(validation, max_attempts)

        self.record_output(last_response)
        self.propagate()
        self.on_complete(queue=..., response=last_response)
        return last_response

    def _build_retry_text(self, error: ValidationError, attempt: int) -> str:
        """Build retry text using custom builder if set, else default."""
        if self.config.retry_policy.retry_continuation_builder is not None:
            return self.config.retry_policy.retry_continuation_builder(error, attempt)
        return self.build_retry_continuation(error, attempt)

    def _handle_exhaustion(self, validation, max_attempts):
        """Handle retry exhaustion per policy."""
        # Fire monitor exhaustion hook
        if self.config.monitor is not None:
            self._safe_call(
                self.config.monitor.on_retry_exhausted,
                self.node_id,
                self.session.session_id,
                ValidationError("; ".join(validation.errors)),
                max_attempts,
            )

        if self.config.retry_policy.on_retry_exhausted == "raise":
            raise NodeExecutionError(...)
        elif self.config.retry_policy.on_retry_exhausted == "record_failure":
            self._record_failure(validation, max_attempts)
        elif self.config.retry_policy.on_retry_exhausted == "route_failure":
            if not self._call_failure_route():
                self._record_failure(validation, max_attempts)

    def _record_failure(self, validation, max_attempts):
        """Write failure state to session."""
        ...

    def _call_failure_route(self) -> bool:
        """Call on_complete failure route if defined. Returns True if called."""
        ...
```

> **Loop-level AgentMonitor**: The `TinyCUALoop._execute_node()` method
> independently calls `AgentMonitor` hooks at loop-level lifecycle points:
> ```python
> # In TinyCUALoop._execute_node():
> if self.agent_monitor is not None:
>     self.agent_monitor.on_before_node_call(node.node_id, ...)
> # Then node executes — NodeMonitor fires within node.__call__()
> if self.agent_monitor is not None:
>     self.agent_monitor.on_after_node_call(node.node_id, ...)
> ```
> AgentMonitor and NodeMonitor are independent hooks — both fire when configured.

### Enhanced DecisionNode.__call__()

> **Note**: The code examples below show the loop orchestrating monitor calls through
> `AgentMonitor` and `NodeMonitor` are independent hooks — the loop calls
> `AgentMonitor` at lifecycle points; the node calls its own `NodeMonitor`
> via `self.config.monitor`. Both fire when configured. See
> Technical Decision #6.

```python
class DecisionNode(ProcessNode):
    def __call__(self, input: NodeInputLike) -> DecisionResult:
        """Execute with classification validation and retry."""
        messages = self.build_messages(self.session, input)

        # Step 1: Analysis call (no retry on analysis — retry on classification)
        analysis_response = self._analysis_call(messages)

        # Step 2: Classification with retry
        retry_policy = self.config.retry_policy
        max_attempts = max(retry_policy.max_attempts, 1)

        classification_response = None
        for attempt in range(1, max_attempts + 1):
            # Fire NodeMonitor before-hook
            if self.config.monitor is not None:
                self._safe_call(
                    self.config.monitor.on_before_node_call,
                    self.node_id,
                    self.session.session_id,
                    attempt,
                    messages,
                    [],
                )

            classification_response = self._classification_call(messages, analysis_response)

            # Validate classification label
            label = classification_response.content.strip().lower()
            if any(l.lower() in label for l in self.classification_labels):
                break

            # Fire NodeMonitor after-hook (validation failed)
            if self.config.monitor is not None:
                self._safe_call(
                    self.config.monitor.on_after_node_call,
                    self.node_id,
                    self.session.session_id,
                    attempt,
                    classification_response,
                    ValidationResult(is_valid=False, errors=[f"Invalid classification: {label}"]),
                )

            if attempt < max_attempts:
                error = ValidationError(f"Invalid classification: {label}")
                retry_text = self._build_retry_text(error, attempt)
                messages.append({"role": "assistant", "content": retry_text})
            else:
                # Retry exhausted — handled by NodeMonitor via _handle_exhaustion
                pass

        route_label = self._dispatch_route(classification_response)

        # ... rest of dispatch
```

### Safe Monitor Hook Caller

`_safe_call()` was implemented as a method on `Node` (not module-level) for cleaner access to `self.node_id` in debug logging. It accepts a callable and its arguments, calls it in a try/except, logs exceptions at debug level, and returns the result or None. This is a minor deviation from the original design that does not affect behavior.

```python
def _safe_call(hook_method, *args, **kwargs):
    """Call a monitor hook method, catching exceptions."""
    try:
        return hook_method(*args, **kwargs)
    except Exception:
        logger.debug("Monitor hook %s failed", hook_method.__name__, exc_info=True)
        return None
```

### New / Modified Endpoints (Streaming)

```python
# StreamEvent factory (convenience constructors)
def make_lifecycle_event(
    event_type: Literal["node.started", "node.llm_call", "node.completed", "node.error", "node.retry"],
    node_id: str,
    node_type: str,
    attempt: int = 1,
    content: str | None = None,
    finish_reason: str | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Create a lifecycle event dict with standard fields."""

def enrich_stream_event(
    event: dict[str, Any],
    node_id: str,
    node_type: str,
    include_metadata: bool = True,
) -> dict[str, Any]:
    """Add node metadata to an existing stream event dict."""
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Stream cancellation | StopIteration / AsyncIterator exit | Clean up and stop yielding |
| LLM endpoint no streaming support | Fallback to single response.completed event | Collect full response, yield once |
| Empty node output | node.completed with content="" | finish_reason="empty" |

---

## Implementation Phases

### Phase 1 — Validation and Retry Completion (required)

- [ ] Wire `validation_fn` into `validate_output()` — call custom fn and merge errors
- [ ] Wire `retry_continuation_builder` into retry loop — use custom builder when set
- [ ] Implement `record_failure` exhaustion — write failure state to session, propagate
- [ ] Implement `route_failure` exhaustion — call `on_complete()` failure route, fallback to `record_failure`
- [ ] Implement `max_attempts=0` — no retries, immediate exhaustion

### Phase 2 — DecisionNode Classification Retry (required)

- [ ] Add classification validation in `DecisionNode.__call__()` — verify label in `classification_labels`
- [ ] Add retry loop for classification step with assistant-role continuation
- [ ] Apply same exhaustion behavior as ProcessNode

### Phase 3 — Monitor Hook (required)

- [ ] Define `NodeMonitor` protocol in `tinycua/config/types.py`
- [ ] Define `AgentMonitor` protocol in `tinycua/config/types.py`
- [ ] Add `monitor: NodeMonitor | None` field to `NodeConfigBase`
- [ ] Add `agent_monitor: AgentMonitor | None` field to `TinyCUALoop`
- [ ] Wire monitor hook calls into `ProcessNode.__call__()` at lifecycle trigger points
- [ ] Implement `_safe_call()` for exception-safe monitor invocation
- [ ] Wire `AgentMonitor` into `TinyCUALoop._execute_node()` — delegate to node monitor

### Phase 4 — Streaming and Transcript Events (required)

- [ ] Create `StreamEvent` and `LifecycleEvent` models in `tinycua/models/stream_event.py`
- [ ] Add `make_lifecycle_event()` and `enrich_stream_event()` helper functions
- [ ] Modify `TinyCUALoop._run_stream()` to emit lifecycle events at node boundaries
- [ ] Apply `NodeStreamPolicy.final_response_only` to suppress intermediate events
- [ ] Apply `NodeStreamPolicy.include_node_metadata` to enrich events with node info
- [ ] Add `TranscriptRecord` type to `tinycua/config/types.py`

### Phase 5 — Tests (required)

- [ ] Unit tests for retry loop, validation, exhaustion behaviors
- [ ] Unit tests for DecisionNode classification retry
- [ ] Unit tests for monitor hook trigger points and exception handling
- [ ] Integration tests for retry through TinyCUALoop
- [ ] Unit tests for event model creation and serialization
- [ ] Unit tests for lifecycle event emission
- [ ] Unit tests for NodeStreamPolicy enforcement
- [ ] Integration test for multi-node streaming

### Phase 6 — Enhancements _(post-MVP)_

- [ ] JSONL transcript export utility
- [ ] Sequence numbering and run_id tracking
- [ ] Stream cancellation cleanup

> **Note**: Phase 6 must NOT be implemented until Phase 5 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: `NodeMonitor` is a Protocol (structural typing), not an ABC.
   - **Reason**: Allows any object with the right methods to serve as a monitor — no inheritance required. Matches Python's duck-typing philosophy and simplifies testing.
   - **Alternatives Considered**: ABC — rejected because it forces inheritance and is less flexible for a prototype.

2. **Decision**: Monitor hooks are called via `_safe_call()` with exception catching.
   - **Reason**: Monitor failures must not break node execution. A buggy monitor should degrade gracefully.
   - **Alternatives Considered**: Let exceptions propagate — rejected because it violates the transient/non-blocking contract.

3. **Decision**: `max_attempts=0` means 1 attempt (no retry), not 0 attempts.
   - **Reason**: A node must always execute at least once. `max_attempts` controls retry count, not total attempts. This matches the existing `max(max_attempts, 1)` pattern in the code.
   - **Alternatives Considered**: `max_attempts=0` means no execution — rejected because it would require special-casing everywhere.

4. **Decision**: `record_failure` writes a `SessionContextEntry` with `segment="output"` rather than a special failure type.
   - **Reason**: Keeps the session context model simple — failure is just another output entry. Downstream consumers can detect failures by checking for the `[RETRY_EXHAUSTED]` prefix in the content field.
   - **Alternatives Considered**: Special `FailureRecord` type — rejected because it adds complexity to the session model.

5. **Decision**: DecisionNode retries only the classification step, not the analysis step.
   - **Reason**: The analysis is an open-ended LLM call that produces content; validating it is subjective. The classification is a discrete label that can be validated against `classification_labels`. Retrying the analysis would be expensive and low-value.
   - **Alternatives Considered**: Retry both steps — rejected for cost/complexity.

6. **Decision**: `AgentMonitor` and `NodeMonitor` are independent hooks. The loop calls `AgentMonitor.on_*()` for loop-level observation; the node calls its own `NodeMonitor` via `self.config.monitor`. Both fire when configured — neither wraps or forwards to the other.
   - **Reason**: Simpler implementation with clear separation of concerns. The loop observes at the orchestration level; the node observes at the execution level. No delegation complexity.
   - **Alternatives Considered**: AgentMonitor wraps NodeMonitor — rejected because it requires AgentMonitor implementations to know about and forward to node-level monitors, coupling the two layers.

7. **Decision**: `NodeMonitor` hooks only fire when a node is called directly (e.g., `node(input)`), not when executed through `TinyCUALoop._execute_node()`.
   - **Reason**: `_execute_node()` calls `agent._call_llm()` directly rather than delegating to `node.__call__()`, so the node's monitor hook wiring (in `ProcessNode.__call__()` and `DecisionNode.__call__()`) is bypassed. This is a known design limitation — wiring `node(input)` through the loop would require a larger refactor to bring the loop's retry handling in line with the node's own retry logic. `AgentMonitor` is the loop-level hook and fires in both paths.
   - **Alternatives Considered**: Wire `node(input)` through `_execute_node()` — deferred to follow-up because it would duplicate the retry loop already in `ProcessNode.__call__()` or require extracting shared retry logic.
   - **Implication**: The hardcoded `ValidationResult(is_valid=True, errors=[])` in `_execute_node()`'s AgentMonitor after-hook is correct for this path — the loop does not run `validate_output()`. Use `NodeMonitor` for per-attempt validation results when direct node calls are used.

8. **Decision**: Use plain dicts for stream events (not a custom class)
   - **Reason**: SDK `BaseLoop` contract expects `AsyncIterator[dict[str, Any]]`. Using dicts maintains compatibility and avoids SDK changes.
   - **Alternatives Considered**: Custom StreamEvent class — rejected because it would require SDK changes to recognize the type.

9. **Decision**: Emit lifecycle events as additional yields in the existing `_run_stream()` generator
   - **Reason**: Minimal code change, no new threading or callback infrastructure needed.
   - **Alternatives Considered**: Separate event queue with background consumer — rejected as overengineering for prototype scope.

10. **Decision**: Apply `NodeStreamPolicy` filtering at the `_run_stream()` level, not per-node
    - **Reason**: Centralized filtering is simpler and consistent with how `NodeToolPolicy` and `NodeMessagePolicy` work.
    - **Alternatives Considered**: Per-node event filtering — rejected as adding unnecessary complexity.

11. **Decision**: Timestamps use `time.time()` (epoch seconds)
    - **Reason**: Simple, no timezone complications, sufficient for transcript ordering.
    - **Alternatives Considered**: `datetime.utcnow()` — rejected for serialization simplicity.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Monitor hook overhead slows node execution | Low | Low | Hooks are optional and lightweight; `_safe_call` catches exceptions fast |
| `record_failure` propagation rule not defined for some nodes | Medium | Medium | Default to no propagation; nodes that need failure propagation configure `PropagationRule.failure` |
| DecisionNode retry loop adds latency for invalid classifications | Low | Low | Classification retry is bounded by `max_attempts`; invalid labels are rare with well-prompted LLMs |
| Custom `validation_fn` raises unexpected exceptions | Medium | Low | `_safe_call` catches all exceptions; validation errors are logged |
| NodeMonitor does not fire through `TinyCUALoop._execute_node()` | Medium | Medium | Use AgentMonitor for loop-level observation; call nodes directly for per-attempt NodeMonitor granularity. Documented in Technical Decision #7 |
| Stream event volume causes memory pressure | Low | Medium | Events are yielded, not accumulated; consumer controls consumption |
| LLM endpoint doesn't support streaming | Medium | Low | Fallback to single-event yield after collecting full response |
| NodeStreamPolicy filtering breaks existing tests | Low | High | Existing tests use `stream=False`; streaming tests already pass |
| WildClawBench transcript format mismatch | Medium | Medium | Design events to be schema-compatible with common JSONL formats |

---

## Open Questions _(optional)_

1. **Should `AgentMonitor` support node-level filtering (e.g., monitor only certain node IDs)?**
   - Current thinking: Not in this milestone. Keep it simple — monitor all nodes, filter in the implementation if needed.

2. **Should failure state recording include the full validation error history across attempts?**
   - Current thinking: Yes — record all errors, not just the final one, for debugging.

3. Should lifecycle events include tool call details (tool name, arguments, result)?
   - **Resolved**: Yes, for `node.completed` events when tools were used. Include a `tool_calls` list in the event metadata.

4. Should we add a `run_id` to all events for multi-run correlation?
   - **Resolved**: Yes, via `TranscriptRecord` wrapper. Individual events don't need it.

---

## References

- Spec: [./spec.md](./spec.md)
- Design docs covered:
  - `src/tinycua/docs/design/loops/node.md` — full (retry, validation, monitor hook sections)
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — full (monitor hook, error handling sections)
  - `src/tinycua/docs/design/models/agent_state.md` — partial (failure recording)
  - `src/tinycua/docs/design/config/node_config.md` — full (NodeRetryPolicy)
  - `src/tinycua/docs/design/loops/base_loop.md` — streaming architecture
- Existing implementation:
  - `tinycua/config/node_config.py` — NodeRetryPolicy (Milestone 1.2)
  - `tinycua/config/types.py` — ValidationResult, ValidationError, LLMResult
  - `tinycua/loops/node.py` — ProcessNode.__call__() retry loop, validate_output(), build_retry_continuation()
  - `tinycua/loops/tinycua_loop.py` — _execute_node() integration point, _run_stream() streaming
  - `tinycua/config/node_config.py` — NodeStreamPolicy
