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

**Testing:**

- **FR-007**: An integration test MUST exist that creates a custom loop subclass, uses it with `Agent.run()`, and verifies correct tool calling behavior via a real LLM call (using the SDK's existing integration test infrastructure).
- **FR-008**: All standalone unit tests MUST cover the new public helpers directly.

**Backward compatibility:**

- **FR-009**: All existing tests MUST pass without modification.
- **FR-010**: Custom loops written against the current `BaseLoop` subclassing contract MUST continue to work.

---

## Success Criteria

- [ ] **`_run_sync()` is ≤45 lines**: Reads as clear orchestration delegating to public helpers
- [ ] **`_run_stream()` is ≤60 lines**: Single-pass event processing, no `_IterStreamState`
- [ ] **Public helpers available**: `build_system_message()`, `process_tool_calls()` (sync helper), `process_stream_iteration()` (stream helper) — all callable from a subclass
- [ ] **Custom loop integration test**: A test with a real LLM call (or the SDK's standard integration mock) proves a custom loop subclass works end-to-end
- [ ] **All existing tests pass**: Zero modifications to test files

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
