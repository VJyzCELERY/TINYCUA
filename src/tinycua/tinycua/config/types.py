"""Shared node configuration protocol and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from tinycua.models.state_object import StateObject

__all__ = [
    "AgentMonitor",
    "LLMResult",
    "NodeMonitor",
    "StateObject",
    "Tool",
    "ValidationError",
    "ValidationResult",
]


class Tool:
    """Minimal SDK-compatible tool type used by TinyCUA node scopes."""

    def __init__(
        self,
        name: str = "",
        description: str = "",
        parameters: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.description = description or name.replace("_", " ")
        self.parameters = parameters or {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }

    def invoke(self, **kwargs: Any) -> Any:
        """Invoke SDK-style tools through the callable interface."""
        return self(**kwargs)  # type: ignore[misc,operator]


@dataclass
class LLMResult:
    """LLM result type for node LLM invocations.

    Contains the assistant's response content and metadata.

    Attributes:
        content: The assistant's response content.
        role: The role of the message (default: "assistant").
        tool_calls: Optional list of tool calls in the response.
        metadata: Optional metadata about the LLM response.
    """

    content: str = ""
    role: str = "assistant"
    tool_calls: list[dict] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    # Reasoning content from reasoning models (Qwen3/DeepSeek/etc.). Preserved
    # and re-injected as reasoning_content on the next turn's assistant message
    # for multi-turn coherency (Qwen3 maintainers: "multi-step tool use with
    # thinking models requires the prior thinking content"). Empty for
    # non-reasoning models — no-op when empty.
    reasoning: str = ""


@dataclass
class ValidationResult:
    """Result of output validation for node retry logic.

    Attributes:
        is_valid: Whether the output passed validation.
        errors: List of error messages describing validation failures.
    """

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)


class ValidationError(Exception):
    """Raised when node output fails validation.

    Contains error details for retry continuation messages.
    """


@runtime_checkable
class NodeMonitor(Protocol):
    """Protocol for node-level monitoring hooks.

    Monitors observe node execution lifecycle events without mutating state.
    All methods are optional — implement only the hooks you need.
    Returning a string from any hook appends it as an assistant-role
    continuation to the messages for the current retry attempt.
    """

    def on_before_node_call(
        self,
        node_id: str,
        session_id: str,
        attempt: int,
        messages: list[dict],
        resolved_tools: list,
    ) -> str | None:
        """Called before each LLM call in a node.

        Args:
            node_id: The node being executed.
            session_id: The session the node is running in.
            attempt: The current attempt number (1-indexed).
            messages: The messages being sent to the LLM.
            resolved_tools: The tools resolved for this call.

        Returns:
            Optional continuation string to append to messages.
        """
        ...

    def on_after_node_call(
        self,
        node_id: str,
        session_id: str,
        attempt: int,
        result: LLMResult,
        validation_result: ValidationResult,
    ) -> str | None:
        """Called after validation following an LLM call.

        Only called when validation fails (is_valid=False).

        Args:
            node_id: The node being executed.
            session_id: The session the node is running in.
            attempt: The current attempt number (1-indexed).
            result: The LLM response.
            validation_result: The validation result.

        Returns:
            Optional continuation string to append to messages.
        """
        ...

    def on_retry_exhausted(
        self,
        node_id: str,
        session_id: str,
        error: ValidationError,
        attempts: int,
    ) -> str | None:
        """Called when retry attempts are exhausted.

        Args:
            node_id: The node being executed.
            session_id: The session the node is running in.
            error: The validation error that caused exhaustion.
            attempts: Total number of attempts made.

        Returns:
            Optional continuation string (typically None at exhaustion).
        """
        ...


@runtime_checkable
class AgentMonitor(Protocol):
    """Protocol for agent-level monitoring hooks.

    AgentMonitor and NodeMonitor are independent hooks. The loop calls
    AgentMonitor.on_*() for loop-level observation; the node calls its
    own NodeMonitor via self.config.monitor. Both fire when configured
    — neither wraps or forwards to the other.
    """

    def on_before_node_call(
        self,
        node_id: str,
        session_id: str,
        attempt: int,
        messages: list[dict],
        resolved_tools: list,
    ) -> str | None:
        """Called before each LLM call in a node."""
        ...

    def on_after_node_call(
        self,
        node_id: str,
        session_id: str,
        attempt: int,
        result: LLMResult,
        validation_result: ValidationResult,
    ) -> str | None:
        """Called after validation following an LLM call."""
        ...

    def on_retry_exhausted(
        self,
        node_id: str,
        session_id: str,
        error: ValidationError,
        attempts: int,
    ) -> str | None:
        """Called when retry attempts are exhausted."""
        ...


@dataclass
class TranscriptRecord:
    """Serializable event record for WildClawBench transcript export.

    Wraps a stream event with run-level metadata for JSONL serialization.

    Attributes:
        event: The original stream event dict.
        run_id: Unique run identifier.
        session_id: Root session ID.
        sequence: Monotonically increasing sequence number.
    """

    event: dict
    run_id: str = ""
    session_id: str = ""
    sequence: int = 0

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for JSONL output.

        Returns:
            Dict with event, run_id, session_id, and sequence fields.
        """
        return {
            "event": self.event,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "sequence": self.sequence,
        }
