# Models Documentation

The `models/` package defines data models for requests, responses, results, and tasks using Pydantic and dataclasses.

**Package path:** `tinycua_sdk/models/`

---

## request.py - Request Models

### Purpose

Defines models for API requests to LLM providers.

### Message

```python
class Message(BaseModel):
    role: str
    content: str
```

Simple message model for conversation entries. Used in `ResponseRequest.input`.

### ToolDefinition

```python
class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    
    def to_config(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
```

Converts to OpenAI function-calling format:
```json
{
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "Does something",
        "parameters": {"type": "object", "properties": {...}}
    }
}
```

### ResponseRequest

```python
class ResponseRequest(BaseModel):
    model: str
    input: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[Any] = Field(default_factory=list)
    temperature: float = 1.0
    max_tokens: int | None = None
    stream: bool = False
    session_id: str | None = None
```

**Fields:**
- `model`: LLM model identifier (e.g., "gpt-4o-mini")
- `input`: List of message dicts (OpenAI chat format)
- `tools`: Tool definitions (accepts `ToolDefinition` or raw dicts)
- `temperature`: Sampling temperature (0.0-2.0)
- `max_tokens`: Maximum tokens to generate
- `stream`: Whether to stream the response
- `session_id`: For server-orchestrated mode

**Why `list[Any]` for tools?** The runner may pass `Tool` objects or dicts. Pydantic will validate dicts but pass through objects.

---

## response.py - Response Models

### Purpose

Defines models for API responses and streaming events.

### Usage

```python
class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
```

Token usage tracking. `total_tokens` is typically `input_tokens + output_tokens`.

### Response

```python
class Response(BaseModel):
    id: str
    model: str
    choices: list[dict[str, Any]] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
```

**choices format:**
```python
[
    {
        "message": {
            "role": "assistant",
            "content": "Hello!",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "my_tool",
                        "arguments": '{"param": "value"}'
                    }
                }
            ]
        },
        "finish_reason": "stop"
    }
]
```

### StreamEventType (Enum)

```python
class StreamEventType(str, Enum):
    # Content/Response events
    CONTENT = "content"
    DONE = "done"
    
    # Tool call events
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_CHUNK = "tool_call_chunk"
    TOOL_CALL_END = "tool_call_end"
    
    # Tool result events
    TOOL_RESULT_START = "tool_result_start"
    TOOL_RESULT_CHUNK = "tool_result_chunk"
    TOOL_RESULT_END = "tool_result_end"
    
    # Delegation events
    DELEGATION_START = "delegation_start"
    DELEGATION_END = "delegation_end"
    
    # LLM events
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    
    # Loop events
    LOOP_LOG = "loop_log"
    LOOP_START = "loop_start"
    LOOP_END = "loop_end"
    
    # Error events
    ERROR = "error"
```

**Event categories:**
- **Content:** Final LLM output tokens
- **Tool:** Tool call and result streaming
- **Delegation:** Sub-agent delegation events
- **LLM:** Raw request/response logging
- **Loop:** Custom loop log messages
- **Error:** Error notifications

### StreamEvent

```python
class StreamEvent(BaseModel):
    type: StreamEventType
    data: dict[str, Any] = Field(default_factory=dict)
    
    def to_sse(self) -> str:
        return f"data: {json.dumps({'type': self.type.value, **self.data})}\n\n"
    
    @classmethod
    def from_sse(cls, data: str) -> "StreamEvent":
        if data.startswith("data: "):
            data = data[6:]
        parsed = json.loads(data)
        return cls(type=StreamEventType(parsed.pop("type")), data=parsed)
```

**SSE conversion:**
- `to_sse()`: Converts to Server-Sent Events format (`data: {...}\n\n`)
- `from_sse()`: Parses SSE data back into `StreamEvent`

**Why SSE format?** Standard for HTTP streaming. Compatible with EventSource browsers and various HTTP clients.

---

## result.py - Result Models

### Purpose

Defines result models for runner execution with trace data.

### ToolCall

```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    result: Any = None
```

Represents a single tool invocation with its result.

### RunResult

```python
@dataclass
class RunResult:
    response: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    
    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)
    
    @property
    def input_tokens(self) -> int:
        return self.usage.get("input_tokens", 0)
    
    @property
    def output_tokens(self) -> int:
        return self.usage.get("output_tokens", 0)
```

**Trace data structure:**
```python
trace = [
    {
        "request": {"model": "gpt-4o-mini", "messages": [...], "tools": [...]},
        "response": {"id": "...", "choices": [...], "usage": {...}},
        "usage": {"input_tokens": 100, "output_tokens": 50},
    },
    # One entry per LLM call
]
```

**Properties:** Convenience accessors for token counts from the usage dict.

### PlanRunResult

```python
@dataclass
class PlanRunResult(RunResult):
    plan: dict[str, Any] = field(default_factory=dict)
    todo_items: list[dict[str, Any]] = field(default_factory=list)
```

Extends `RunResult` with planning-specific fields for agents that use task planning mode.

---

## task.py - Task Planning Models

### Purpose

Defines models for task planning and todo list management.

### TodoItem

```python
@dataclass
class TodoItem:
    id: str
    description: str
    status: str = "pending"
    tool_name: str | None = None
    tool_args: dict = field(default_factory=dict)
    result: Any = None
```

Represents a single task in a plan:
- `id`: Unique identifier
- `description`: Human-readable task description
- `status`: "pending", "in_progress", "completed", "failed"
- `tool_name`: Optional tool to execute for this task
- `tool_args`: Arguments for the tool
- `result`: Outcome after execution

### TaskPlan

```python
@dataclass
class TaskPlan:
    main_task: str
    todo: list[TodoItem] = field(default_factory=list)
```

Container for a task plan with a main objective and todo list.

### PlanningResult

```python
@dataclass
class PlanningResult:
    plan: TaskPlan
    final_response: str
```

Result from planning execution, containing both the plan and the agent's final response.

---

## Inter-Module Data Flow

### Request Building Flow
```
Runner._chat_direct()
  → ResponseRequest(
      model=self.model,
      input=messages,
      tools=tool_configs,
    )
    → Pydantic validation
    → Converted to dict for httpx
```

### Response Parsing Flow
```
httpx response
  → response.json()
  → Response(
      id=data.get("id", ""),
      model=data.get("model", ""),
      choices=data.get("choices", []),
      usage=Usage(**usage_data),
    )
```

### Streaming Event Flow
```
SSE line from LLM
  → json.loads(line[6:])
  → StreamEvent(
      type=StreamEventType.CONTENT,
      data=event_data,
    )
  → Yield to caller
```

### Trace Data Flow
```
Runner execution
  → For each LLM call:
    → Append {
        "request": request.model_dump(),
        "response": response.model_dump(),
        "usage": usage_data,
      } to trace_data
  → Return RunResult(trace=trace_data)
```
