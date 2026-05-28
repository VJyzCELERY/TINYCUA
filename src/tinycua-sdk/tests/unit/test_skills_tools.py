# Unit tests for Skills Tools

import pytest
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.tools.native.skills_tools import (
    create_skills_list_tool,
    create_skill_view_tool,
)


class TestSkillsTools:
    """Tests for the skills_list and skill_view tools."""

    def test_skills_list_basic(self):
        """Test skills_list returns all skills."""
        registry = SkillRegistry()
        registry.register(
            Skill(name="Skill A", description="Desc A", instructions="")
        )
        registry.register(
            Skill(name="Skill B", description="Desc B", instructions="")
        )

        tool = create_skills_list_tool(registry)
        result = tool.invoke()

        assert "skills" in result
        assert len(result["skills"]) == 2

    def test_skill_view_basic(self):
        """Test skill_view returns full skill details."""
        registry = SkillRegistry()
        registry.register(
            Skill(
                name="Test Skill",
                description="Test description",
                instructions="Do something specific",
            )
        )

        tool = create_skill_view_tool(registry)
        result = tool.invoke(skill_name="Test Skill")

        assert result["name"] == "Test Skill"
        assert result["description"] == "Test description"
        assert result["instructions"] == "Do something specific"

    def test_skill_view_not_found(self):
        """Test skill_view raises error for missing skill."""
        registry = SkillRegistry()

        tool = create_skill_view_tool(registry)

        with pytest.raises(ValueError, match="not found"):
            tool.invoke(skill_name="NonExistent")

    def test_skills_list_empty(self):
        """Test skills_list with no skills."""
        registry = SkillRegistry()

        tool = create_skills_list_tool(registry)
        result = tool.invoke()

        assert result["skills"] == []
