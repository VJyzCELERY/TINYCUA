"""Skill data models."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Skill:
    """Represents a loaded skill from the filesystem.

    Attributes:
        name: The name of the skill.
        description: A brief description of what the skill does.
        category: The category the skill belongs to.
        instructions: Detailed instructions for the agent.
        tools: List of tool names this skill provides.
        dependencies: List of other skills this skill depends on.
        path: Path to the skill directory.
        metadata: Additional metadata from SKILL.md.
        created_at: When the skill was created.
        modified_at: When the skill was last modified.
    """

    name: str
    description: str = ""
    category: str = "general"
    instructions: str = ""
    tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    modified_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert skill to dictionary representation.

        Returns:
            Dictionary containing all skill attributes
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "instructions": self.instructions,
            "tools": self.tools,
            "dependencies": self.dependencies,
            "path": str(self.path) if self.path else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
        }
