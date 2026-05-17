"""Canonical TypedDict definitions for agent event shapes and input types.

This module defines the canonical SSE event schema (provider-agnostic),
canonical input message types, and related type aliases for the TINYCUA SDK.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict, Union

# ── Canonical SSE Events ────────────────────────────────────────────────────


class ContentDeltaEvent(TypedDict):
    """Emitted for each text content delta in streaming."""

    type: Literal["content.delta"]
    delta: str
    index: int


class ContentDoneEvent(TypedDict):
    """Emitted when a text content block is complete."""

    type: Literal["content.done"]
    index: int


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
    ResponseFailedEvent,
]

# ── Non-streaming response type ─────────────────────────────────────────────


class LLMResponse(TypedDict):
    """Canonical non-streaming LLM response shape."""

    content: str | None
    tool_calls: list[dict[str, Any]] | None
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
    """User message."""

    role: Literal["user"]
    content: str


class AssistantMessage(TypedDict):
    """Assistant response message."""

    role: Literal["assistant"]
    content: str | None


class ToolResultMessage(TypedDict):
    """Tool result message."""

    role: Literal["tool_result"]
    call_id: str
    content: str


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
    "ContentDoneEvent",
    # Union type
    "LLMEvent",
    "LLMMessage",
    # Non-streaming response
    "LLMResponse",
    "LLMToolSpec",
    # Raw SSE event
    "RawSseEvent",
    "ResponseCompletedEvent",
    "ResponseFailedEvent",
    "ResponseUsageEvent",
    # Canonical Input Types
    "SystemMessage",
    "TokenUsage",
    "ToolCallArgumentsDeltaEvent",
    "ToolCallArgumentsDoneEvent",
    "ToolCallReadyEvent",
    "ToolCallStartedEvent",
    "ToolResultMessage",
    "UserMessage",
]
