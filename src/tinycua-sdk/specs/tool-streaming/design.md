# Tool Streaming Design

**Feature**: Streaming Tool Execution
**Status**: In Progress
**Created**: 2026-03-16

---

## Problem Statement

Currently, the `.stream()` method only yields assistant text tokens. Tools are executed **after** the LLM responds, blocking until complete. This prevents real-time feedback for long-running tools.

**Goal**: Allow tool execution results to stream token-by-token while maintaining the streaming response flow.

---

## Architecture

### Current Flow

```
User Input → LLM (streaming tokens) → [tool_calls detected] → Execute tools (blocking) → Final Response
```

### New Flow with Tool Streaming

```
User Input → LLM (streaming) 
           → [tool_calls detected mid-stream] 
           → Execute tool (streaming results) 
           → Continue LLM streaming 
           → Final Response
```

### Event Types

The streaming response will yield different event types:

| Event Type | Description |
|------------|-------------|
| `content` | Regular text token from LLM |
| `tool_call_start` | LLM is requesting a tool call |
| `tool_call_chunk` | Tool call arguments (streaming in) |
| `tool_call_end` | Tool call complete, ready to execute |
| `tool_result_start` | Starting tool execution |
| `tool_result_chunk` | Tool result streaming token-by-token |
| `tool_result_end` | Tool execution complete |
| `done` | Response complete |

---

## Implementation

### Runner Changes

```python
class Runner:
    async def stream_with_tools(
        self, user_input: str, instructions: str | None = None
    ) -> AsyncIterator[StreamEvent]:
        """Stream response with tool execution."""
        
        # Phase 1: Initial LLM streaming
        async for event in self._stream_llm_response():
            if event.type == "tool_call":
                # Store tool call, don't yield yet
                self._accumulate_tool_call(event)
            else:
                yield event
        
        # Phase 2: Execute tools and stream results
        for tool_call in self._pending_tool_calls:
            yield StreamEvent(type="tool_result_start", tool_name=tool_call.name)
            
            # Execute tool (can be async generator for streaming)
            result = self._execute_tool_streaming(tool_call.name, tool_call.args)
            
            async for result_chunk in result:
                yield StreamEvent(type="tool_result_chunk", content=result_chunk)
            
            yield StreamEvent(type="tool_result_end", tool_name=tool_call.name)
        
        # Phase 3: Continue LLM with tool results
        async for event in self._stream_llm_continue():
            yield event
```

### Tool Interface Updates

Tools can optionally return async generators for streaming results:

```python
@tool()
def run_command(cmd: str) -> AsyncIterator[str]:
    """Run shell command with streaming output."""
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE
    )
    async for line in process.stdout:
        yield line.decode()

# Or regular function (gets wrapped)
@tool()
def get_weather(location: str) -> dict:
    return {"temp": 22, "condition": "sunny"}
```

### StreamEvent Model

```python
from enum import Enum
from typing import Any

class StreamEventType(Enum):
    CONTENT = "content"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_CHUNK = "tool_call_chunk"
    TOOL_CALL_END = "tool_call_end"
    TOOL_RESULT_START = "tool_result_start"
    TOOL_RESULT_CHUNK = "tool_result_chunk"
    TOOL_RESULT_END = "tool_result_end"
    DONE = "done"

@dataclass
class StreamEvent:
    type: StreamEventType
    data: dict[str, Any]  # Contains content, tool_name, tool_call_id, etc.
```

---

## API Changes

### Runner.stream() Enhancement

```python
# Current (unchanged for backward compatibility)
async for token in runner.stream("Hello"):
    print(token, end="")

# New (with tools)
async for event in runner.stream_with_tools("Run ls -la"):
    if event.type == "content":
        print(event.data["content"], end="")
    elif event.type == "tool_result_chunk":
        print(event.data["content"], end="")
```

### Agent.stream() Enhancement

```python
# Agent.stream() should automatically handle tools
async for event in agent.stream("Run a long command"):
    print(event)  # Full event with type info
```

---

## Edge Cases

1. **Multiple tool calls**: Execute sequentially, stream each result
2. **Tool without streaming support**: Wrap result in chunks
3. **Tool error**: Stream error message as result
4. **No tools provided**: Fall back to simple token streaming
5. **Plan mode + streaming**: Handle plan mode specially (not supported initially)

---

## Backward Compatibility

- `runner.stream()` returns `AsyncIterator[str]` (existing behavior)
- New method: `runner.stream_with_tools()` returns `AsyncIterator[StreamEvent]`
- Agent handles this internally

---

## Testing Plan

1. Simple text streaming (no tools)
2. Tool call detection during stream
3. Tool result streaming (for async generator tools)
4. Multiple tool calls
5. Tool error handling
6. Backward compatibility

---

## Status

- [ ] Runner: Add stream_with_tools() method
- [ ] StreamEvent model with proper types
- [ ] Tool execution: Support async generators
- [ ] Agent: Update stream() to use stream_with_tools
- [ ] Tests
