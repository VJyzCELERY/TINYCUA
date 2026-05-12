"""Skill data models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


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
    metadata: dict[str, Any] = Field(default_factory=dict)

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

    @classmethod
    def from_directory(cls, path: Path) -> "Skill":
        """Load a skill from a directory containing a SKILL.md file.

        Parses YAML frontmatter (between --- delimiters) for name, description,
        and metadata. Everything after the frontmatter becomes instructions.

        Args:
            path: Path to the skill directory containing SKILL.md.

        Returns:
            A new Skill instance.
        """
        skill_md = Path(path) / "SKILL.md"
        content = skill_md.read_text()

        frontmatter: dict[str, Any] = {}
        instructions = content
        if content.startswith("---"):
            _DELIMITER_COUNT = 2
            parts = content.split("---", _DELIMITER_COUNT)
            if len(parts) >= 3:
                _, frontmatter_yaml, instructions = parts
                frontmatter = yaml.safe_load(frontmatter_yaml) or {}
                instructions = instructions.strip()

        name = frontmatter.pop("name", path.name)
        description = frontmatter.pop("description", "")

        return cls(
            name=name,
            description=description,
            instructions=instructions,
            metadata=frontmatter,
        )

    @classmethod
    def load_directory(cls, path: Path) -> list["Skill"]:
        """Load all skills from a directory of skill subdirectories.

        Each immediate subdirectory containing a SKILL.md file is loaded as a
        Skill via from_directory.

        Args:
            path: Path to the directory containing skill subdirectories.

        Returns:
            List of Skill instances found.
        """
        skills: list[Skill] = []
        for subdir in sorted(Path(path).iterdir()):
            if subdir.is_dir() and (subdir / "SKILL.md").exists():
                skills.append(cls.from_directory(subdir))
        return skills
