# Feature Specification: Custom Loop Creation API Simplification

**Status**: Draft
**Created**: 2026-05-16
**Last Updated**: 2026-05-16
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Make `BaseLoop` a clean, readable base class that custom loops can easily build upon:

- `_run_sync()` and `_run_stream()` should be thin orchestrators (~40–55 lines each) that delegate to well-named public helper methods
- Those helper methods must be **public** (no `_` prefix) so custom loop subclasses can call them directly in their own `run()` override without accessing private API
- A custom loop author subclassing `BaseLoop` should be able to compose these public helpers however they need — not reverse-engineer private internals
- The Agent's public API (`agent.tool_permissions`, `agent.tools`, `agent.skills`, `agent.run()`) stays simple and unchanged
- End-to-end confidence: an integration test proves a custom loop works with a real LLM call

### Gaps

1. **`_run_sync()` is ~90 lines of interleaved logic.** Tool call processing, JSON parsing, tool lookup, execution, and message building are all inline with no helper decomposition. A custom loop that wants different tool processing must reimplement the whole thing.

2. **`_run_stream()` is ~130 lines plus ~120 more across four helper methods.** Two of those helpers (`_yield_first_chunk_events`, `_yield_stream_body_events`) are private and communicate via `_IterStreamState`, making them unusable by subclasses.

3. **Private helpers block reuse.** Currently everything useful is prefixed with `_`: `_build_system_message`, `_accumulate_chunk`, `_last_assistant_content`, etc. Subclasses that need these must either copy the code or call private API (bad practice).

4. **No integration test for custom loops.** Unit tests cover the default `BaseLoop` well, but there's no end-to-end test proving a custom loop subclass works with a real LLM provider.

### Non-Goals

- Adding a large surface of new standalone module-level API functions
- Changing the runtime behavior of `BaseLoop.run()` or `Agent.run()` for existing callers
- Removing the `BaseLoop` class
- Extracting permission/approval logic out of `ToolExecutor`
- Performance optimization

### Constraints

- All existing tests must pass without modification
- The subclassing contract stays unchanged — `class MyLoop(BaseLoop): async def run(self, ...)`
- Agent public API stays unchanged

---

## User Scenarios & Testing

### Primary Scenario: Custom Loop Subclass Composing Public Helpers

**As a** developer building a custom agent loop,
**I want to** subclass `BaseLoop` and compose its public helper methods in my `run()` override,
**So that** I can define custom tool-calling and streaming behavior without duplicating internal logic or accessing private `_` API.

**Given** a `BaseLoop` subclass `CustomToolLoop` that overrides `run()` and calls `self.build_system_message()`, `self.process_tool_calls()`, and `self.last_assistant_content()`,
**When** an `Agent` is configured with `loop=CustomToolLoop()` and `agent.run()` is invoked with a query that triggers tool calling,
**Then** the custom loop produces the correct tool-calling result, and the helper methods are confirmed to have been called during execution.

### Acceptance Scenarios

**AC-001: Sync custom loop with tool calls** — A custom sync loop subclassing `BaseLoop` calls `build_system_message()`, `process_tool_calls()`, and `last_assistant_content()` in its `run()` override. When used with `Agent.run()`, the result includes the tool output. The custom loop subclass exposes observable flags proving each helper was invoked.

**AC-002: Streaming custom loop with tool calls** — A custom streaming loop subclassing `BaseLoop` calls `build_system_message()`, `process_stream_iteration()`, and `process_stream_tool_calls()` in its `run()` override. When used with `Agent.run(stream=True)`, the event stream includes `response.created`, `response.completed`, and content deltas. The subclass exposes observable flags proving each helper was invoked.

**AC-003: Cancellation during sync loop** — When `agent.is_cancelled` is `True` during tool processing, the sync custom loop raises `asyncio.CancelledError` immediately.

**AC-004: Max tool calls limit enforced** — When a sync custom loop reaches `max_tool_calls` in a single response, it returns fallback content (e.g., `"[max tool calls]"`) without calling the LLM again.

**AC-005: `Agent.run()` API unchanged** — The `Agent` class public API (`agent.run()`, `agent.tool_permissions`, `agent.tools`, `agent.skills`) remains unchanged. Custom loop authors configure tool behavior solely via `LanguageModel` and the custom loop subclass.

### Edge Cases

- **Invalid tool arguments**: When a tool call has unparseable JSON arguments, the loop reports an error and continues without crashing.
- **Unknown tool name**: When the LLM requests a tool not registered with the agent, the loop returns an error message to the LLM and continues.
- **Provider stream failure**: When the LLM provider stream raises an exception mid-stream, the custom loop yields a `response.failed` event and stops gracefully.
- **No tool calls in response**: When the LLM returns content with no tool calls, the custom loop returns the content directly without calling `process_tool_calls()`.
- **Max iterations reached**: When the loop exceeds `max_iterations` without a final answer, the custom loop returns fallback content.
- **Skipped real-LLM integration tests**: Integration tests that require a real LLM server are skipped gracefully when no server is available, using the existing `@pytest.mark.integration` infrastructure.

---

## Requirements

### Functional Requirements

**Code clarity:**

- **FR-001**: `BaseLoop._run_sync()` MUST be restructured so its body is ≤45 lines, with tool processing extracted into a public helper method.
- **FR-002**: `BaseLoop._run_stream()` MUST be restructured so its body is ≤60 lines, with stream event processing extracted into a public helper that eliminates `_IterStreamState`.
- **FR-003**: Both `_run_sync()` and `_run_stream()` MUST delegate only to public helper methods (no `_` prefix) or to truly internal plumbing.

**Public helpers:**

- **FR-004**: The tool processing helper extracted from `_run_sync()` MUST be a public method on `BaseLoop` (no `_` prefix), documented and usable by custom loop subclasses.
- **FR-005**: The stream event processing helper extracted from `_run_stream()` MUST be a public method on `BaseLoop`, documented and usable by custom loop subclasses.
- **FR-006**: `build_system_message()` MUST be a public method on `BaseLoop` (currently `_build_system_message`), callable by subclasses.
- **FR-007**: `process_stream_tool_calls()` MUST be a public method on `BaseLoop`, cleaned up from the current `_execute_tools_stream()`, documented and usable by custom streaming loop subclasses.
- **FR-008**: `last_assistant_content()` MUST be a public method on `BaseLoop` (currently `_last_assistant_content`), callable by subclasses.

**Testing:**

- **FR-009**: An integration test MUST exist that creates a custom loop subclass, uses it with `Agent.run()`, and verifies correct tool calling behavior via a real LLM call (using the SDK's existing integration test infrastructure).
- **FR-010**: All standalone unit tests MUST cover the new public helpers directly.

**Backward compatibility:**

- **FR-011**: All existing tests MUST pass after migrating private-helper references to the new public `BaseLoop` helper API.
- **FR-012**: Custom loops that only rely on the supported `BaseLoop.run(...)` subclassing contract MUST continue to work; private `_` helper access is not preserved because the SDK has not been publicly released.

---

## Success Criteria

- [ ] **`_run_sync()` is ≤45 lines**: Reads as clear orchestration delegating to public helpers
- [ ] **`_run_stream()` is ≤60 lines**: Single-pass event processing, no `_IterStreamState`
- [ ] **Public helpers available**: `build_system_message()`, `process_tool_calls()` (sync helper), `process_stream_iteration()` (stream helper), `process_stream_tool_calls()`, `last_assistant_content()` — all callable from a subclass
- [ ] **Custom loop integration test**: A test with a real LLM call (or the SDK's standard integration mock) proves a custom loop subclass works end-to-end
- [ ] **All existing tests pass**: All existing behavioral coverage continues to pass after intentional test updates for renamed/public helper APIs

---

## Testing Plan

### Unit Tests

- Extend existing `test_loop_custom.py` with tests that call the new public helpers directly from a custom subclass
- Test each public helper independently with fake LLM responses

### Integration Tests

- New integration test (or extend existing `test_custom_agent_loop.py`): Create a `CustomLoop(BaseLoop)` subclass that uses the public helpers in its `run()` override, then call `agent.run()` and verify the full tool-calling flow works

---

## Open Questions

None.
