# Feature Specification: Custom Loop Creation API Simplification

**Status**: Draft
**Created**: 2026-05-16
**Last Updated**: 2026-05-16
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Provide a simpler, more accessible API for creating custom agent execution loops so that SDK users can:

- Write a custom loop (e.g., ReAct, PlanThenExecute, simple direct-LLM) with minimal boilerplate — ideally 10–20 lines
- Reuse stream lifecycle primitives (first-chunk detection, event accumulation, tool call extraction) without subclassing `BaseLoop`
- Read and understand the default `_run_stream()` implementation at a glance, because its internals are built from the same composable building blocks

### Gaps

1. **`_run_stream()` is too complex for what it does.** At ~130 lines for the method body plus ~250 total across its four helper methods (`_yield_first_chunk_events`, `_yield_stream_body_events`, `_execute_tools_stream`, `_accumulate_chunk`), the streaming path is hard to follow end-to-end. Each helper is tightly coupled to `BaseLoop` internals (mutating `_IterStreamState`, `working_messages`, `content_parts`, etc.) and cannot be reused independently.

2. **No standalone stream processing primitives.** The static/private methods (`_read_stream_chunk`, `_iter_llm_events`, `_accumulate_chunk`, `_accumulate_tool_chunk`, `_accumulate_usage`) are prefixed with `_` and undocumented. A custom loop author who wants streaming must reimplement all lifecycle event handling.

3. **Tool execution in streaming mode duplicates logic.** The tool call → execute → append cycle in `_run_sync` (lines 102–164) and `_execute_tools_stream` (lines 371–456) have different shapes but share the same core pattern. A shared primitive could unify them and simplify both paths.

### Non-Goals

- Changing the runtime behavior of `BaseLoop.run()` or `Agent.run()` — existing callers must see zero difference
- Adding new pre-built loop subclasses (ReActLoop, PlanThenExecuteLoop) as built-in SDK components
- Changing the `Agent` class API, its `run()` signature, or the `BaseLoop` subclassing contract
- Removing or renaming existing public methods on `BaseLoop`
- Performance optimization — this is purely a readability/composability improvement

### Constraints

- Backward compatibility: all existing unit/integration tests must pass without modification
- The `BaseLoop` subclassing contract (override `run()`, call `agent._call_llm()`, use `ToolExecutor.execute()`) must continue to work
- Existing private methods on `BaseLoop` may be refactored only if their public equivalent preserves the same behavior
- Must work with Python 3.11+

---

## User Scenarios & Testing

### Primary Scenario

**SDK user writes a custom streaming loop.** A developer wants to create a custom agent loop that streams intermediate events. Currently they would need to subclass `BaseLoop` and reimplement all streaming lifecycle handling. With the new API, they should be able to import standalone helpers and compose them in their custom loop without duplicating lifecycle logic.

### Acceptance Scenarios

1. **Given** a developer extends `BaseLoop` with a custom loop, **When** they implement `run()` using only the documented public helpers (stream processing, tool execution), **Then** the loop correctly handles streaming lifecycle (created, in_progress, output deltas, completed events).

2. **Given** the existing `test_loop.py` test suite, **When** the refactored `BaseLoop` is executed against all tests, **Then** every test passes with zero modifications.

3. **Given** the existing `test_loop_custom.py` contract tests, **When** a developer subclasses `BaseLoop` and overrides `run()`, **Then** their custom loop implementation continues to work as before.

4. **Given** a developer reads `_run_stream()`, **When** they trace through it, **Then** they should be able to understand the full flow by reading ~40–60 lines of orchestration that delegates to clearly-named helpers (not 250+ lines of interleaved logic).

### Edge Cases

- What happens when a custom loop uses stream processing helpers on an empty LLM stream? → Should handle `StopAsyncIteration` cleanly.
- What happens when cancellation occurs mid-stream? → Should produce `response.cancelled` event consistently.
- What happens when the provider emits a terminal event (`response.completed`, `response.failed`, `error`) as the first chunk? → Should not double-emit lifecycle events.
- What happens when tool call arguments span multiple chunks? → Should accumulate correctly and produce valid JSON.
- What happens when a custom stream helper encounters a malformed chunk? → Should yield an error event rather than crashing.

---

## Requirements

### Functional Requirements

- **FR-001**: The SDK MUST expose standalone, documented, public stream processing functions that custom loops can import and use without subclassing `BaseLoop`.
- **FR-002**: The SDK MUST expose a standalone, documented, public function for building system messages from agent instructions and skills.
- **FR-003**: The SDK MUST expose a standalone, documented, public function for executing tool calls and appending results to a message list.
- **FR-004**: `BaseLoop._run_stream()` MUST be refactored to use these standalone helpers, reducing its body size to a clear orchestration layer (~40–60 lines).
- **FR-005**: All standalone helpers MUST be tested independently (unit tests with fake LLM streams).
- **FR-006**: All existing tests MUST pass without modification.
- **FR-007**: The module-level functions `_accumulate_tool_chunk` and `_accumulate_usage` MUST be promoted to public names and documented.
- **FR-008**: A custom loop author MUST be able to implement a fully functional streaming loop (ReAct-style) using only the public helpers, without accessing any private `BaseLoop` methods.

### Key Entities

- **Loop Stream Primitives**: Functions that handle LLM stream lifecycle — reading chunks, detecting first-chunk type, accumulating content/tool calls/usage, iterating remaining events. These are stateless and receive all state via parameters.
- **Tool Execution Primitives**: Functions that execute tool calls from accumulated tool call data and append results to a working message list in the correct format.
- **System Message Builder**: A pure function that builds a system message dict from agent instructions and skill definitions.
- **BaseLoop (unchanged)**: The standard execution loop, refactored internally to delegate to the above primitives.

---

## Success Criteria

- [ ] **Custom loop with 15 lines**: A developer can write a streaming custom loop that handles all lifecycle events in ~15–20 lines of `run()` implementation plus helper calls
- [ ] **`_run_stream()` readability**: The refactored `_run_stream()` body is ≤60 lines and uses only public helper calls
- [ ] **All existing tests pass**: `test_loop.py`, `test_loop_custom.py`, `test_agent_streaming.py`, and integration tests pass with zero modifications
- [ ] **Public API documented**: Every exposed helper function has a docstring and appears in `__all__` in its module
- [ ] **New unit tests pass**: At least 5 new unit tests cover the standalone helpers directly

---

## Testing Plan

### Unit Tests

- New tests for each standalone helper function with fake streams:
  - `build_system_message()` — covers instructions, override, skills
  - `read_stream_chunk()` — covers normal chunk, empty stream, cancellation
  - `iter_llm_events()` — covers multi-chunk, stream exhaustion, cancellation
  - `accumulate_chunk()` — covers text delta, tool call delta, usage, completed
  - `accumulate_tool_chunk()` — covers all 4 event types (tool_call.delta, output_item.added, function_call_arguments.delta/done)
  - `accumulate_usage()` — covers Responses API keys and Chat Completions keys
  - `execute_tool_calls()` — covers success, unknown tool, JSON parse error, cancellation
  - `last_assistant_content()` — covers various message orderings
- Existing `test_loop.py` and `test_loop_custom.py` tests must still pass
- Edge case: empty stream, cancellation mid-chunk, provider-failed first chunk

### Integration Tests

- Existing integration tests (`test_agent_streaming.py`, `test_custom_agent_loop.py`) must pass without modification — this proves backward compatibility

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec | Draft | Initial version |
| Design | Pending | To be created alongside |

---

## Open Questions

1. **Helper module location**
   - **Owner**: @agent
   - **Target**: 2026-05-16
   - **Status**: Decided
   - **Proposed Answer**: Refactor within `loop.py` — keep all loop primitives in one module. The module will export both `BaseLoop` class and standalone functions. This avoids circular imports and keeps the API surface simple.
