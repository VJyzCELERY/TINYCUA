"""Skill registry for managing skills."""

from tinycua_sdk.skills.models import Skill


class SkillRegistry:
    """Registry for managing loaded skills.

    Provides a central registry for skills that can be registered,
    retrieved by name, and supports overwrite on duplicate registration.
    """

    def __init__(self) -> None:
        """Initialize the registry with empty skill storage."""
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Register a skill in the registry.

        Overwrites any existing skill with the same name.

        Args:
            skill: Skill to register.

        Returns:
            None.
        """
        self._skills[skill.name] = skill

    def list_skills(self) -> list[Skill]:
        """List all registered skills.

        Returns:
            List of all registered skills.
        """
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        """Get a skill by name.

        Args:
            name: Skill name.

        Returns:
            Skill if found, None otherwise.
        """
        return self._skills.get(name)
