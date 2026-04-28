# Tool Streaming Specification

**Feature**: Streaming Tool Execution
**Status**: In Progress
**Last Updated**: 2026-03-16

---

## Overview

Enable token-by-token streaming of both LLM responses AND tool execution results. The LLM should be able to see tool results streaming in, enabling real-time feedback for long-running operations.

---

## Requirements

### FR-030: Streaming Tool Execution

The runner MUST support streaming tool execution results while maintaining the response stream.

### FR-031: Event Types

The streaming response MUST include these event types:
- `content`: Regular text token from LLM
- `tool_call_start`: LLM is requesting a tool call
- `tool_call_chunk`: Tool arguments streaming in
- `tool_call_end`: Tool call ready to execute
- `tool_result_start`: Starting tool execution
- `tool_result_chunk`: Tool result token-by-token
- `tool_result_end`: Tool execution complete
- `done`: Response complete

### FR-032: Async Generator Tools

Tools MAY return an async generator for streaming results. Tools that return regular values MUST be wrapped to support chunked streaming.

### FR-033: Backward Compatibility

The existing `runner.stream()` method MUST continue to return `AsyncIterator[str]` for backward compatibility.

### FR-034: Agent Integration

`agent.stream()` MUST automatically handle tool execution and yield full event objects with type information.

---

## API Design

### StreamEventType Enum

```python
class StreamEventType(Enum):
    CONTENT = "content"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_CHUNK = "tool_call_chunk"
    TOOL_CALL_END = "tool_call_end"
    TOOL_RESULT_START = "tool_result_start"
    TOOL_RESULT_CHUNK = "tool_result_chunk"
    TOOL_RESULT_END = "tool_result_end"
    DONE = "done"
```

### StreamEvent Model

```python
@dataclass
class StreamEvent:
    type: StreamEventType
    data: dict[str, Any]  # Flexible payload per event type

    # Content event
    # data = {"content": "text token"}

    # Tool call events
    # data = {"tool_call_id": "xxx", "tool_name": "func", "arguments": "..."}

    # Tool result events
    # data = {"tool_call_id": "xxx", "tool_name": "func", "content": "result chunk"}
```

### Runner Interface

```python
class Runner:
    # Existing - returns strings
    async def stream(
        self, user_input: str, instructions: str | None = None
    ) -> AsyncIterator[str]:
        ...

    # New - returns events
    async def stream_with_tools(
        self, user_input: str, instructions: str | None = None
    ) -> AsyncIterator[StreamEvent]:
        ...
```

---

## Tool Interface

### Regular Tool (non-streaming)

```python
@tool()
def get_weather(location: str) -> dict:
    """Get weather for a location."""
    return {"temp": 22, "condition": "sunny"}
```

### Streaming Tool

```python
@tool()
async def run_command(cmd: str) -> AsyncIterator[str]:
    """Run command with streaming output."""
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    async for line in process.stdout:
        yield line.decode()
```

---

## Implementation Notes

1. **OpenAI-compatible endpoint limitation**: Some providers may not support mid-stream tool calls. Fall back to accumulating full response before executing tools.

2. **Chunking**: For non-streaming tools, wrap result string and yield in chunks (e.g., 10 chars at a time).

3. **Error handling**: Stream error messages as tool results on failure.

4. **Sequential execution**: Multiple tool calls execute sequentially, streaming each result before the next.

---

## Status

| Component | Status |
|-----------|--------|
| StreamEventType enum | ⏳ |
| StreamEvent model | ⏳ |
| Runner.stream_with_tools() | ⏳ |
| Async generator tool support | ⏳ |
| Agent.stream() update | ⏳ |
| Tests | ⏳ |

---

## Related

- [design.md](design.md) - Implementation details
- [spec.md](../spec.md) - Main SDK spec
