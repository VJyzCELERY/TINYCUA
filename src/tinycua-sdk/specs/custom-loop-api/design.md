# Design Document: Custom Loop Creation API Simplification

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-16

---

## Overview

Restructure the existing `BaseLoop` internals to make both `_run_sync()` and `_run_stream()` readable at a glance. The approach is to extract a few private helper methods that isolate the complex parts (tool execution iteration, stream event processing) into named, documented blocks. No new public API unless a genuinely universal helper emerges naturally.

The Agent's public API (`agent.tool_permissions`, `agent.tools`, `agent.skills`, `agent.run()`, etc.) stays completely unchanged — users configure their agent the same way they always have.

---

## Affected Components

| Component | Change | Notes |
|-----------|--------|-------|
| `BaseLoop._run_sync()` | Refactored | Tool execution extracted into private `_process_tool_calls_sync()`. Body ~40 lines. |
| `BaseLoop._run_stream()` | Refactored | Two-phase event processing combined. `_IterStreamState` removed. Body ~55 lines. |
| `BaseLoop._yield_first_chunk_events()` | Removed | Logic merged into a single stream pass |
| `BaseLoop._yield_stream_body_events()` | Removed | Logic merged into a single stream pass |
| `BaseLoop._IterStreamState` | Deleted | Replaced by local boolean variables |
| `BaseLoop._execute_tools_stream()` | Refactored | Simplified, may be kept or inlined |
| `BaseLoop._build_function_call_entry()` | **New private** | Extracts repeated dict construction |

---

## Refactored `_run_sync()` (~40 lines)

The current `_run_sync()` has ~90 lines with tool call logic inline. The refactored version:

```
1. Build system message, init working_messages (3 lines)
2. For each iteration:
   a. Guard: is_cancelled, max_tool_calls (4 lines)
   b. Call LLM via agent._call_llm() (1 line)
   c. If no tool_calls: append content and return (4 lines)
   d. Append assistant message + function_call entries (5 lines)
   e. Delegate to process_tool_calls_sync() (3 lines)
   f. If max_tool_calls reached: return fallback (2 lines)
3. Return fallback message (2 lines)
```

**New private helper: `_process_tool_calls_sync()`**

Extracts the inline tool call loop (~40 lines) into a named private method. Responsible for:
- Checking cancellation and max_tool_calls per tool call
- JSON argument parsing with error handling
- Tool lookup
- ToolExecutor.execute() call
- Appending function_call_output messages
- Returning `(updated_tool_call_count, max_tool_calls_reached)`

**New private helper: `_build_function_call_entry(tc)`**

Static method that builds the function_call message dict from a tool call dict. Used in both sync and stream paths to avoid repeated inline construction.

---

## Refactored `_run_stream()` (~55 lines)

The current `_run_stream()` has ~130 lines plus ~120 lines of helpers. The key simplification is merging the two-phase event processing (`_yield_first_chunk_events` + `_yield_stream_body_events`) into a single pass over the LLM stream, eliminating `_IterStreamState`.

```
1. Build system message, init state variables (5 lines)
2. try/except wrapper (2 lines)
3. For each iteration:
   a. Guard: is_cancelled, max_tool_calls (6 lines)
   b. Reset per-iteration containers (3 lines)
   c. Call LLM stream (1 line)
   d. Process ALL stream events in one pass:
      - Iterate iter_llm_events()
      - Handle lifecycle: created, completed, failed, error
      - Accumulate content, tool calls, usage
      - Track booleans: cancelled, provider_failed, completed_by_provider
      - Yield each event (15 lines)
   e. If cancelled or failed: break (3 lines)
   f. If tool_calls_list: execute and continue (8 lines)
   g. Else: append content and break (3 lines)
4. Yield usage + completion events (4 lines)
5. except: yield failed events (4 lines)
```

The `_IterStreamState` dataclass is replaced by three local boolean variables (`cancelled`, `provider_failed`, `completed_by_provider`) tracked directly from yielded event types.

---

## Potential Public Addition (only if genuinely useful)

During refactoring, one candidate may emerge as a public helper:

**`iterate_stream_events(llm_stream, cancel_event, content_parts, tool_calls_buffer, cumulative_usage, usage_settled_ids)`**

This would be the extracted stream processing loop — a standalone async generator that processes a full LLM stream iteration, yielding lifecycle events and accumulating into mutable containers. It would be useful for custom loop authors who want streaming with their own tool execution logic.

**Decision rule**: Only promote to public if:
1. It's a pure function of its inputs (no `self` references)
2. It's independently testable
3. At least one realistic custom loop use case would benefit from it

If promoted, it becomes `tinycua_sdk.agent.loop.iterate_stream_events()` with its own unit tests. If not, it stays as a private `BaseLoop._process_stream_iteration()` method.

---

## Implementation Phases

### Phase 1 — Refactor `_run_sync()`

- [ ] Extract `_build_function_call_entry()` static method
- [ ] Extract `_process_tool_calls_sync()` private method
- [ ] Restructure `_run_sync()` to ~40 lines
- [ ] Run existing `test_loop.py` sync tests — all pass

### Phase 2 — Refactor `_run_stream()`

- [ ] Combine first-chunk + body event processing into single stream pass
- [ ] Remove `_IterStreamState` dataclass, replace with local booleans
- [ ] Simplify `_execute_tools_stream()` or inline it
- [ ] Restructure `_run_stream()` to ~55 lines
- [ ] Decide: extract as public `iterate_stream_events()` or keep as private `_process_stream_iteration()`
- [ ] Run existing `test_loop.py` stream tests — all pass

### Phase 3 — Verification

- [ ] Run all existing tests: `test_loop.py`, `test_loop_custom.py`, `test_agent_streaming.py`, integration tests
- [ ] Verify zero modifications to test files
- [ ] Verify no changes to Agent class API
- [ ] Clean up any stale imports or dead code

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Merging two-phase stream events changes event ordering | Low | High | Existing stream tests validate exact ordering (created < in_progress < delta); they must pass |
| Removing `_IterStreamState` breaks subclass that references it | Very Low | Low | `_IterStreamState` is private and not exported in `__all__`; no external code should reference it |
| `_execute_tools_stream()` removal breaks external use | Low | Low | If it's used externally, keep as a delegate; otherwise remove |

---

## References

- Spec: `./spec.md`
- Current code: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- Current tests: `tests/unit/test_loop.py`, `tests/unit/test_loop_custom.py`
