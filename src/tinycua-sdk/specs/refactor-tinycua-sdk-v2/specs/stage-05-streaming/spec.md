# Stage 5: Streaming — Specification

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
