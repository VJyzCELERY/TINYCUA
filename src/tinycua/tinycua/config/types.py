"""Placeholder type stubs for node configuration types.

These are forward references for types that will be implemented in later milestones.
Currently defined as simple stubs to satisfy type annotations in node config.
"""

from __future__ import annotations

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
    tool_calls: list[dict] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


class ValidationResult:
    """Placeholder for validation result type.

    Will be defined in the loop milestone.
    """
    pass


class ValidationError(Exception):
    """Placeholder for validation error type.

    Will be defined in the loop milestone.
    """
    pass
