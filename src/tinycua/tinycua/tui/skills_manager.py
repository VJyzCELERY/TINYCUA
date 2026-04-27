"""Skills manager for TinyCUA TUI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tinycua_sdk.skills.loader import SkillLoader
from tinycua_sdk.skills.registry import SkillRegistry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DEFAULT_SKILL_DIRS = [
    Path.home() / ".tinycua" / "skills",
    Path(__file__).parent.parent.parent.parent / "skills",
]


@dataclass
class SkillInfo:
    """Skill information for display.

    Attributes:
        name: Skill name.
        description: Skill description.
        category: Skill category.
        path: Path to skill directory.
    """

    name: str
    description: str
    category: str
    path: Path


class SkillsManager:
    """Skills manager for TUI.

    Provides skill discovery, loading, and listing capabilities
    using the SDK's SkillLoader and SkillRegistry.
    """

    def __init__(self, skill_directories: list[Path] | None = None) -> None:
        """Initialize the skills manager.

        Args:
            skill_directories: Optional list of skill directories.
        """
        self._skill_directories = skill_directories or DEFAULT_SKILL_DIRS
        self._registry = SkillRegistry()
        self._loader = SkillLoader(self._skill_directories)
        self._loaded_skills: dict[str, SkillInfo] = {}
        self._skills_loaded = False

    def load_skills(self) -> bool:
        """Load skills from configured directories.

        Returns:
            True if successful, False otherwise.
        """
        try:
            for directory in self._skill_directories:
                if directory.exists() and directory.is_dir():
                    self._registry.load_skills_from_directory(directory)

            skills = self._loader.discover()
            for skill in skills:
                self._loaded_skills[skill.name] = SkillInfo(
                    name=skill.name,
                    description=skill.description or "",
                    category=skill.category,
                    path=skill.path,
                )

            self._skills_loaded = True
            return True
        except (OSError, ValueError, ImportError):
            logger.exception("Failed to load skills")
            return False

    def reload_skills(self) -> bool:
        """Reload skills from directories.

        Returns:
            True if successful, False otherwise.
        """
        self._loaded_skills.clear()
        self._registry = SkillRegistry()
        self._loader = SkillLoader(self._skill_directories)
        self._skills_loaded = False
        return self.load_skills()

    def list_skills(self) -> list[SkillInfo]:
        """List all available skills.

        Returns:
            List of SkillInfo instances.
        """
        if not self._skills_loaded:
            self.load_skills()
        return list(self._loaded_skills.values())

    def get_skill(self, name: str) -> SkillInfo | None:
        """Get skill information by name.

        Args:
            name: Skill name.

        Returns:
            SkillInfo or None if not found.
        """
        if name in self._loaded_skills:
            return self._loaded_skills[name]

        skill = self._registry.get_skill(name)
        if skill is None:
            return None

        return SkillInfo(
            name=skill.name,
            description=skill.description or "",
            category=skill.category,
            path=skill.path,
        )

    def get_skills_by_category(self, category: str) -> list[SkillInfo]:
        """Get skills belonging to a specific category.

        Args:
            category: Category name.

        Returns:
            List of SkillInfo instances.
        """
        return [
            skill
            for skill in self.list_skills()
            if skill.category == category
        ]

    def get_categories(self) -> list[str]:
        """Get list of available categories.

        Returns:
            List of category names.
        """
        categories = set()
        for skill in self.list_skills():
            categories.add(skill.category)
        return sorted(categories)

    def add_skill_directory(self, directory: Path) -> None:
        """Add a skill directory to search in.

        Args:
            directory: Path to skill directory.
        """
        if directory not in self._skill_directories:
            self._skill_directories.append(directory)
            self._skills_loaded = False
