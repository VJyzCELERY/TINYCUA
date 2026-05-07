# Stage 5: Streaming — Specification

**Status**: Draft | In Progress | Complete
**Created**: 2026-05-02
**Last Updated**: 2026-05-02
**Subproject(s) Affected**: tinycua-sdk

## Objective
Implement all four streaming modes exactly as specified.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

## Reference
- [`goals/getting-started/04_agent_streaming.py`](../goals/getting-started/04_agent_streaming.py)

## Requirements

### R-5.1: Streaming Modes

| Mode | Return Type | Content |
|------|-------------|---------|
| `stream="off"` | `str` | Final response text (default). |
| `stream="token"` | `AsyncIterator[dict]` | Raw LLM token deltas only. |
| `stream="event"` | `AsyncIterator[dict]` | Agent-level events only (no token deltas). |
| `stream="all"` | `AsyncIterator[dict]` | Interleaved token deltas + agent events. |

### R-5.2: Event Shapes

**Token delta:**
```python
{
    "type": "response.output_text.delta",
    "delta": "Hello",
    "item_id": "msg_abc123",
}
```

**Agent events:**
```python
{"type": "response.created"}
{"type": "response.output_item.added", "item": {"type": "tool_call", "name": "calculator", "arguments": {"expression": "2+2"}}}
{"type": "response.output_item.added", "item": {"type": "tool_output", "name": "calculator", "output": "4"}}
{"type": "response.completed"}
```

### R-5.2.0: OpenAI Responses API Event Type Reference

All streaming events MUST follow the OpenAI Responses API SSE event format. Each event is a JSON dict with a `type` field identifying the event kind. The table below enumerates all standard OpenAI Responses API event types, annotated with implementation status for this stage.

| Event Type | Implemented | Description |
|---|---|---|
| `response.created` | ✅ | Emitted once when the response is created. |
| `response.in_progress` | ❌ Deferred | Response is being processed. |
| `response.output_text.delta` | ✅ | Text content delta chunk. |
| `response.output_text.done` | ✅ | Text output item complete — contains full accumulated text. |
| `response.output_text.annotation.added` | ❌ Deferred | Citation/annotation on text output. |
| `response.output_item.added` | ✅ | Output item (tool_call, tool_output) added. |
| `response.output_item.done` | ✅ | Output item complete. |
| `response.content_part.added` | ❌ Deferred | Content part added (multi-part responses). |
| `response.content_part.done` | ❌ Deferred | Content part complete. |
| `response.function_call_arguments.delta` | ❌ Deferred | Function call argument delta (standard event; `response.tool_call.delta` is used internally as equivalent). |
| `response.function_call_arguments.done` | ❌ Deferred | Function call arguments complete. |
| `response.completed` | ✅ | Response completed successfully. |
| `response.failed` | ✅ | Response failed with error details. |
| `error` | ✅ | Transient streaming error event. |

Events marked ❌ Deferred are recognized OpenAI standard events that are out of scope for this stage. They MUST be emitted with the correct type string when implemented in future stages to maintain backward compatibility.

### R-5.2.1: response.output_text.done Event

Emitted when a text output item is complete (all delta chunks for that item have been received).

```python
{
    "type": "response.output_text.done",
    "item_id": "msg_abc123",
    "content": "Hello world",
}
```

### R-5.2.2: response.output_item.done Event

Emitted when any output item (text, tool call, tool output) is complete.

```python
{"type": "response.output_item.done", "item": {"type": "text"}}
{"type": "response.output_item.done", "item": {"type": "tool_call", "name": "calculator"}}
{"type": "response.output_item.done", "item": {"type": "tool_output", "name": "calculator"}}
```

### R-5.2.3: response.failed / error Events

Emitted when the response fails due to an error (tool execution failure, stream error, etc.). `response.failed` is the standard OpenAI Responses API error event; `error` is a general-purpose error event for transient issues.

```python
{
    "type": "response.failed",
    "error": {"message": "Tool execution failed: ..."},
}
{"type": "error", "error": {"message": "Tool execution failed: ..."}}
```

### R-5.3: Behavior with Tool Calls
When the LLM returns tool calls during a stream:
- The stream pauses while tools execute.
- Tool call events are emitted.
- Tool output events are emitted.
- The stream resumes with the next LLM response's tokens.

### R-5.4: Loop Integration
- `BaseLoop.run()` must support streaming by yielding events/tokens instead of returning a single string when `stream != "off"`.
- The same tool-calling logic from Stage 3 runs, but events are yielded at each stage.

### R-5.5: LLMClient Streaming
- `OpenAICompatibleClient.chat()` must accept `stream: bool = False`.
- When `stream=True`, it returns an async generator of SSE chunks.
- Each chunk is normalized to the same event dict shape.

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] stream="off" Returns String - tests/integration/goals/test_gs_04_agent_streaming.py - PASS - `print('PASS')`
  Description: Default mode returns `str`.

- [ ] stream="token" Yields Token Deltas - tests/integration/goals/test_gs_04_agent_streaming.py - PASS - `print('PASS: tokens =', tokens)`
  Description: Returns async iterator of token chunks.

- [ ] stream="event" Yields Agent Events - tests/integration/goals/test_gs_04_agent_streaming.py - PASS - `print('PASS: events =', events)`
  Description: Returns async iterator of events without token deltas.

- [ ] stream="all" Yields Both - tests/integration/goals/test_gs_04_agent_streaming.py - PASS - `print('PASS')`
  Description: Interleaved token deltas and events.

- [ ] Streaming with Tool Calls - tests/integration/goals/test_gs_04_agent_streaming.py - PASS - `print('PASS: tool_events =', len(tool_events))`
  Description: Tool call events appear in event/all streams.

- [ ] Integration Test Pass - tests/integration/goals/test_gs_04_agent_streaming.py - 1 passed, 0 failed - pytest -v

## Integration Test File
- `tests/integration/goals/test_gs_04_agent_streaming.py`
