# Tasks: Stage 5 — Streaming

Implementation tasks for adding raw SSE passthrough streaming to the agent execution loop and LLM client. Check off items as completed.

## Implementation Phase

- [x] Update `LLMClient` ABC — add `stream: bool = False` to `chat()` signature <!-- id: 0 -->
  - [x] Add `stream` parameter to abstract method
  - [x] Update `OpenAICompatibleClient` to match new signature
- [x] Implement `OpenAICompatibleClient._chat_stream()` — SSE-based async generator <!-- id: 1 -->
  - [x] Parse SSE `data:` lines, skip `[DONE]`
  - [x] Normalise content deltas to `response.output_text.delta` events
  - [x] Normalise tool call deltas to `response.tool_call.delta` events
  - [x] Extract existing non-streaming logic into `_chat_sync()`
- [x] Update `BaseLoop.run()` — add `stream: bool = False` parameter <!-- id: 2 -->
  - [x] Dispatch to `_run_sync()` or `_run_stream()`
  - [x] Extract existing loop body into `_run_sync()`
- [x] Implement `BaseLoop._run_stream()` — raw passthrough async generator <!-- id: 3 -->
  - [x] Yield `response.created` at start
  - [x] Call `agent._call_llm(..., stream=True)` for LLM streaming
  - [x] Yield every chunk as-is (no mode filtering)
  - [x] Accumulate content/tool call parts from chunk stream
  - [x] Execute tools silently (no synthetic events)
  - [x] Accumulate cumulative usage across iterations
  - [x] Loop back when tool calls present, break for final content
  - [x] Yield cumulative `response.usage` at end
  - [x] Yield `response.completed` at termination
- [x] Update `AgentExecutor._call_llm()` — add `stream: bool = False` passthrough <!-- id: 4 -->
- [x] Wire streaming in `Agent.run()` — `stream: bool = False`, remove mode validation <!-- id: 5 -->

## Testing Phase

- [x] Write unit tests for `LLMClient` SSE streaming (mock httpx stream) <!-- id: 6 -->
  - [x] Test token delta parsing
  - [x] Test tool call delta parsing
  - [x] Test `[DONE]` sentinel handling
- [x] Write unit tests for `BaseLoop._run_stream()` (mock LLM responses) <!-- id: 7 -->
  - [x] Test raw event passthrough
  - [x] Test tool-call streaming (pause, execute, resume)
- [x] Write unit tests for `Agent.run()` streaming return types <!-- id: 8 -->
- [x] Update integration test file `tests/integration/goals/test_gs_04_agent_streaming.py` <!-- id: 9 -->
  - [x] `stream=False` returns `str`
  - [x] `stream=True` yields raw events

## Verification Phase

- [x] Run `make lint` — no errors <!-- id: 10 -->
- [x] Run full test suite (`make test`) — all tests pass <!-- id: 11 -->
- [x] Run `make complexity` — within limits <!-- id: 12 -->

## Review and Merge

- [ ] Create pull request <!-- id: 13 -->
- [ ] Address review feedback <!-- id: 14 -->
- [ ] Merge to main branch <!-- id: 15 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-08*
