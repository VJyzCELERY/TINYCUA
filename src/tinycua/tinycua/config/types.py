"""Placeholder type stubs for node configuration types.

These are forward references for types that will be implemented in later milestones.
Currently defined as simple stubs to satisfy type annotations in node config.
"""

from __future__ import annotations

from typing import Any

from dataclasses import dataclass, field


class Tool:
    """Placeholder for SDK Tool type.

    Will be replaced with the actual Tool class from tinycua.agent.tools
    when the tool SDK is stable.
    """

    def __init__(self, name: str = "") -> None:
        self.name = name


class StateObject:
    """Placeholder for state object type.

    Conceptual design exists in tinycua.specs.state_objects but not yet implemented.
    Use Any for now.
    """
    pass


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
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


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
