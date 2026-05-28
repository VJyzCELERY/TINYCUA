"""Response models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Usage(BaseModel):
    """Token usage information."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class MessageItem(BaseModel):
    """A message in the response."""

    type: str = "message"
    role: str
    content: list[dict[str, Any]] = Field(default_factory=list)


class FunctionCall(BaseModel):
    """A function call in the response."""

    type: str = "function_call"
    name: str
    arguments: str
    call_id: str


class FunctionCallOutput(BaseModel):
    """Output from a function call."""

    type: str = "function_call_output"
    call_id: str
    output: str


class OutputItem(BaseModel):
    """An output item in the response."""

    type: str
    id: str | None = None


class Response(BaseModel):
    """Response from the API."""

    id: str
    model: str
    choices: list[dict[str, Any]] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)


class StreamEventType(str, Enum):
    """Types of streaming events."""

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

    # Delegation events (for sub-agents)
    DELEGATION_START = "delegation_start"
    DELEGATION_END = "delegation_end"

    # LLM request/response events
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"

    # Loop custom events
    LOOP_LOG = "loop_log"
    LOOP_START = "loop_start"
    LOOP_END = "loop_end"

    # Error events
    ERROR = "error"


class StreamEvent(BaseModel):
    """A streaming event with type and data."""

    type: StreamEventType
    data: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        """Convert event to SSE format for remote passthrough."""
        import json

        return f"data: {json.dumps({'type': self.type.value, **self.data})}\n\n"

    @classmethod
    def from_sse(cls, data: str) -> "StreamEvent":
        """Parse event from SSE data."""
        import json

        if data.startswith("data: "):
            data = data[6:]
        parsed = json.loads(data)
        return cls(type=StreamEventType(parsed.pop("type")), data=parsed)


__all__ = [
    "Usage",
    "MessageItem",
    "FunctionCall",
    "FunctionCallOutput",
    "OutputItem",
    "Response",
    "StreamEvent",
]
