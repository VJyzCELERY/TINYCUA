"""Placeholder type stubs for node configuration types.

These are forward references for types that will be implemented in later milestones.
Currently defined as simple stubs to satisfy type annotations in node config.
"""

from __future__ import annotations


class Tool:
    """Placeholder for SDK Tool type.

    Will be replaced with the actual Tool class from tinycua.agent.tools
    when the tool SDK is stable.
    """

    name: str = ""

    def __init__(self, name: str = "") -> None:
        self.name = name


class StateObject:
    """Placeholder for state object type.

    Conceptual design exists in tinycua.specs.state_objects but not yet implemented.
    Use Any for now.
    """
    pass


class LLMResult:
    """Placeholder for LLM result type.

    Will be defined in the loop milestone.
    """
    pass


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
