"""Skills tools for progressive disclosure."""

from typing import Any

from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.tools import tool


class CallableTool:
    """Wrapper to make a Tool callable."""

    def __init__(self, tool_instance):
        """Initialize with a Tool instance.

        Args:
            tool_instance: Tool instance to wrap
        """
        self._tool = tool_instance

    @property
    def name(self) -> str:
        """Return the name of the wrapped tool.

        Returns:
            Name of the wrapped tool.
        """
        return self._tool.name

    def __call__(self, *args, **kwargs):
        """Call the underlying tool function.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result from tool invocation
        """
        # Convert positional args to keyword args based on parameter names
        import inspect

        sig = inspect.signature(self._tool._fn)
        param_names = list(sig.parameters.keys())

        # Map positional args to parameter names
        for i, arg in enumerate(args):
            if i < len(param_names):
                kwargs[param_names[i]] = arg

        return self._tool.invoke(**kwargs)


def create_skills_list_tool(registry: SkillRegistry):
    """Create skills_list() tool.

    Args:
        registry: SkillRegistry instance

    Returns:
        CallableTool instance for listing skills
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

    return CallableTool(skills_list)


def create_skill_view_tool(registry: SkillRegistry):
    """Create skill_view() tool.

    Args:
        registry: SkillRegistry instance

    Returns:
        CallableTool instance for viewing skill details
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
        skill = registry.get_skill(skill_name)

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

    return CallableTool(skill_view)
