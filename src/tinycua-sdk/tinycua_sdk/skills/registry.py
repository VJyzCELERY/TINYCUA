"""Skill registry for managing skills."""


from tinycua_sdk.skills.models import Skill


class SkillRegistry:
    """Registry for managing loaded skills.

    Provides a central registry for skills that can be registered,
    retrieved by name or category, and unregistered.
    """

    def __init__(self):
        """Initialize the registry."""
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Register a skill in the registry.

        Args:
            skill: Skill to register.
        """
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        """Get a skill by name.

        Args:
            name: Skill name.

        Returns:
            Skill if found, None otherwise.
        """
        return self._skills.get(name)

    def unregister(self, name: str) -> None:
        """Remove a skill from the registry.

        Args:
            name: Name of the skill to remove.
        """
        self._skills.pop(name, None)

    def list_skills(self, category: str | None = None) -> list[Skill]:
        """List all skills, optionally filtered by category.

        Args:
            category: Optional category filter.

        Returns:
            List of skills.
        """
        skills = list(self._skills.values())

        if category:
            skills = [s for s in skills if s.category == category]

        return sorted(skills, key=lambda s: s.name)

    def get_categories(self) -> list[str]:
        """Get all unique categories.

        Returns:
            List of category names.
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
