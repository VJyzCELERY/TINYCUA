# Implementation: Stage 5 — Streaming

Add all four streaming modes (`off`, `token`, `event`, `all`) to the agent execution loop and LLM client, so that `agent.run()` can return either a final string or an async iterator of events.

## Context

- **Spec Reference**: `specs/refactor-tinycua-sdk-v2/specs/stage-05-streaming/spec.md`
- **Design Reference**: `specs/refactor-tinycua-sdk-v2/specs/stage-05-streaming/design.md`
- **Priority**: P0
- **Estimated Effort**: M

## Proposed Changes

### LLM Client — Streaming Support

#### MODIFY `tinycua_sdk/agent/llm_client.py`

- **[Add `stream` parameter to `LLMClient.chat()` ABC]**: Add `stream: bool = False` to the abstract method signature so all implementations opt in.
- **[Add `stream` parameter to `OpenAICompatibleClient.chat()`]**: Accept `stream: bool = False` and dispatch to `_chat_sync` or `_chat_stream`.
- **[NEW `OpenAICompatibleClient._chat_stream()`]**: Async generator that uses `httpx.AsyncClient.stream()` with `POST /chat/completions` and `stream=True` in payload. Parses SSE `data:` lines, normalising token content deltas and tool call deltas to the event dict shapes defined in the spec.
- **[NEW `OpenAICompatibleClient._chat_sync()`]**: Extract existing non-streaming logic into a private method for clarity.

### Execution Loop — Streaming Support

#### MODIFY `tinycua_sdk/agent/loop.py`

- **[Add `stream` parameter to `BaseLoop.run()`]**: Accept `stream: str = "off"` and dispatch to `_run_sync` or `_run_stream`.
- **[NEW `BaseLoop._run_sync()`]**: Extract the existing synchronous execution logic unchanged (identical to Stage 3 behaviour).
- **[NEW `BaseLoop._run_stream()`]**: Async generator that:
  - Yields `response.created` at start.
  - Calls `agent._call_llm(..., stream=True)` to get an async iter of chunks.
  - Accumulates content parts and tool call parts from the chunk stream.
  - Yields token delta events only in `token`/`all` modes.
  - After full LLM response, emits `response.output_item.added` events for tool calls and tool outputs in `event`/`all` modes.
  - Loops back for next iteration when tool calls are present.
  - Yields `response.completed` at termination.
- **[Return type change]**: `run()` now returns `str | AsyncIterator[dict]` instead of `str`.

### Agent Executor — Streaming Passthrough

#### MODIFY `tinycua_sdk/agent/executor.py`

- **[Add `stream` parameter to `AgentExecutor._call_llm()`]**: Accept `stream: bool = False` and forward to `client.chat()`.

### Agent — Wire Streaming

#### MODIFY `tinycua_sdk/agent/agent.py`

- **[Remove streaming `NotImplementedError`]**: Delete the guard in `Agent.run()` that raises for non-`off` modes.
- **[Wire `stream` to loop]**: Pass the `stream` parameter through to `loop.run()`.
- **[Update return type]**: Change return annotation from `str` to `str | AsyncIterator[dict]`.

### Integration Test

#### NEW `tests/integration/goals/test_gs_04_agent_streaming.py`

- Write integration tests that mock `httpx.AsyncClient.stream` and verify each streaming mode independently:
  - `off`: returns `str`.
  - `token`: yields only `response.output_text.delta` events.
  - `event`: yields only lifecycle/tool events, no delta events.
  - `all`: yields both delta and lifecycle events.
  - Tool call streaming: verify tool_call and tool_output events appear and stream resumes.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `OpenAICompatibleClient` | Modify | Add `stream` param, `_chat_stream()`, `_chat_sync()` |
| `LLMClient` (ABC) | Modify | Add `stream` param to abstract `chat()` |
| `BaseLoop` | Modify | Add `stream` param, `_run_stream()`, `_run_sync()` |
| `AgentExecutor._call_llm` | Modify | Add `stream` param passthrough |
| `Agent.run()` | Modify | Wire streaming, remove NotImplementedError |
| `test_gs_04_agent_streaming.py` | New | Integration tests for all 4 modes |

## API Changes

### Modified Methods

| Method | Change |
|--------|--------|
| `LLMClient.chat()` | Added `stream: bool = False` parameter |
| `OpenAICompatibleClient.chat()` | Added `stream` param, returns `dict` or `AsyncIterator[dict]` |
| `BaseLoop.run()` | Added `stream: str = "off"` param, returns `str` or `AsyncIterator[dict]` |
| `AgentExecutor._call_llm()` | Added `stream: bool = False` parameter |
| `Agent.run()` | Removes `NotImplementedError` for streaming, returns `str` or `AsyncIterator[dict]` |

## Verification Plan

### Automated Tests

- [ ] Unit tests: `LLMClient` SSE parsing (token deltas, tool call deltas, [DONE] sentinel)
- [ ] Unit tests: `BaseLoop._run_stream()` with mocked LLM for each mode
- [ ] Unit tests: `Agent.run()` streaming return types
- [ ] Integration tests: `test_gs_04_agent_streaming.py` — all 6 success criteria from spec

### Manual Verification

- [ ] Run `pytest tests/integration/goals/test_gs_04_agent_streaming.py` — 1 passed, 0 failed
- [ ] Run `make lint` — no errors
- [ ] Run `make complexity` — within limits

## Dependencies

### Internal Dependencies

- Depends on Stages 0–4 (execution loop, tool calling, LLM client all exist).

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Partial tool call JSON across SSE chunks | Medium | Accumulate tool call deltas in buffer before parsing |
| httpx stream context manager resource leak | Medium | Use `async with` properly; test with mocked responses |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-07*
