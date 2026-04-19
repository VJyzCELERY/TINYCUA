# Unit tests for Skills Tools

import pytest
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.skills.tools import (
    create_skills_list_tool,
    create_skill_view_tool,
    CallableTool,
)
from tinycua_sdk.tools import tool


class TestSkillsTools:
    """Tests for the skills_list and skill_view tools."""

    def test_skills_list_basic(self):
        """Test skills_list returns all skills."""
        registry = SkillRegistry()
        registry.register_skill(
            Skill(name="Skill A", description="Desc A", category="cat1")
        )
        registry.register_skill(
            Skill(name="Skill B", description="Desc B", category="cat2")
        )

        tool = create_skills_list_tool(registry)
        result = tool()

        assert "skills" in result
        assert len(result["skills"]) == 2

    def test_skills_list_with_category_filter(self):
        """Test skills_list filters by category."""
        registry = SkillRegistry()
        registry.register_skill(
            Skill(name="Tool Skill", description="Desc", category="tools")
        )
        registry.register_skill(
            Skill(name="Mem Skill", description="Desc", category="memory")
        )

        tool = create_skills_list_tool(registry)
        result = tool(category="tools")

        assert len(result["skills"]) == 1
        assert result["skills"][0]["name"] == "Tool Skill"

    def test_skill_view_basic(self):
        """Test skill_view returns full skill details."""
        registry = SkillRegistry()
        registry.register_skill(
            Skill(
                name="Test Skill",
                description="Test description",
                category="testing",
                instructions="Do something specific",
                tools=["tool1", "tool2"],
                dependencies=["dep1"],
            )
        )

        tool = create_skill_view_tool(registry)
        result = tool("Test Skill")

        assert result["name"] == "Test Skill"
        assert result["description"] == "Test description"
        assert result["instructions"] == "Do something specific"
        assert result["tools"] == ["tool1", "tool2"]
        assert result["dependencies"] == ["dep1"]

    def test_skill_view_not_found(self):
        """Test skill_view raises error for missing skill."""
        registry = SkillRegistry()

        tool = create_skill_view_tool(registry)

        with pytest.raises(ValueError, match="not found"):
            tool("NonExistent")

    def test_skills_list_empty(self):
        """Test skills_list with no skills."""
        registry = SkillRegistry()

        tool = create_skills_list_tool(registry)
        result = tool()

        assert result["skills"] == []

    def test_callable_tool_name_property(self):
        """Test that CallableTool exposes name property from wrapped tool."""

        @tool
        def my_custom_tool(category: str | None = None) -> dict:
            """A custom tool."""
            return {"category": category}

        callable_tool = CallableTool(my_custom_tool)

        # Test that name property returns the correct tool name
        assert callable_tool.name == "my_custom_tool"

        # Test that name property forwards to _tool.name (FR-3)
        assert callable_tool.name == callable_tool._tool.name
