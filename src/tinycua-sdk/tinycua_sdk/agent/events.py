"""TypedDict definitions for agent event shapes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class ResponseCreatedEvent(TypedDict):
    """Emitted at the start of every stream session."""

    type: Literal["response.created"]


class ResponseCancelledEvent(TypedDict):
    """Emitted when the agent is cancelled during streaming."""

    type: Literal["response.cancelled"]


class ResponseFailedEvent(TypedDict):
    """Emitted when an exception occurs during streaming."""

    type: Literal["response.failed"]
    error: dict[str, str]


class ErrorEvent(TypedDict):
    """Emitted for transient errors during streaming."""

    type: Literal["error"]
    error: dict[str, str]


class ResponseCompletedEvent(TypedDict):
    """Emitted at the end of a successful stream session."""

    type: Literal["response.completed"]
    finish_reason: str


class ResponseUsageEvent(TypedDict):
    """Emitted with token usage data from the LLM."""

    type: Literal["response.usage"]
    usage: dict[str, Any]


class ResponseOutputTextDeltaEvent(TypedDict):
    """Emitted for each text content delta in streaming."""

    type: Literal["response.output_text.delta"]
    delta: str
    item_id: str


class ResponseToolCallDeltaEvent(TypedDict):
    """Emitted for each tool call argument delta in streaming."""

    type: Literal["response.tool_call.delta"]
    index: int
    id: str
    name: str
    arguments: str


class ToolCallStartedEvent(TypedDict):
    """Emitted when a new tool call starts in the stream."""

    type: Literal["tool_call.started"]
    id: str
    call_id: str
    name: str


class ToolCallArgumentsDeltaEvent(TypedDict):
    """Emitted for tool call arguments delta in the stream."""

    type: Literal["tool_call.arguments.delta"]
    id: str
    arguments: str


class ToolCallArgumentsDoneEvent(TypedDict):
    """Emitted when tool call arguments are complete."""

    type: Literal["tool_call.arguments.done"]
    id: str
    arguments: str


class ResponseFunctionCallArgumentsDeltaEvent(TypedDict):
    """Emitted for each function call argument delta in streaming (raw provider event)."""

    type: Literal["response.function_call_arguments.delta"]
    item_id: str
    delta: str


class ResponseFunctionCallArgumentsDoneEvent(TypedDict):
    """Emitted when function call arguments are complete (raw provider event)."""

    type: Literal["response.function_call_arguments.done"]
    item_id: str
    arguments: str


class ResponseOutputItemAddedEvent(TypedDict):
    """Emitted when a new output item is added during streaming (raw provider event)."""

    type: Literal["response.output_item.added"]
    item: dict


class ResponseInProgressEvent(TypedDict):
    """Emitted after response.created when streaming is active."""

    type: Literal["response.in_progress"]


__all__ = [
    "ResponseCreatedEvent",
    "ResponseCancelledEvent",
    "ResponseFailedEvent",
    "ErrorEvent",
    "ResponseCompletedEvent",
    "ResponseUsageEvent",
    "ResponseOutputTextDeltaEvent",
    "ResponseToolCallDeltaEvent",
    "ToolCallStartedEvent",
    "ToolCallArgumentsDeltaEvent",
    "ToolCallArgumentsDoneEvent",
    "ResponseFunctionCallArgumentsDeltaEvent",
    "ResponseFunctionCallArgumentsDoneEvent",
    "ResponseOutputItemAddedEvent",
    "ResponseInProgressEvent",
]
