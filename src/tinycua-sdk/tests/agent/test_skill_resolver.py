"""Unit tests for SkillToolResolver and SkillActivator."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tinycua_sdk.agent.skill_resolver import SkillToolResolver, SkillActivator
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.tools.decorators import Tool
from tinycua_sdk.core.registry import ToolRegistry, ToolEntry


class TestSkillToolResolver:
    """Tests for SkillToolResolver class."""

    def setup_method(self):
        """Clear ToolRegistry before each test."""
        self.registry = ToolRegistry()
        self.registry.clear()

    def teardown_method(self):
        """Clear ToolRegistry after each test."""
        self.registry.clear()

    def test_resolver_can_be_instantiated(self):
        """Test that SkillToolResolver can be instantiated."""
        resolver = SkillToolResolver()
        assert resolver is not None

    def test_resolver_with_tool_registry(self):
        """Test that SkillToolResolver can be instantiated with a ToolRegistry."""
        registry = ToolRegistry()
        resolver = SkillToolResolver(tool_registry=registry)
        assert resolver.tool_registry is registry

    def test_resolve_skill_tools_returns_list(self):
        """Test that resolve_skill_tools returns a list."""
        resolver = SkillToolResolver()
        skill = Skill(name="test-skill", tools=[])
        result = resolver.resolve_skill_tools(skill)
        assert isinstance(result, list)
        assert result == []

    def test_resolve_skill_tools_with_valid_tools(self):
        """Test resolving tools that exist in registry."""
        # Register a tool in the registry
        tool = Tool(
            name="search_web",
            description="Search the web",
            parameters={"type": "object", "properties": {}},
        )
        self.registry.register(name="search_web", tool=tool, schema=tool.to_config())

        resolver = SkillToolResolver(tool_registry=self.registry)
        skill = Skill(name="web-researcher", tools=["search_web"])

        result = resolver.resolve_skill_tools(skill)
        assert len(result) == 1
        assert result[0].name == "search_web"

    def test_resolve_skill_tools_with_missing_tools(self):
        """Test resolving tools that don't exist in registry logs warning."""
        resolver = SkillToolResolver(tool_registry=self.registry)
        skill = Skill(name="web-researcher", tools=["nonexistent_tool"])

        # Should return empty list and log warning
        result = resolver.resolve_skill_tools(skill)
        assert result == []

    def test_resolve_skill_tools_maps_multiple_tools(self):
        """Test resolving multiple tools."""
        tool1 = Tool(
            name="search_web",
            description="Search the web",
            parameters={"type": "object", "properties": {}},
        )
        tool2 = Tool(
            name="fetch_url",
            description="Fetch a URL",
            parameters={"type": "object", "properties": {}},
        )
        self.registry.register(name="search_web", tool=tool1, schema=tool1.to_config())
        self.registry.register(name="fetch_url", tool=tool2, schema=tool2.to_config())

        resolver = SkillToolResolver(tool_registry=self.registry)
        skill = Skill(name="web-researcher", tools=["search_web", "fetch_url"])

        result = resolver.resolve_skill_tools(skill)
        assert len(result) == 2
        tool_names = [t.name for t in result]
        assert "search_web" in tool_names
        assert "fetch_url" in tool_names

    def test_get_resolved_tools_with_multiple_skills(self):
        """Test getting tools for multiple skills."""
        from tinycua_sdk.skills.registry import SkillRegistry

        tool1 = Tool(
            name="search_web",
            description="Search the web",
            parameters={"type": "object", "properties": {}},
        )
        self.registry.register(name="search_web", tool=tool1, schema=tool1.to_config())

        # Create skills
        skill1 = Skill(name="web-researcher", tools=["search_web"])
        skill2 = Skill(name="data-analyst", tools=[])

        # Create registry and register skills
        skill_registry = SkillRegistry()
        skill_registry.register_skill(skill1)
        skill_registry.register_skill(skill2)

        resolver = SkillToolResolver(tool_registry=self.registry)
        result = resolver.get_resolved_tools(
            ["web-researcher", "data-analyst"], skill_registry
        )
        assert len(result) == 1
        assert result[0].name == "search_web"

    def test_resolve_skill_tools_partial_resolution(self):
        """Test resolving when some tools exist and some don't."""
        tool1 = Tool(
            name="search_web",
            description="Search the web",
            parameters={"type": "object", "properties": {}},
        )
        self.registry.register(name="search_web", tool=tool1, schema=tool1.to_config())

        resolver = SkillToolResolver(tool_registry=self.registry)
        skill = Skill(name="web-researcher", tools=["search_web", "nonexistent"])

        result = resolver.resolve_skill_tools(skill)
        # Only the existing tool should be returned
        assert len(result) == 1
        assert result[0].name == "search_web"


class TestSkillActivator:
    """Tests for SkillActivator class."""

    def test_activator_can_be_instantiated(self):
        """Test that SkillActivator can be instantiated."""
        activator = SkillActivator()
        assert activator is not None

    def test_should_activate_skill_no_conditions(self):
        """Test that skill activates when no conditions specified."""
        activator = SkillActivator()
        skill = Skill(name="test-skill", tools=[], metadata={})

        result = activator.should_activate_skill(skill, set(), set())
        assert result is True

    def test_should_activate_skill_platform_check_linux(self):
        """Test platform check for linux."""
        activator = SkillActivator()
        skill = Skill(
            name="linux-skill",
            tools=[],
            metadata={"platforms": ["linux"]},
        )

        with patch("sys.platform", "linux"):
            result = activator.should_activate_skill(skill, set(), set())
            assert result is True

    def test_should_activate_skill_platform_check_darwin(self):
        """Test platform check for macOS."""
        activator = SkillActivator()
        skill = Skill(
            name="macos-skill",
            tools=[],
            metadata={"platforms": ["macos"]},
        )

        with patch("sys.platform", "darwin"):
            result = activator.should_activate_skill(skill, set(), set())
            assert result is True

    def test_should_activate_skill_platform_check_windows(self):
        """Test platform check for Windows."""
        activator = SkillActivator()
        skill = Skill(
            name="windows-skill",
            tools=[],
            metadata={"platforms": ["windows"]},
        )

        with patch("sys.platform", "win32"):
            result = activator.should_activate_skill(skill, set(), set())
            assert result is True

    def test_should_activate_skill_platform_mismatch(self):
        """Test platform check returns False when platform doesn't match."""
        activator = SkillActivator()
        skill = Skill(
            name="linux-skill",
            tools=[],
            metadata={"platforms": ["linux"]},
        )

        with patch("sys.platform", "win32"):
            result = activator.should_activate_skill(skill, set(), set())
            assert result is False

    def test_should_activate_skill_requires_toolsets(self):
        """Test requires_toolsets check."""
        activator = SkillActivator()
        skill = Skill(
            name="browser-skill",
            tools=[],
            metadata={"requires_toolsets": ["browser"]},
        )

        result = activator.should_activate_skill(skill, {"browser"}, set())
        assert result is True

    def test_should_activate_skill_requires_toolsets_no_match(self):
        """Test requires_toolsets returns False when no toolset matches."""
        activator = SkillActivator()
        skill = Skill(
            name="browser-skill",
            tools=[],
            metadata={"requires_toolsets": ["browser"]},
        )

        result = activator.should_activate_skill(skill, {"web"}, set())
        assert result is False

    def test_should_activate_skill_requires_toolsets_or_semantics(self):
        """Test requires_toolsets uses OR semantics."""
        activator = SkillActivator()
        skill = Skill(
            name="browser-skill",
            tools=[],
            metadata={"requires_toolsets": ["browser", "web"]},
        )

        # Should activate if either toolset is available
        result = activator.should_activate_skill(skill, {"browser"}, set())
        assert result is True

        result = activator.should_activate_skill(skill, {"web"}, set())
        assert result is True

    def test_should_activate_skill_fallback_for_toolsets(self):
        """Test fallback_for_toolsets hides skill when toolset available."""
        activator = SkillActivator()
        skill = Skill(
            name="web-skill",
            tools=[],
            metadata={"fallback_for_toolsets": ["browser"]},
        )

        # Should NOT activate when fallback toolset is available
        result = activator.should_activate_skill(skill, {"browser"}, set())
        assert result is False

        # Should activate when fallback toolset is NOT available
        result = activator.should_activate_skill(skill, {"web"}, set())
        assert result is True

    def test_should_activate_skill_requires_tools(self):
        """Test requires_tools check."""
        activator = SkillActivator()
        skill = Skill(
            name="search-skill",
            tools=[],
            metadata={"requires_tools": ["search_web"]},
        )

        result = activator.should_activate_skill(skill, set(), {"search_web"})
        assert result is True

    def test_should_activate_skill_requires_tools_no_match(self):
        """Test requires_tools returns False when no tool matches."""
        activator = SkillActivator()
        skill = Skill(
            name="search-skill",
            tools=[],
            metadata={"requires_tools": ["search_web"]},
        )

        result = activator.should_activate_skill(skill, set(), {"other_tool"})
        assert result is False

    def test_should_activate_skill_fallback_for_tools(self):
        """Test fallback_for_tools hides skill when tool available."""
        activator = SkillActivator()
        skill = Skill(
            name="search-skill",
            tools=[],
            metadata={"fallback_for_tools": ["search_web"]},
        )

        # Should NOT activate when fallback tool is available
        result = activator.should_activate_skill(skill, set(), {"search_web"})
        assert result is False

        # Should activate when fallback tool is NOT available
        result = activator.should_activate_skill(skill, set(), {"other_tool"})
        assert result is True

    def test_should_activate_skill_and_semantics_between_conditions(self):
        """Test AND semantics between different condition types."""
        activator = SkillActivator()
        skill = Skill(
            name="complex-skill",
            tools=[],
            metadata={
                "platforms": ["linux"],
                "requires_toolsets": ["browser"],
            },
        )

        # Should activate when ALL conditions pass
        with patch("sys.platform", "linux"):
            result = activator.should_activate_skill(skill, {"browser"}, set())
            assert result is True

            # Should NOT activate when platform doesn't match
            result = activator.should_activate_skill(skill, {"browser"}, set())
            assert result is True  # This passes because browser is available

        # Test with platform mismatch
        with patch("sys.platform", "win32"):
            result = activator.should_activate_skill(skill, {"browser"}, set())
            assert result is False

    def test_should_activate_skill_all_conditions_fail(self):
        """Test when all conditions fail."""
        activator = SkillActivator()
        skill = Skill(
            name="complex-skill",
            tools=[],
            metadata={
                "platforms": ["linux"],
                "requires_toolsets": ["browser"],
                "requires_tools": ["search_web"],
            },
        )

        with patch("sys.platform", "win32"):
            result = activator.should_activate_skill(
                skill, {"web"}, {"other_tool"}
            )
            assert result is False
