# Design Document: Custom Loop Creation API Simplification

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-16

---

## Overview

Restructure `BaseLoop` so that both `_run_sync()` and `_run_stream()` are thin orchestrators (~40–55 lines) that delegate to **public helper methods**. These helpers — `build_system_message()`, `process_tool_calls()`, `process_stream_iteration()`, and a few others — are callable by custom loop subclasses without reaching into private `_` API.

The goal is: when a developer writes `class MyLoop(BaseLoop)` and overrides `run()`, the public helpers they need are right there, documented and importable, not hidden behind underscores.

---

## Architecture

### Current vs. Proposed Method Visibility

| Current (private) | Proposed (public) | Used by |
|-------------------|-------------------|---------|
| `_build_system_message()` | `build_system_message()` | All loops |
| *(inline in `_run_sync`)* | `process_tool_calls()` | Sync custom loops |
| `_execute_tools_stream()` | `process_stream_tool_calls()` | Stream custom loops |
| *(two-phase helpers)* | `process_stream_iteration()` | Stream custom loops |
| `_accumulate_chunk()` | *(kept static private)* | Internal only |
| `_last_assistant_content()` | `last_assistant_content()` | All loops |
| `_read_stream_chunk()` | *(kept static private)* | Internal only |
| `_iter_llm_events()` | *(kept static private)* | Internal only |

Only truly internal plumbing stays private. Everything a custom loop might need is public.

---

## Public Helpers on `BaseLoop`

### `build_system_message(agent, override_instructions=None)`

Renamed from `_build_system_message`. No signature change. Custom loops call it in their `run()` override to build the system message without duplicating the logic:

```python
class MyLoop(BaseLoop):
    async def run(self, agent, messages, tools, ...):
        system_msg = self.build_system_message(agent)
        ...
```

### `async process_tool_calls(agent, tools, tool_calls, working_messages, tool_call_count)`

Extracted from the inline tool call loop in `_run_sync()`. Handles:
- Iterating over tool calls
- Parsing JSON arguments
- Looking up tools
- Calling `ToolExecutor.execute()`
- Checking cancellation and `max_tool_calls`
- Appending `function_call` and `function_call_output` messages to `working_messages`

Returns `(updated_tool_call_count, max_tool_calls_reached)`.

Custom sync loops that want different pre/post processing can call this and add their own logic around it:

```python
class MyLoop(BaseLoop):
    async def run(self, agent, messages, tools, ...):
        ...
        for _ in range(self.max_iterations):
            response = await agent._call_llm(messages, tools)
            if response.get("tool_calls"):
                log_tool_calls(response["tool_calls"])  # custom pre
                tool_call_count, _ = await self.process_tool_calls(
                    agent, tools, response["tool_calls"],
                    working_messages, tool_call_count,
                )
                log_results(working_messages)  # custom post
                continue
            return response.get("content", "")
```

### `process_stream_iteration(llm_stream, agent, content_parts, tool_calls_buffer, cumulative_usage, usage_settled_ids)`

An async generator that processes a full LLM stream iteration. Combines the current two-phase logic (`_yield_first_chunk_events` + `_yield_stream_body_events`) into a single public method. Yields raw SSE events plus synthetic lifecycle events (`response.created`, `response.in_progress`, `response.cancelled`). Returns cancellation/provider status via yielded events rather than a shared state object.

Custom streaming loops use this instead of reimplementing lifecycle handling:

```python
class MyStreamingLoop(BaseLoop):
    async def run(self, agent, messages, tools, ...):
        ...
        llm_stream = await agent._call_llm(messages, tools, stream=True)
        async for event in self.process_stream_iteration(
            llm_stream, agent, content_parts, tool_calls_buffer,
            cumulative_usage, usage_settled_ids,
        ):
            if event["type"] == "response.output_text.delta":
                await self.on_token(event["delta"])  # custom callback
            yield event
```

### `async process_stream_tool_calls(agent, tools, tool_calls_list, working_messages, tool_call_count)`

Cleaned-up version of the current `_execute_tools_stream()`. Handles the same logic but returns cleaner state. Public so custom streaming loops can call it after `process_stream_iteration` detects tool calls.

Returns `tuple[int, bool]` — `(updated_tool_call_count, max_tool_calls_reached)`. Custom callers must check the second element to decide whether to break out of the iteration loop (`max_tool_calls_reached=True`) or continue with the next LLM call.

### `last_assistant_content(messages)`

Renamed from `_last_assistant_content`. Static method, pure function.

---

## Refactored `_run_sync()` (~40 lines)

```
1. Build system message: self.build_system_message(agent)  ← public helper
2. For each iteration:
   a. Guard: is_cancelled, max_tool_calls
   b. Call agent._call_llm()
   c. If no tool_calls: append content and return
   d. Append assistant message
   e. Delegate to self.process_tool_calls()  ← public helper
   f. If max_tool_calls reached: return fallback
3. Return max-iterations fallback
```

---

## Refactored `_run_stream()` (~55 lines)

```
1. Build system message: self.build_system_message(agent)  ← public helper
2. Init state variables
3. try/except wrapper
4. For each iteration:
   a. Guard: is_cancelled, max_tool_calls
   b. Reset per-iteration containers
   c. Call agent._call_llm(stream=True)
   d. Delegate to self.process_stream_iteration()  ← public helper
      (yields events, tracks cancelled/provider_failed/completed booleans)
   e. If cancelled/failed: break
   f. If tool_calls_list:
      - tool_call_count, max_tool_calls_reached = await self.process_stream_tool_calls(...)  ← public helper
      - If max_tool_calls_reached: break
   g. Else: append content and break
5. Yield usage + completion events
6. except: yield failed events
```

`_IterStreamState` is removed. The three booleans (`cancelled`, `provider_failed`, `completed_by_provider`) are tracked as local variables in `_run_stream()` by inspecting yielded event types from `process_stream_iteration()`.

---

## Integration Test

A new test in `tests/integration/test_custom_agent_loop.py` (or a dedicated test) that:

1. Creates a custom `BaseLoop` subclass that overrides `run()` and calls the public helpers (`build_system_message()`, `process_tool_calls()`, etc.)
2. Creates an `Agent` with tools and this custom loop
3. Calls `agent.run()` with a query designed to trigger tool calling
4. Asserts that the custom loop called the helper methods and that at least one `function_call_output` was produced

**Deterministic forcing strategy**: To avoid flaky results across providers/models, the test MUST use one of these approaches (in order of preference):

- **Option A (provider-supported)**: Use the provider's `tool_choice` parameter (e.g., `tool_choice="required"` or `tool_choice={"type": "function", "function": {"name": "..."}}`) to force the named tool. This guarantees the LLM calls the tool regardless of the query.
- **Option B (fixture-based)**: Use an integration fixture that returns a real transport-compatible tool-call response while still exercising `Agent.run()` and the public helper code path end-to-end.
- **Option C (split strategy)**: Split into (1) deterministic unit/contract tests that verify exact tool execution via mocked LLM responses, plus (2) a real-LLM smoke test that does not serve as the acceptance gate for tool execution. Only the smoke test requires a real API key.

The test MUST assert that the custom loop called the new helper and produced at least one `function_call_output` message, not just that the LLM returned content.

This test uses the same LLM client infrastructure as existing integration tests (e.g., `tests/integration/conftest.py`).

---

## Implementation Phases

### Phase 1 — Promote existing private methods to public

- [ ] Rename `_build_system_message` → `build_system_message` and migrate all internal/test references.
- [ ] Rename `_last_assistant_content` → `last_assistant_content` and migrate all internal/test references.

### Phase 2 — Extract and expose sync tool processing

- [ ] Extract `process_tool_calls()` from the inline loop in `_run_sync()`
- [ ] Restructure `_run_sync()` to ~40 lines using `build_system_message()` + `process_tool_calls()`
- [ ] Run sync tests — all pass

### Phase 3 — Extract and expose stream processing

- [ ] Create `process_stream_iteration()` combining two-phase event logic
- [ ] Create `process_stream_tool_calls()` (cleaned up from `_execute_tools_stream()`)
- [ ] Remove `_IterStreamState` dataclass
- [ ] Remove `_yield_first_chunk_events`, `_yield_stream_body_events`
- [ ] Restructure `_run_stream()` to ~55 lines
- [ ] Run stream tests — all pass

### Phase 4 — New unit tests

- [ ] Unit tests for `build_system_message()` called from a subclass
- [ ] Unit tests for `process_tool_calls()` called from a subclass
- [ ] Unit tests for `process_stream_iteration()` called from a subclass
- [ ] Unit tests for `process_stream_tool_calls()` called from a subclass

### Phase 5 — Integration test

- [ ] Write integration test: custom loop subclass → agent.run() → real LLM call → verify tool execution
- [ ] Test runs as part of the integration test suite (`uv run pytest tests/integration/`)

### Phase 6 — Final verification

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All existing tests pass with zero modifications
- [ ] No changes to `Agent` class API

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Renaming `_build_system_message` to `build_system_message` breaks external code that calls the private method | Low | Medium | This is an intentional pre-release breaking change — no compatibility alias is required because the SDK has not been publicly released. |
| `process_stream_iteration()` changes event ordering vs current two-phase approach | Low | High | Existing stream tests validate exact ordering; they must pass. |
| Integration test requires a real LLM key | Medium | Low | Use the same mock/skip infrastructure as existing integration tests. |

---

## References

- Spec: `./spec.md`
- Current code: `src/tinycua-sdk/tinycua_sdk/agent/loop.py`
- Current tests: `tests/unit/test_loop.py`, `tests/unit/test_loop_custom.py`
- Integration tests: `tests/integration/test_custom_agent_loop.py`
