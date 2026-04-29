"""Skills tools for progressive disclosure."""

from typing import Any

from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.tools import tool


def create_skills_list_tool(registry: SkillRegistry):
    """Create skills_list() tool.

    Args:
        registry: SkillRegistry instance

    Returns:
        Tool instance for listing skills
    """

    @tool
    def skills_list(category: str | None = None) -> dict[str, Any]:
        """List available skills with their metadata.

        Use this to discover what skills are available for extending
        the agent's capabilities.

        Args:
            category: Optional category filter

        Returns:
            Dictionary containing list of skills
        """
        skills = registry.list_skills(category=category)

        return {
            "skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "tools": s.tools,
                }
                for s in skills
            ]
        }

    return skills_list


def create_skill_view_tool(registry: SkillRegistry):
    """Create skill_view() tool.

    Args:
        registry: SkillRegistry instance

    Returns:
        Tool instance for viewing skill details
    """

    @tool
    def skill_view(skill_name: str) -> dict[str, Any]:
        """View full details of a specific skill including instructions and tools.

        Args:
            skill_name: Name of the skill to view

        Returns:
            Dictionary containing skill details

        Raises:
            ValueError: If skill not found
        """
        skill = registry.get(skill_name)

        if skill is None:
            raise ValueError(f"Skill '{skill_name}' not found")

        return {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "instructions": skill.instructions,
            "tools": skill.tools,
            "dependencies": skill.dependencies,
        }

    return skill_view
