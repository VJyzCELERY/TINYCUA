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


class ResponseFunctionCallArgumentsDeltaEvent(TypedDict):
    """Emitted for each function call argument delta in streaming."""

    type: Literal["response.function_call_arguments.delta"]
    item_id: str
    delta: str


class ResponseFunctionCallArgumentsDoneEvent(TypedDict):
    """Emitted when function call arguments are complete."""

    type: Literal["response.function_call_arguments.done"]
    item_id: str
    arguments: str


class ResponseOutputItemAddedEvent(TypedDict):
    """Emitted when a new output item is added during streaming."""

    type: Literal["response.output_item.added"]
    item: dict


__all__ = [
    "ResponseCreatedEvent",
    "ResponseCancelledEvent",
    "ResponseFailedEvent",
    "ErrorEvent",
    "ResponseCompletedEvent",
    "ResponseUsageEvent",
    "ResponseOutputTextDeltaEvent",
    "ResponseToolCallDeltaEvent",
    "ResponseFunctionCallArgumentsDeltaEvent",
    "ResponseFunctionCallArgumentsDoneEvent",
    "ResponseOutputItemAddedEvent",
]
