# Feature Specification: Custom Loop Creation API Simplification

**Status**: Draft
**Created**: 2026-05-16
**Last Updated**: 2026-05-16
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Make the existing `BaseLoop` implementation clean and readable so that:

- A developer reading `_run_sync()` or `_run_stream()` can understand the full flow at a glance — no more than ~40–50 lines of clear orchestration per method
- A developer subclassing `BaseLoop` and overriding `run()` can easily understand what the parent does by reading its cleanly decomposed internals
- The Agent's public API (`agent.tool_permissions`, `agent.tools`, `agent.skills`, `agent.run()`, etc.) stays simple and unchanged — complexity lives inside the loop, not the configuration surface
- If any genuinely universal helper emerges from the refactoring, it can be promoted to a public function — but this is not the primary goal

### Gaps

1. **`_run_sync()` is ~90 lines of interleaved logic.** The tool call iteration, JSON parsing, tool lookup, execution, and message building are all inline with no helper decomposition.

2. **`_run_stream()` is ~130 lines plus ~120 more across four helper methods.** The two-phase event processing (first chunk + body events) with `_IterStreamState` dataclass makes the flow hard to trace.

3. **No internal helper granularity.** The sync path has no extracted helpers at all. The stream path has helpers that exist (like `_yield_first_chunk_events`, `_yield_stream_body_events`) but they communicate via a shared mutable `_IterStreamState` dataclass, making them hard to understand independently.

### Non-Goals

- Adding a large surface of new public API functions
- Changing the runtime behavior of `BaseLoop.run()` or `Agent.run()`
- Removing the `BaseLoop` class
- Extracting permission/approval logic out of `ToolExecutor`
- Performance optimization

### Constraints

- All existing tests must pass without modification
- The subclassing contract (`BaseLoop`, `override run()`) stays unchanged
- Agent public API unchanged

---

## Requirements

### Functional Requirements

**Code clarity:**

- **FR-001**: `BaseLoop._run_sync()` MUST be restructured so its body is ≤45 lines, with tool processing extracted into a private helper method.
- **FR-002**: `BaseLoop._run_stream()` MUST be restructured so its body is ≤60 lines, with event processing extracted into a single private helper that eliminates `_IterStreamState`.
- **FR-003**: Any extracted private helpers MUST be cleanly documented with docstrings.

**Minimal public additions:**

- **FR-004**: If a genuinely reusable stream-processing primitive emerges (e.g., combining the first-chunk and body-event logic), it MAY be promoted to a public module-level function — but only if it is independently testable and useful outside `BaseLoop`.
- **FR-005**: Any new public function MUST have unit tests and a docstring.

**Backward compatibility:**

- **FR-006**: All existing tests MUST pass without modification.
- **FR-007**: Custom loops subclassing `BaseLoop` MUST continue to work unchanged.

---

## Success Criteria

- [ ] **`_run_sync()` is ≤45 lines**: A developer can read it top-to-bottom in one pass
- [ ] **`_run_stream()` is ≤60 lines**: Same — clear orchestration, no hidden state
- [ ] **`_IterStreamState` removed**: Replace with inline boolean tracking
- [ ] **All existing tests pass**: Zero modifications to test files
- [ ] **No new public functions unless genuinely useful**: If a helper is promoted, it must have its own tests

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec | Refocused | Internal simplification first; minimal public additions |

---

## Open Questions

1. **Is `build_system_message()` worth making public?**
   - It's a pure function, easy to extract, and useful for custom loops.
   - Decision: Promote only if it's already called externally or is clearly valuable as a standalone helper.
