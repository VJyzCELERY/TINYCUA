"""Skill data models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Skill:
    """Represents a loaded skill.

    Attributes:
        name: The name of the skill.
        description: A brief description of what the skill does.
        category: The category the skill belongs to.
        instructions: Detailed instructions for the agent.
        tools: List of tool names this skill provides.
        dependencies: List of other skills this skill depends on.
        source: Source identifier for the skill (e.g., file path, inline).
        metadata: Additional metadata from SKILL.md.
        is_active: Whether the skill is active.
        version: Skill version string.
    """

    name: str
    description: str = ""
    category: str = "general"
    instructions: str = ""
    tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    version: str = "1.0.0"

    @classmethod
    def load(cls, text: str) -> "Skill":
        """Parse a skill from Markdown text with YAML frontmatter.

        Args:
            text: Markdown text containing optional YAML frontmatter.

        Returns:
            Parsed Skill instance.

        Raises:
            ValueError: If YAML frontmatter is invalid.
        """
        import yaml

        stripped_text = text.lstrip()
        if stripped_text.startswith("---"):
            parts = stripped_text.split("---", 2)
            if len(parts) < 3:
                raise ValueError("Invalid YAML frontmatter format")
            yaml_content = parts[1].strip()
            markdown_content = parts[2].strip()
        else:
            yaml_content = ""
            markdown_content = text

        metadata = {}
        if yaml_content:
            try:
                metadata = yaml.safe_load(yaml_content) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML: {e}")

        sections = _parse_markdown_sections(markdown_content)

        return cls(
            name=metadata.get("name", "unnamed"),
            description=metadata.get("description", sections.get("description", "")),
            category=metadata.get("category", "general"),
            instructions=sections.get("instructions", markdown_content),
            tools=metadata.get("tools", []),
            dependencies=metadata.get("dependencies", []),
            source=metadata.get("source"),
            metadata=metadata,
            is_active=metadata.get("is_active", True),
            version=metadata.get("version", "1.0.0"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        """Create a Skill from a dictionary.

        Args:
            data: Dictionary containing skill attributes.

        Returns:
            Skill instance.
        """
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            instructions=data.get("instructions", ""),
            tools=data.get("tools", []),
            dependencies=data.get("dependencies", []),
            source=data.get("source"),
            metadata=data.get("metadata", {}),
            is_active=data.get("is_active", True),
            version=data.get("version", "1.0.0"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert skill to dictionary representation.

        Returns:
            Dictionary containing all skill attributes.
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "instructions": self.instructions,
            "tools": self.tools,
            "dependencies": self.dependencies,
            "source": self.source,
            "metadata": self.metadata,
            "is_active": self.is_active,
            "version": self.version,
        }


def _parse_markdown_sections(body: str) -> dict[str, str]:
    """Extract sections from markdown body.

    Recognized sections: ## Description, ## Instructions, ## Tools.

    Args:
        body: Markdown content.

    Returns:
        Dictionary mapping lower-case section names to their content.
    """
    sections: dict[str, str] = {}
    lines = body.split("\n")
    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = stripped[3:].strip().lower()
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections
