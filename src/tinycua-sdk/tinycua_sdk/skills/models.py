"""Skill data models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Skill(BaseModel):
    """Immutable skill configuration value object.

    Attributes:
        name: The name of the skill.
        description: A brief description of what the skill does.
        instructions: Detailed instructions for the agent.
        metadata: Additional metadata.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    instructions: str
    metadata: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        """Deserialize from plain dict.

        Args:
            data: A dictionary with skill configuration values.

        Returns:
            A new Skill instance.
        """
        return cls(**data)
