"""Canonical TypedDict definitions for agent event shapes and input types.

This module defines the canonical SSE event schema (provider-agnostic),
canonical input message types, and related type aliases for the TINYCUA SDK.
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict, Union

from tinycua_sdk.models import ContentPart, FileAttachment

# ── Canonical SSE Events ────────────────────────────────────────────────────


class ContentDeltaEvent(TypedDict):
    """Emitted for each text content delta in streaming."""

    type: Literal["response.output_text.delta"]
    delta: str
    index: int


class ContentDoneEvent(TypedDict):
    """Emitted when a text content block is complete."""

    type: Literal["response.output_text.done"]
    index: int


class ToolCallStartedEvent(TypedDict):
    """Emitted when a new tool call starts in the stream."""

    type: Literal["response.output_item.added"]
    id: str
    call_id: str
    name: str


class ToolCallArgumentsDeltaEvent(TypedDict):
    """Emitted for tool call arguments delta in the stream."""

    type: Literal["response.function_call_arguments.delta"]
    id: str
    arguments: str


class ToolCallArgumentsDoneEvent(TypedDict):
    """Emitted when tool call arguments are complete."""

    type: Literal["response.function_call_arguments.done"]
    id: str
    call_id: str
    name: str
    arguments: str


class ToolCallReadyEvent(TypedDict):
    """Emitted when a tool call is fully ready to execute."""

    type: Literal["tool_call.ready"]
    id: str
    call_id: str
    name: str
    arguments: str


class TokenUsage(TypedDict):
    """Token usage summary for an LLM response."""

    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class ToolCallDict(TypedDict):
    """Typed tool call entry within an LLMResponse."""

    id: str
    call_id: str
    name: str
    arguments: str


class ResponseUsageEvent(TypedDict):
    """Emitted with token usage data from the LLM."""

    type: Literal["response.usage"]
    usage: TokenUsage


class ResponseCompletedEvent(TypedDict):
    """Emitted at the end of a successful stream session."""

    type: Literal["response.completed"]
    finish_reason: str


class ResponseFailedEvent(TypedDict):
    """Emitted when an exception occurs during streaming.

    The ``error`` dict preserves original provider error value types
    (e.g. numeric codes, nested objects) — consumer code should handle
    mixed types via ``isinstance`` checks.
    """

    type: Literal["response.failed"]
    error: dict[str, Any]


class ResponseCreatedEvent(TypedDict):
    """Emitted when a response is created at the start of streaming."""

    type: Literal["response.created"]


class ResponseInProgressEvent(TypedDict):
    """Emitted when the response processing is in progress."""

    type: Literal["response.in_progress"]


class ResponseCancelledEvent(TypedDict):
    """Emitted when a streaming response is cancelled."""

    type: Literal["response.cancelled"]


class ErrorEvent(TypedDict):
    """Emitted when an unexpected error occurs during streaming.

    The ``error`` dict preserves original provider error value types
    (e.g. numeric codes, nested objects) — consumer code should handle
    mixed types via ``isinstance`` checks.
    """

    type: Literal["error"]
    error: dict[str, Any]


class ReasoningDeltaEvent(TypedDict):
    """Emitted for each reasoning token delta in streaming.

    Reasoning tokens (chain-of-thought) are produced by models like
    DeepSeek R1, Qwen with reasoning enabled, or OpenAI o-series.
    """

    type: Literal["response.reasoning.delta"]
    delta: str


class ReasoningDoneEvent(TypedDict):
    """Emitted when the reasoning block is complete.

    Marks the end of chain-of-thought output — the stream will
    subsequently emit ``response.output_text.delta`` events for the
    visible response.
    """

    type: Literal["response.reasoning.done"]


# ── LLMEvent union ──────────────────────────────────────────────────────────

LLMEvent = Union[
    ContentDeltaEvent,
    ContentDoneEvent,
    ToolCallStartedEvent,
    ToolCallArgumentsDeltaEvent,
    ToolCallArgumentsDoneEvent,
    ToolCallReadyEvent,
    ResponseUsageEvent,
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseInProgressEvent,
    ResponseCancelledEvent,
    ErrorEvent,
    ResponseFailedEvent,
    ReasoningDeltaEvent,
    ReasoningDoneEvent,
]

# ── Non-streaming response type ─────────────────────────────────────────────


class LLMResponse(TypedDict):
    """Canonical non-streaming LLM response shape."""

    content: str | None
    tool_calls: list[ToolCallDict] | None
    usage: TokenUsage | None
    finish_reason: str | None
    model: str | None


# ── Raw SSE event type ──────────────────────────────────────────────────────


class RawSseEvent(TypedDict):
    """Raw provider SSE event, paired with its canonical form."""

    provider: str
    raw_event: Any


# ── Canonical Input Types ───────────────────────────────────────────────────


class SystemMessage(TypedDict):
    """System instruction message."""

    role: Literal["system"]
    content: str


class UserMessage(TypedDict):
    """User message.

    Content can be a plain string (legacy), a list of multimodal content
    parts (text + file attachments), or a string with a separate
    attachments list.
    """

    role: Literal["user"]
    content: str | list[ContentPart]
    attachments: NotRequired[list[FileAttachment]]


class AssistantMessage(TypedDict):
    """Assistant response message."""

    role: Literal["assistant"]
    content: str | None


class ToolResultMessage(TypedDict):
    """Tool result message.

    Content can be a plain string (legacy), a list of multimodal content
    parts (text + file attachments), or a string with a separate
    attachments list.
    """

    role: Literal["tool_result"]
    call_id: str
    content: str | list[ContentPart]
    attachments: NotRequired[list[FileAttachment]]


LLMMessage = Union[SystemMessage, UserMessage, AssistantMessage, ToolResultMessage]


class LLMToolSpec(TypedDict):
    """Tool specification for LLM function calling."""

    name: str
    description: str
    parameters: dict[str, Any]


# ── Public API ──────────────────────────────────────────────────────────────

__all__ = [
    "AssistantMessage",
    # Canonical SSE Events
    "ContentDeltaEvent",
    "ContentPart",
    "ContentDoneEvent",
    "ErrorEvent",
    # Union type
    "LLMEvent",
    "LLMMessage",
    # Non-streaming response
    "LLMResponse",
    "LLMToolSpec",
    # Raw SSE event
    "RawSseEvent",
    "ReasoningDeltaEvent",
    "ReasoningDoneEvent",
    "ResponseCancelledEvent",
    "ResponseCompletedEvent",
    "ResponseCreatedEvent",
    "ResponseFailedEvent",
    "ResponseInProgressEvent",
    "ResponseUsageEvent",
    # Canonical Input Types
    "SystemMessage",
    "TokenUsage",
    "ToolCallArgumentsDeltaEvent",
    "ToolCallArgumentsDoneEvent",
    "ToolCallDict",
    "ToolCallReadyEvent",
    "ToolCallStartedEvent",
    "ToolResultMessage",
    "UserMessage",
]
