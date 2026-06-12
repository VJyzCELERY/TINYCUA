# Design Document: Retry, Validation, and Monitor Hook

**Spec**: ./spec.md
**Status**: Draft
**Last Updated**: 2026-06-12
**Milestone**: 4.3 — Retry, Validation, and Monitor Hook

---

## Overview

This design implements the retry orchestration, output validation pipeline, and transient monitor hook for TinyCUA nodes. It wires `NodeRetryPolicy` into the `ProcessNode.__call__` loop, adds three monitor trigger points to `TinyCUALoop._execute_node`, and introduces `NodeMonitor`/`AgentMonitor` as lightweight protocol-based hooks. The monitor hooks are transient — they observe lifecycle events without creating sessions or writing to chat_history/session_context.

---

## Architecture

### Component Overview

```
ProcessNode.__call__(input)
  ├── build_messages()
  ├── retry loop (max_attempts):
  │     ├── [Monitor: before_llm_call]
  │     ├── _call_llm(messages)
  │     ├── [Monitor: after_llm_result]
  │     ├── validate_output(response)
  │     │     ├── required_tool_calls check
  │     │     ├── required_output_schema check
  │     │     └── validation_fn check
  │     ├── if valid → break
  │     ├── if invalid & attempts remain:
  │     │     └── build_retry_continuation() → append assistant message
  │     └── if invalid & exhausted:
  │           ├── [Monitor: after_exhaustion]
  │           └── on_retry_exhausted handler
  │                 ├── "raise" → NodeExecutionError
  │                 ├── "record_failure" → write failure state + propagate
  │                 └── "route_failure" → call failure route or fallback
  ├── record_output()
  ├── propagate()
  └── on_complete()
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| tinycua.config.node_config | Modified | NodeRetryPolicy review; add monitor protocol types |
| tinycua.loops.node | Modified | ProcessNode retry loop — monitor integration, exhaustion handlers |
| tinycua.loops.tinycua_loop | Modified | AgentMonitor integration into _execute_node |
| tinycua.config.types | Modified | Add NodeMonitor protocol, AgentMonitor protocol, MonitorContext |
| tinycua.loops.propagation | Modified | Failure propagation for record_failure/route_failure |

---

## Data Model

### New Entities

```python
# MonitorContext — context passed to monitor hooks
MonitorContext:
    node_id: str
    session_id: str
    attempt: int
    max_attempts: int
    resolved_tools: list[Tool]
    messages: list[dict]          # LLM-bound messages
    stream: bool

# NodeMonitor — protocol for node lifecycle observation
class NodeMonitor(Protocol):
    def on_before_llm_call(
        self, ctx: MonitorContext
    ) -> str | None:
        """Called before each LLM call. Returns optional continuation message."""
        ...

    def on_after_llm_result(
        self,
        ctx: MonitorContext,
        result: LLMResult,
        validation_error: ValidationError | None,
    ) -> str | None:
        """Called after LLM result, before retry handling. Returns optional continuation."""
        ...

    def on_after_exhaustion(
        self,
        ctx: MonitorContext,
        final_error: ValidationError,
    ) -> str | None:
        """Called after retry exhaustion, before failure propagation. Returns optional continuation."""
        ...

# AgentMonitor — protocol for loop-level observation (wraps NodeMonitor)
class AgentMonitor(Protocol):
    def on_before_node(
        self, node_id: str, session_id: str
    ) -> None:
        """Called before a node starts executing."""
        ...

    def on_after_node(
        self, node_id: str, session_id: str, result: LLMResult | DecisionResult
    ) -> None:
        """Called after a node completes execution."""
        ...

    def on_node_retry(
        self, node_id: str, attempt: int, error: ValidationError
    ) -> None:
        """Called when a node retries."""
        ...

    def on_node_exhaustion(
        self, node_id: str, final_error: ValidationError
    ) -> None:
        """Called when a node exhausts all retries."""
        ...
```

### Schema Changes

- `NodeConfigBase` gains optional `node_monitor: NodeMonitor | None = None` field.
- `TinyCUALoop` gains optional `agent_monitor: AgentMonitor | None = None` field.
- `ProcessNode.__call__` retry loop gains monitor hook invocations at three trigger points.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
class NodeMonitor(Protocol):
    """Transient hook for node lifecycle observation.
    
    Monitor invocations are transient: they do not create sessions,
    are not written to chat_history or session_context, and exceptions
    are caught and logged without disrupting execution.
    """

    def on_before_llm_call(
        self, ctx: MonitorContext
    ) -> str | None:
        """Called before each LLM call.
        
        Args:
            ctx: Monitor context with node_id, session_id, attempt, tools, messages.
            
        Returns:
            Optional assistant-role continuation message to inject, or None for no-op.
        """

    def on_after_llm_result(
        self,
        ctx: MonitorContext,
        result: LLMResult,
        validation_error: ValidationError | None,
    ) -> str | None:
        """Called after LLM result, before retry handling.
        
        Args:
            ctx: Monitor context.
            result: The raw LLM result.
            validation_error: Validation error if validation failed, None if valid.
            
        Returns:
            Optional assistant-role continuation message to inject, or None for no-op.
        """

    def on_after_exhaustion(
        self,
        ctx: MonitorContext,
        final_error: ValidationError,
    ) -> str | None:
        """Called after retry exhaustion, before failure propagation.
        
        Args:
            ctx: Monitor context.
            final_error: The final validation error.
            
        Returns:
            Optional assistant-role continuation message, or None for no-op.
        """


class AgentMonitor(Protocol):
    """Transient hook for loop-level observation."""

    def on_before_node(
        self, node_id: str, session_id: str
    ) -> None:
        """Called before a node starts executing."""

    def on_after_node(
        self, node_id: str, session_id: str, result: LLMResult | DecisionResult
    ) -> None:
        """Called after a node completes execution."""

    def on_node_retry(
        self, node_id: str, attempt: int, error: ValidationError
    ) -> None:
        """Called when a node retries."""

    def on_node_exhaustion(
        self, node_id: str, final_error: ValidationError
    ) -> None:
        """Called when a node exhausts all retries."""


def _invoke_monitor_safely(
    hook: Callable[..., str | None] | None,
    *args: Any,
    **kwargs: Any,
) -> str | None:
    """Invoke a monitor hook safely, catching and logging exceptions.
    
    Returns the hook's return value, or None if the hook raises.
    """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Monitor hook raises exception | Caught, logged, continuation is None | Node continues normal flow |
| monitor returns non-None non-string | Treated as None (no-op) | Defensive fallback |
| Both required_tool_calls and required_output_schema fail | Both errors in ValidationError | Single retry with combined message |
| validation_fn raises exception | Caught as ValidationError | Error message from exception |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Add `MonitorContext` dataclass to `tinycua.config.types`
- [ ] Add `NodeMonitor` protocol to `tinycua.config.types`
- [ ] Add `AgentMonitor` protocol to `tinycua.config.types`
- [ ] Add `_invoke_monitor_safely()` helper to `tinycua.config.types`
- [ ] Add `node_monitor: NodeMonitor | None` field to `NodeConfigBase`
- [ ] Add `agent_monitor: AgentMonitor | None` field to `TinyCUALoop`
- [ ] Integrate monitor hooks into `ProcessNode.__call__` retry loop (3 trigger points)
- [ ] Implement `on_retry_exhausted="record_failure"` with propagation integration
- [ ] Implement `on_retry_exhausted="route_failure"` with failure route fallback
- [ ] Review and verify `validate_output()` covers all validation paths
- [ ] Review and verify `build_retry_continuation()` uses custom builder when provided
- [ ] Write unit tests for retry loop, validation, exhaustion handlers, and monitor hooks
- [ ] Write integration tests for retry e2e and monitor e2e

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Advanced monitor hooks (e.g., per-node-type monitors, conditional monitoring)
- [ ] Monitor hook performance profiling

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: NodeMonitor as a Protocol (not ABC)
   - **Reason**: Lighter weight, allows duck-typing and simple callable hooks (e.g., a plain function)
   - **Alternatives Considered**: ABC — rejected because overly formal for an optional transient hook

2. **Decision**: Three monitor trigger points (before, after, exhaustion)
   - **Reason**: Covers all lifecycle states without being overly granular; aligns with design doc spec
   - **Alternatives Considered**: More trigger points (e.g., per-validation-check) — rejected because too fine-grained for prototype

3. **Decision**: Monitor exceptions caught and logged, not propagated
   - **Reason**: Monitor hooks are observational; they must not disrupt node execution
   - **Alternatives Considered**: Let exceptions propagate — rejected because fragile

4. **Decision**: Monitor continuations enter retry message flow (not direct LLM injection)
   - **Reason**: Continuations are assistant-role messages that follow the same retry message path
   - **Alternatives Considered**: Direct LLM injection — rejected because bypasses validation loop

5. **Decision**: AgentMonitor composes NodeMonitor (not replaces)
   - **Reason**: AgentMonitor adds loop-level observation; NodeMonitor handles per-node hooks
   - **Alternatives Considered**: Single combined interface — rejected because separation of concerns

6. **Decision**: record_failure uses PropagationRule.failure target
   - **Reason**: Consistent with existing propagation model from Milestone 4.1
   - **Alternatives Considered**: Hardcoded root session write — rejected because ignores propagation rules

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Monitor hook performance impact | Low | Medium | Hooks are optional and transient; no-ops are cheap |
| Monitor hook exceptions break retry loop | Low | High | All hooks wrapped in _invoke_monitor_safely with try/except |
| route_failure without defined handler | Medium | Low | Fallback to record_failure when no handler exists |
| Custom validation_fn raises unexpected exception | Medium | Medium | Caught as ValidationError with exception message |
| Monitor hook injects invalid continuation | Low | Low | Continuation is validated as str before injection |

---

## Open Questions

1. **Should NodeMonitor be a protocol or an abstract base class?**
   - **Status**: Proposed
   - **Resolution**: Protocol — lighter weight, allows duck-typing and simple callable hooks.

2. **Should AgentMonitor be a separate interface or compose NodeMonitor?**
   - **Status**: Proposed
   - **Resolution**: Compose — AgentMonitor wraps NodeMonitor and adds loop-level observation.

---

## References

- Spec: `./spec.md`
- Node design: `src/tinycua/docs/design/loops/node.md`
- TinyCUALoop design: `src/tinycua/docs/design/loops/tinycua_loop.md`
- Node config design: `src/tinycua/docs/design/config/node_config.md`
- AgentState design: `src/tinycua/docs/design/models/agent_state.md`
- Propagation design: `src/tinycua/docs/design/loops/propagation.md`
