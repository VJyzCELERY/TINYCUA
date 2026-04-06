"""Skill registry for managing skills."""

from pathlib import Path
from typing import Any

from tinycua_sdk.skills.models import Skill
from tinycua_sdk.skills.loader import SkillLoader


class SkillRegistry:
    """Registry for managing loaded skills with caching.

    Provides a central registry for skills that can be discovered,
    registered, and retrieved by name or category.
    """

    def __init__(self, cache: Any | None = None):
        """Initialize the registry.

        Args:
            cache: Optional cache instance for skill caching
        """
        self._skills: dict[str, Skill] = {}
        self._loader = SkillLoader()
        self._cache = cache

    def register_skill(self, skill: Skill) -> None:
        """Register a skill in the registry.

        Args:
            skill: Skill to register
        """
        self._skills[skill.name] = skill

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill if found, None otherwise
        """
        return self._skills.get(name)

    def list_skills(self, category: str | None = None) -> list[Skill]:
        """List all skills, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of skills
        """
        skills = list(self._skills.values())

        if category:
            skills = [s for s in skills if s.category == category]

        return sorted(skills, key=lambda s: s.name)

    def load_skills_from_directory(self, base_dir: Path) -> list[Skill]:
        """Load and register skills from a directory.

        Args:
            base_dir: Directory containing skill subdirectories

        Returns:
            List of loaded skills
        """
        skills = self._loader.discover_skills(base_dir)

        for skill in skills:
            self.register_skill(skill)

        return skills

    def get_categories(self) -> list[str]:
        """Get all unique categories.

        Returns:
            List of category names
        """
        categories = set()
        for skill in self._skills.values():
            categories.add(skill.category)
        return sorted(categories)

    def clear(self) -> None:
        """Clear all registered skills."""
        self._skills.clear()

    @property
    def count(self) -> int:
        """Get the number of registered skills."""
        return len(self._skills)
