# Stage 5: Streaming — Specification

**Status**: Complete
**Created**: 2026-05-02
**Last Updated**: 2026-05-08
**Subproject(s) Affected**: tinycua-sdk

## Objective
Implement raw SSE passthrough streaming — `stream=False` returns `str`, `stream=True` returns `AsyncIterator[dict]` of raw OpenAI SSE events.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

## Reference
- [`goals/getting-started/04_agent_streaming.py`](../goals/getting-started/04_agent_streaming.py)

## Requirements

### R-5.1: Streaming Mode

| Mode | Return Type | Content |
|------|-------------|---------|
| `stream=False` | `str` | Final response text (default). |
| `stream=True` | `AsyncIterator[dict]` | Raw OpenAI SSE events from the LLM, plus lifecycle bookends (response.created/response.completed). |

### R-5.2: Event Passthrough

When `stream=True`, provider SSE events are forwarded to the consumer as-is (no filtering). The loop may inject documented lifecycle bookends (`response.created`/`response.completed`/`response.failed`/`response.cancelled`/`error`) and a final cumulative `response.usage` event.

**Raw LLM events** (passthrough from provider):
```python
{"type": "response.output_text.delta", "delta": "Hello", "item_id": "msg_abc123"}
{"type": "response.tool_call.delta", "index": 0, "id": "call_1", "name": "get_time", "arguments": "{}"}
{"type": "response.usage", "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
```

**Lifecycle events** (emitted by the loop):
```python
{"type": "response.created"}
{"type": "response.completed", "finish_reason": "completed"}
{"type": "response.failed", "error": {"message": "..."}}
{"type": "response.cancelled"}
{"type": "error", "error": {"message": "..."}}
```

### R-5.2.0: OpenAI Responses API Event Type Reference

All streaming events follow the OpenAI Responses API SSE event format. Each event is a JSON dict with a `type` field identifying the event kind.

| Event Type | Implemented | Stage | Description |
|---|---|---|---|
| `response.created` | ✅ | 5 | Emitted once when the response is created. |
| `response.in_progress` | ❌ Deferred | 8 | Response is being processed. |
| `response.output_text.delta` | ✅ | 5 | Text content delta chunk (passthrough from LLM). |
| `response.output_text.done` | ❌ Removed | — | No longer emitted — consumers track completion via the end of delta stream or response.completed. |
| `response.output_text.annotation.added` | ❌ Deferred | 9 | Citation/annotation on text output. |
| `response.output_item.added` | ✅ Handled | 5 | Passthrough — handled for `function_call` items from provider. |
| `response.output_item.done` | ❌ Removed | — | No longer emitted — synthetic events removed in favor of raw passthrough. |
| `response.content_part.added` | ❌ Deferred | 9 | Content part added (multi-part responses). |
| `response.content_part.done` | ❌ Deferred | 9 | Content part complete. |
| `response.function_call_arguments.delta` | ✅ Implemented | 5 | Tool call argument delta accumulation. |
| `response.function_call_arguments.done` | ✅ Implemented | 5 | Tool call argument completion. |
| `response.completed` | ✅ | 5 | Response completed successfully. |
| `response.failed` | ✅ | 5 | Response failed with error details. |
| `error` | ✅ | 5 | Transient streaming error event. |
| `response.usage` | ✅ | 5 | Cumulative token usage emitted at end of stream (plus raw events forwarded during stream). |
| `response.cancelled` | ✅ | 5 | Emitted when the agent is cancelled during streaming. |

### R-5.2.3: response.failed / error Events

Emitted when the response fails due to an error (tool execution failure, stream error, etc.).

```python
{
    "type": "response.failed",
    "error": {"message": "Tool execution failed: ..."},
}
{"type": "error", "error": {"message": "Tool execution failed: ..."}}
```

### R-5.3: Behavior with Tool Calls
When the LLM returns tool calls during a stream:
- Raw tool_call.delta events passthrough to the consumer.
- The stream pauses while tools execute (no synthetic events are emitted for tool calls or results).
- Tool results are appended to the message list for the next LLM iteration.
- The stream resumes with the next LLM response's raw events.

### R-5.4: Loop Integration
- `BaseLoop.run()` must support streaming by yielding raw LLM events instead of returning a single string when `stream=True`.
- The same tool-calling logic from Stage 3 runs, but events are yielded raw at each stage.

### R-5.5: LLMClient Streaming
- `OpenAICompatibleClient.chat()` must accept `stream: bool = False`.
- When `stream=True`, it returns an async generator of SSE chunks.
- Each chunk is normalized to the same event dict shape.

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] stream=False Returns String - tests/integration/goals/test_gs_04_agent_streaming.py - PASS - `print('PASS')`
  Description: Default mode returns `str`.

- [ ] stream=True Yields Raw Events - tests/integration/goals/test_gs_04_agent_streaming.py - PASS - `print('PASS')`
  Description: Returns async iterator with raw SSE events.

- [ ] Integration Test Pass - tests/integration/goals/test_gs_04_agent_streaming.py - 1 passed, 0 failed - pytest -v

## Integration Test File
- `tests/integration/goals/test_gs_04_agent_streaming.py`
