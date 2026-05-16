# Design Document: Custom Loop Creation API Simplification

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-16

---

## Overview

Refactor `tinycua_sdk/agent/loop.py` to extract standalone, public, documented helper functions from `BaseLoop`'s private methods. The `BaseLoop` class itself is refactored to delegate to these new functions, making `_run_stream()` dramatically more readable (~50 lines of orchestration instead of ~250 lines of interleaved logic). Custom loop authors can import and compose the helpers without subclassing `BaseLoop`.

All helpers live in `loop.py` alongside `BaseLoop` — keeping the loop API surface in one module avoids circular imports and provides a single import path.

---

## Architecture

### Component Overview

```
  Custom Loop Author                          SDK internals
  ──────────────────                         ────────────

  from tinycua_sdk.agent.loop import          BaseLoop
      build_system_message,                   ├── run()  ← unchanged
      iterate_stream_events,                  ├── _run_sync()  ← minor refactor
      execute_tool_calls,                     └── _run_stream()  ← now delegates to
          ...                                     public standalone helpers

  class MyLoop(BaseLoop):
      async def run(self, ...):               Standalone functions (public API)
          msg = build_system_message(...)     ├── build_system_message()
          llm_stream = await agent._call_llm(...)  ├── read_stream_chunk()
          async for event in iterate_stream_events(...):  ├── iter_llm_events()
              yield event                     ├── iterate_stream_events()
          ...                                 ├── accumulate_chunk()
                                              ├── accumulate_tool_chunk()
                                              ├── accumulate_usage()
                                              ├── execute_tool_calls()
                                              └── last_assistant_content()
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `loop.py` — module-level | Modified | Private `_accumulate_tool_chunk`, `_accumulate_usage` → public; add new standalone functions |
| `loop.py` — `BaseLoop` | Modified | Private methods delegate to standalone functions; `_run_stream()` simplified |
| `loop.py` — `__all__` | Modified | Export new public functions |
| `loop.py` — `_IterStreamState` | Deleted | Replaced by inline boolean tracking in `_run_stream()` |
| `test_loop.py` | Unchanged | Must pass without modification |
| `test_loop_custom.py` | Unchanged | Must pass without modification |
| `__init__.py` | Unchanged | `BaseLoop` re-export unchanged |

---

## API / Interface Contracts

### New Public Functions in `tinycua_sdk/agent/loop`

All functions are stateless and accept their dependencies explicitly.

---

#### `build_system_message(agent, override_instructions=None)`

```python
def build_system_message(
    agent: Agent,
    override_instructions: str | None = None,
) -> dict[str, str]:
    """Build a system message from agent instructions and skill definitions.

    Args:
        agent: The agent whose instructions/skills to use.
        override_instructions: When provided, replaces agent.instructions.

    Returns:
        A dict with ``role="system"`` and joined ``content``.
    """
```

Pure function — no exceptions. Empty instructions produce `{"role": "system", "content": ""}`.

---

#### `read_stream_chunk(llm_stream, cancel_event)`

```python
async def read_stream_chunk(
    llm_stream: AsyncIterator[dict[str, Any]],
    cancel_event: asyncio.Event,
) -> tuple[dict[str, Any] | None, bool]:
    """Read one chunk from an LLM stream, raced against cancellation.

    Args:
        llm_stream: The LLM response async iterator.
        cancel_event: An asyncio.Event that is set when cancellation is requested.

    Returns:
        ``(chunk, False)`` on a successful read,
        ``(None, True)`` when cancellation was requested,
        ``(None, False)`` when the stream is exhausted.
    """
```

Swallows `CancelledError` on cancelled pending tasks. `StopAsyncIteration` from the stream is caught and returns `(None, False)`.

---

#### `iter_llm_events(llm_stream, cancel_event)`

```python
async def iter_llm_events(
    llm_stream: AsyncIterator[dict[str, Any]],
    cancel_event: asyncio.Event,
) -> AsyncIterator[tuple[dict[str, Any] | None, bool]]:
    """Yield ``(chunk, is_completed)`` from an LLM stream.

    Yields ``(None, False)`` on exhaustion. Stops iteration on cancellation.

    Args:
        llm_stream: The LLM response async iterator.
        cancel_event: An asyncio.Event set on cancellation.

    Yields:
        ``(chunk, False)`` for normal chunks,
        ``(None, False)`` when the stream ends,
        ``(None, True)`` when the chunk type is ``response.completed``.
    """
```

Closes the stream via `aclose()` in a `finally` block.

---

#### `accumulate_chunk(chunk, content_parts, tool_calls_buffer, cumulative_usage, usage_settled_ids)`

```python
def accumulate_chunk(
    chunk: dict[str, Any],
    content_parts: list[str],
    tool_calls_buffer: dict[str, dict[str, Any]],
    cumulative_usage: dict[str, int],
    usage_settled_ids: set[str],
) -> None:
    """Accumulate a stream chunk into content parts, tool calls, and usage.

    All mutable containers are updated in place.
    """
```

No exceptions. Unknown chunk types are silently ignored (future-proofing).

---

#### `accumulate_tool_chunk(chunk, chunk_type, tool_calls_buffer)`

```python
def accumulate_tool_chunk(
    chunk: dict[str, Any],
    chunk_type: str,
    tool_calls_buffer: dict[str, dict[str, Any]],
) -> None:
    """Accumulate tool call data from a stream chunk.

    Handles four event types:
    - ``response.tool_call.delta`` — creates or updates tool call by index
    - ``response.output_item.added`` — creates tool call entry for function_call items
    - ``response.function_call_arguments.delta`` — appends argument delta
    - ``response.function_call_arguments.done`` — sets final argument string
    """
```

No exceptions. Unknown chunk types are silently ignored.

---

#### `accumulate_usage(cumulative, usage)`

```python
def accumulate_usage(
    cumulative: dict[str, int],
    usage: dict[str, Any],
) -> None:
    """Accumulate usage into cumulative counters.

    Normalises both Responses API keys (``input_tokens``, ``output_tokens``)
    and Chat Completions keys (``prompt_tokens``, ``completion_tokens``).

    Args:
        cumulative: Dict with keys ``input_tokens``, ``output_tokens``, ``total_tokens``.
        usage: Usage dict from provider (may use either key convention).
    """
```

---

#### `iterate_stream_events(llm_stream, agent, content_parts, tool_calls_buffer, cumulative_usage, usage_settled_ids)`

```python
async def iterate_stream_events(
    llm_stream: AsyncIterator[dict[str, Any]],
    agent: Agent,
    content_parts: list[str],
    tool_calls_buffer: dict[str, dict[str, Any]],
    cumulative_usage: dict[str, int],
    usage_settled_ids: set[str],
) -> AsyncIterator[dict[str, Any]]:
    """Process a full LLM stream iteration, yielding lifecycle events.

    Encapsulates first-chunk detection, lifecycle event injection
    (``response.created``, ``response.in_progress``), and body event
    processing. All content, tool call, and usage accumulation is
    written into the mutable containers.

    When cancellation is detected mid-stream, yields a ``response.cancelled``
    event and stops.

    Yields:
        Raw SSE event dicts plus synthetic lifecycle events.
    """
```

**Error handling**:
- Empty stream: yields `response.created`, `response.in_progress`, then stops.
- First chunk is `response.completed`: yields `response.created`, the completed event.
- First chunk is `response.failed`/`error`: yields `response.created`, the error event.
- Cancellation mid-body: yields `response.cancelled` then stops.
- Stream exhaustion: handled cleanly via `iter_llm_events` returning `None`.

**Why a combined function instead of two** (first-chunk + body-events):
The original split into `_yield_first_chunk_events` and `_yield_stream_body_events` existed to allow the caller to short-circuit (break the loop) after first-chunk processing without redundant iteration. However, this split introduced the `_IterStreamState` mutability pattern and made the flow harder to follow. The combined version is simpler: one async generator that yields all events, with the caller tracking booleans from yielded event types. The 4–8 lines of "wasted" stream reads on a short-circuit are trivial compared to the readability gain.

---

#### `execute_tool_calls(tool_calls_list, tools, agent, working_messages, tool_call_count)`

```python
async def execute_tool_calls(
    tool_calls_list: list[dict[str, Any]],
    tools: list[Tool],
    agent: Agent,
    working_messages: list[dict],
    tool_call_count: int,
) -> tuple[int, list[dict[str, Any]], int]:
    """Execute accumulated tool calls and append results to working_messages.

    For each tool call:
    1. Checks cancellation and max_tool_calls limit
    2. Parses JSON arguments
    3. Looks up the tool by name
    4. Executes via ``ToolExecutor.execute()``
    5. Appends ``function_call`` and ``function_call_output`` messages

    Args:
        tool_calls_list: Accumulated tool call data from the stream.
        tools: List of available tools.
        agent: The agent (provides tool_permissions, approval_workflow, etc.).
        working_messages: Message list (mutated in place with tool call entries).
        tool_call_count: Current count of executed tool calls.

    Returns:
        Tuple of (updated tool_call_count, executed_tool_calls list,
        assistant_index = index before first appended message).
    """
```

**Error handling**:
- JSON parse error: appends error output, continues to next tool call.
- Unknown tool: appends error output, continues.
- Tool execution exception: raises `RuntimeError` (same as current behavior).
- Cancellation or max_tool_calls: stops processing remaining tool calls (returns early).

---

#### `last_assistant_content(messages)`

```python
def last_assistant_content(messages: list[dict]) -> str:
    """Find the content of the last assistant message, or empty string."""
```

Returns `""` when no assistant message exists.

---

### Refactored `BaseLoop._run_stream()`

The new `_run_stream()` body is approximately 55 lines of orchestration:

```
1.  Build system message
2.  Initialize state (cumulative_usage, usage_settled_ids, finish_reason)
3.  try/except wrapping the outer iteration loop
4.  For each iteration:
    a.  Guard (is_cancelled, max_tool_calls)
    b.  Reset per-iteration containers
    c.  Call agent._call_llm(stream=True)
    d.  Process stream via iterate_stream_events(), tracking booleans
    e.  Short-circuit on cancellation/failure
    f.  Build combined_content and tool_calls_list from accumulated state
    g.  Either execute tool calls and continue, or append content and break
5.  Yield final usage event
6.  Yield final completion event (if not already provided)
7.  except Exception → yield failed/error events
```

### Refactored `BaseLoop` static methods

Private static methods become thin delegates to the standalone functions for backward compatibility:

```python
class BaseLoop:
    @staticmethod
    async def _read_stream_chunk(llm_stream, cancel_event):
        return read_stream_chunk(llm_stream, cancel_event)
```

Same pattern for `_accumulate_chunk`, `_last_assistant_content`, `_build_system_message`, and `_iter_llm_events`. The `_yield_first_chunk_events` and `_yield_stream_body_events` methods are **removed** since they are private and no longer used. `_execute_tools_stream` **delegates** to `execute_tool_calls()`.

`_IterStreamState` is **deleted** — no longer needed.

---

## Implementation Phases

### Phase 1 — Extract and Refactor

- [ ] **PH1-1**: Rename `_accumulate_tool_chunk` → `accumulate_tool_chunk` (public), add docstring, update `__all__`
- [ ] **PH1-2**: Rename `_accumulate_usage` → `accumulate_usage` (public), add docstring, update `__all__`
- [ ] **PH1-3**: Extract `BaseLoop._build_system_message` → standalone `build_system_message()`, delegate from class
- [ ] **PH1-4**: Extract `BaseLoop._read_stream_chunk` → standalone `read_stream_chunk()`, delegate from class
- [ ] **PH1-5**: Extract `BaseLoop._iter_llm_events` → standalone `iter_llm_events()`, delegate from class
- [ ] **PH1-6**: Extract `BaseLoop._accumulate_chunk` → standalone `accumulate_chunk()`, delegate from class
- [ ] **PH1-7**: Extract `BaseLoop._last_assistant_content` → standalone `last_assistant_content()`, delegate from class
- [ ] **PH1-8**: Extract `BaseLoop._execute_tools_stream` → standalone `execute_tool_calls()`, delegate from class
- [ ] **PH1-9**: Create standalone `iterate_stream_events()` combining first-chunk + body-event logic
- [ ] **PH1-10**: Refactor `BaseLoop._run_stream()` to use the standalone helpers (`iterate_stream_events`, `execute_tool_calls`)
- [ ] **PH1-11**: Delete `_IterStreamState` dataclass
- [ ] **PH1-12**: Delete `_yield_first_chunk_events` and `_yield_stream_body_events` from BaseLoop
- [ ] **PH1-13**: Run existing tests — all must pass without modification

### Phase 2 — New Tests

- [ ] **PH2-1**: Test `build_system_message()` standalone — same coverage as current `TestBaseLoopBuildSystemMessage`
- [ ] **PH2-2**: Test `read_stream_chunk()` standalone — normal chunk, cancellation, exhausted stream
- [ ] **PH2-3**: Test `iter_llm_events()` standalone — multi-chunk, cancellation, stream aclose
- [ ] **PH2-4**: Test `accumulate_chunk()` standalone — delta, tool call, usage, completed
- [ ] **PH2-5**: Test `accumulate_tool_chunk()` standalone — all 4 event types
- [ ] **PH2-6**: Test `accumulate_usage()` standalone — both key conventions
- [ ] **PH2-7**: Test `iterate_stream_events()` standalone — empty, first-chunk completed/failed/error, normal flow, cancellation
- [ ] **PH2-8**: Test `execute_tool_calls()` standalone — success, unknown tool, JSON parse error, cancellation, max_tool_calls
- [ ] **PH2-9**: Test `last_assistant_content()` standalone — various orderings, no assistant
- [ ] **PH2-10**: Verify existing `test_loop.py` and `test_loop_custom.py` tests still pass = zero modifications needed

### Phase 3 — Documentation Wrap-up

- [ ] **PH3-1**: Update `loop.py` module docstring to mention standalone helpers
- [ ] **PH3-2**: Ensure all public functions are in `__all__`
- [ ] **PH3-3**: Verify all docstrings are complete (Args, Returns, Yields, Raises)

---

## Technical Decisions

1. **Keep all standalone helpers in `loop.py` rather than a new module.**
   - Avoids circular imports (helpers reference `Agent`, `Tool` types used elsewhere in the SDK). Single import path `from tinycua_sdk.agent.loop import ...` is simpler for users.
   - Alternative considered: A separate `stream_primitives.py` module — rejected because it would require either an import chain or duplication of type references.

2. **`iterate_stream_events()` is a combined async generator (not separate first-chunk + body functions).**
   - The original two-function split required a mutable `_IterStreamState` dataclass to communicate between them and the caller. A single generator eliminates this indirection. The minimal overhead of reading a few extra stream chunks on short-circuit is negligible.
   - Alternative considered: Keep the two-function split but make them standalone — rejected as it would force the same awkward state pattern on custom loop authors.

3. **Mutable containers (`content_parts`, `tool_calls_buffer`, etc.) remain as explicit parameters rather than being bundled into a state object.**
   - Explicit parameters make the data flow visible and are more Pythonic. A `StreamAccumulator` class would add abstraction without reducing complexity.
   - Alternative considered: A `StreamAccumulator` dataclass bundling all state — rejected as overengineering.

4. **`execute_tool_calls()` appends messages in interleaved format (function_call, function_call_output per tool call) rather than grouped format.**
   - The interleaved format is what both `_run_sync` and `_execute_tools_stream` produce. This makes `execute_tool_calls()` usable by both paths. Custom loops typically want the interleaved format for real-time processing.

5. **BaseLoop's private methods become thin delegates to standalone functions, kept briefly for any out-of-tree callers.**
   - While the methods are prefixed `_` (private), they might be accessed by custom loops written against the current SDK. Delegation provides a deprecation path without breaking existing code.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Refactored `_run_stream()` introduces a subtle behavioral regression | Low | High | The existing tests are comprehensive (30+ test cases for streaming). Run the full test suite before Phase 1 merge. |
| Standalone functions have a different signature than expected by custom loop authors | Low | Medium | Keep private method delegates in Phase 1. Remove them only after a deprecation cycle. |
| `iterate_stream_events()` doesn't preserve the exact event ordering of the original split functions | Low | Medium | Existing tests validate exact event ordering (e.g., `created < in_progress < delta`). These tests must pass. |
| Circular import when moving functions out of BaseLoop | Low | Low | All new functions take `Agent` type hints via `TYPE_CHECKING` guard (same pattern as existing code). |

---

## References

- Spec: `./spec.md`
- Current implementation: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- Current tests: `src/tinycua-sdk/tests/unit/test_loop.py`, `src/tinycua-sdk/tests/unit/test_loop_custom.py`
