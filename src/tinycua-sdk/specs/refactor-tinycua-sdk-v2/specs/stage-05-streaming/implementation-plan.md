# Implementation: Stage 5 — Streaming

Add raw SSE passthrough streaming (`stream: bool = False` → `str`, `stream=True` → raw `AsyncIterator[dict]`).

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
- **[NEW `OpenAICompatibleClient._chat_stream()`]**: Async generator that uses `httpx.AsyncClient.stream()` with `POST /responses` and `stream=True` in payload. Yields raw SSE events from the Responses API stream (all events include a `type` field: `response.output_text.delta`, `response.tool_call.delta`, `response.usage`, etc.).
- **[NEW `OpenAICompatibleClient._chat_sync()`]**: Extract existing non-streaming logic into a private method for clarity.

### Execution Loop — Streaming Support

#### MODIFY `tinycua_sdk/agent/loop.py`

- **[Add `stream` parameter to `BaseLoop.run()`]**: Accept `stream: bool = False` and dispatch to `_run_sync` or `_run_stream`.
- **[NEW `BaseLoop._run_sync()`]**: Extract the existing synchronous execution logic unchanged.
- **[NEW `BaseLoop._run_stream()`]**: Async generator that:
  - Yields `response.created` at start.
  - Calls `agent._call_llm(..., stream=True)` to get an async iter of chunks.
  - Yields every chunk as-is (raw passthrough, no mode filtering).
  - Accumulates content parts, tool call parts, and usage from the chunk stream.
  - After LLM response, executes tools and appends results to messages (no synthetic events).
  - Loops back for next iteration when tool calls are present.
  - Emits cumulative `response.usage` at termination.
  - Yields `response.completed` at termination.
- **[Return type change]**: `run()` now returns `str | AsyncIterator[dict]` instead of `str`.
- **[Remove `_build_tool_events`]**: No longer needed — no synthetic tool events.
- **[Remove `stream_mode`]**: No mode filtering — all events passthrough.

### Agent Executor — Streaming Passthrough

#### MODIFY `tinycua_sdk/agent/executor.py`

- **[Add `stream` parameter to `AgentExecutor._call_llm()`]**: Accept `stream: bool = False` and forward to `client.chat()`.

### Agent — Wire Streaming

#### MODIFY `tinycua_sdk/agent/agent.py`

- **[Remove streaming `NotImplementedError`]**: Delete the guard in `Agent.run()` that raises for non-`off` modes.
- **[Wire `stream` to loop]**: Pass the `stream` parameter through to `loop.run()`.
- **[Update return type]**: Change return annotation from `str` to `str | AsyncIterator[dict]`.

### Integration Test

#### MODIFY `tests/integration/goals/test_gs_04_agent_streaming.py`

- Update to use `stream=True` / `stream=False` instead of mode strings.
- Verify raw event passthrough (deltas, lifecycle events, usage).

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `OpenAICompatibleClient` | Modify | Add `stream` param, `_chat_stream()`, `_chat_sync()` |
| `LLMClient` (ABC) | Modify | Add `stream` param to abstract `chat()` |
| `BaseLoop` | Modify | Add `stream` param, `_run_stream()`, raw passthrough, cumulative usage |
| `AgentExecutor._call_llm` | Modify | Add `stream` param passthrough |
| `Agent.run()` | Modify | Wire streaming, `stream: bool`, remove mode validation |

## API Changes

### Modified Methods

| Method | Change |
|--------|--------|
| `LLMClient.chat()` | Added `stream: bool = False` parameter |
| `OpenAICompatibleClient.chat()` | Added `stream` param, returns `dict` or `AsyncIterator[dict]` |
| `BaseLoop.run()` | Added `stream: bool = False` param, returns `str` or `AsyncIterator[dict]` |
| `AgentExecutor._call_llm()` | Added `stream: bool = False` parameter |
| `Agent.run()` | `stream: bool = False`, removes mode validation |

## Verification Plan

### Automated Tests

- [x] Unit tests: `LLMClient` SSE parsing (token deltas, tool call deltas, [DONE] sentinel)
- [x] Unit tests: `BaseLoop._run_stream()` with mocked LLM for raw passthrough
- [x] Unit tests: `Agent.run()` streaming return types
- [x] Integration tests: `test_gs_04_agent_streaming.py` — stream=False and stream=True

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
*Last updated: 2026-05-08*
