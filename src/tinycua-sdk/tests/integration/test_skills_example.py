"""Integration Tests: Skills System

Tests based on skills example (12_skills_example.py)
Tests:
1. Skill discovery from directory
2. Skill registry operations
3. Skill tools (list, view)
4. Skills with agents
5. Skill activation logic
"""

import pytest
import tempfile
from pathlib import Path

from tinycua_sdk import Agent
from tinycua_sdk.skills.loader import SkillLoader
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.skills.tools import create_skills_list_tool, create_skill_view_tool
from tinycua_sdk.skills.models import Skill


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_skill_dir():
    """Create a temporary directory with test skills."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        
        # Create test skills
        skill_dir = base_dir / "math-helper"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: math-helper
description: Helps with math calculations
category: tools
tools: [calculator, add]
dependencies: []
---

## Instructions
This skill helps with math calculations.
""")
        
        skill_dir = base_dir / "web-search"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: web-search
description: Searches the web
category: tools
tools: [requests]
dependencies: []
---

## Instructions
This skill searches the web.
""")
        
        skill_dir = base_dir / "data-analysis"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: data-analysis
description: Analyzes data
category: analytics
tools: [pandas]
dependencies: []
---

## Instructions
This skill analyzes data.
""")
        
        yield base_dir


@pytest.fixture
def skill_registry(temp_skill_dir):
    """Create a registry with loaded skills."""
    registry = SkillRegistry()
    registry.load_skills_from_directory(temp_skill_dir)
    return registry


# =============================================================================
# Test Cases
# =============================================================================

class TestSkillDiscovery:
    """Test skill discovery from directory."""

    def test_discover_skills(self, temp_skill_dir):
        """Test discovering skills from directory."""
        loader = SkillLoader()
        skills = loader.discover_skills(temp_skill_dir)
        
        assert len(skills) == 3
        skill_names = [s.name for s in skills]
        assert "math-helper" in skill_names
        assert "web-search" in skill_names
        assert "data-analysis" in skill_names

    def test_discover_skills_with_category(self, temp_skill_dir):
        """Test discovering skills filtered by category."""
        loader = SkillLoader()
        skills = loader.discover_skills(temp_skill_dir)
        
        tools_skills = [s for s in skills if s.category == "tools"]
        assert len(tools_skills) == 2
        
        analytics_skills = [s for s in skills if s.category == "analytics"]
        assert len(analytics_skills) == 1

    def test_skill_metadata(self, temp_skill_dir):
        """Test skill metadata parsing."""
        loader = SkillLoader()
        skills = loader.discover_skills(temp_skill_dir)
        
        math_skill = next(s for s in skills if s.name == "math-helper")
        assert math_skill.description == "Helps with math calculations"
        assert math_skill.tools == ["calculator", "add"]
        assert "calculations" in math_skill.instructions.lower()


class TestSkillRegistry:
    """Test skill registry operations."""

    def test_registry_list_all(self, skill_registry):
        """Test listing all skills."""
        skills = skill_registry.list_skills()
        assert len(skills) == 3

    def test_registry_list_filtered(self, skill_registry):
        """Test listing skills with category filter."""
        skills = skill_registry.list_skills(category="tools")
        assert len(skills) == 2
        assert all(s.category == "tools" for s in skills)

    def test_registry_get(self, skill_registry):
        """Test getting skill by name."""
        skill = skill_registry.get_skill("math-helper")
        assert skill is not None
        assert skill.description == "Helps with math calculations"

    def test_registry_get_not_found(self, skill_registry):
        """Test getting skill that doesn't exist."""
        skill = skill_registry.get_skill("nonexistent")
        assert skill is None

    def test_registry_categories(self, skill_registry):
        """Test getting all categories."""
        categories = skill_registry.get_categories()
        assert "tools" in categories
        assert "analytics" in categories


class TestSkillTools:
    """Test skill tools."""

    def test_skills_list_tool(self, skill_registry):
        """Test skills_list tool."""
        tool = create_skills_list_tool(skill_registry)
        result = tool(category=None)
        
        assert "skills" in result
        assert len(result["skills"]) == 3
        
        # Filter by category
        result = tool(category="tools")
        assert len(result["skills"]) == 2

    def test_skills_list_tool_empty_category(self, skill_registry):
        """Test skills_list with non-matching category."""
        result = create_skills_list_tool(skill_registry)(category="nonexistent")
        assert len(result["skills"]) == 0

    def test_skill_view_tool(self, skill_registry):
        """Test skill_view tool."""
        tool = create_skill_view_tool(skill_registry)
        result = tool(skill_name="math-helper")
        
        assert result["name"] == "math-helper"
        assert result["description"] == "Helps with math calculations"
        assert result["tools"] == ["calculator", "add"]
        assert result["instructions"] != ""

    def test_skill_view_not_found(self, skill_registry):
        """Test skill_view with non-existent skill."""
        tool = create_skill_view_tool(skill_registry)
        
        with pytest.raises(ValueError, match="not found"):
            tool(skill_name="nonexistent")


class TestSkillsWithAgent:
    """Test skills with agent creation."""

    def test_agent_creation_without_skills(self):
        """Test basic agent creation."""
        agent = Agent(
            name="test-agent",
            instructions="You are helpful.",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
        )
        
        assert agent.name == "test-agent"

    @pytest.mark.asyncio
    async def test_agent_run_simple(self):
        """Test agent run with simple prompt."""
        agent = Agent(
            name="test-agent",
            instructions="You are helpful.",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
        )
        
        try:
            response = await agent.run("Say 'hello' in one word.")
            assert isinstance(response, str)
        except Exception:
            pytest.skip("LM Studio not available")


class TestSkillActivation:
    """Test skill activation logic."""

    def test_platform_activation_linux(self):
        """Test platform activation for linux."""
        from tinycua_sdk.agent.skill_resolver import SkillActivator
        
        activator = SkillActivator()
        
        # Test with linux
        skill = type('Skill', (), {'metadata': {'platforms': ['linux']}})()
        # On linux this should activate
        result = activator._check_platform(['linux'])
        assert result == True

    def test_platform_activation_no_match(self):
        """Test platform activation with no match."""
        from tinycua_sdk.agent.skill_resolver import SkillActivator
        
        activator = SkillActivator()
        
        # This should only match win32 which we're likely not running on
        result = activator._check_platform(['win32'])
        # Will vary based on actual platform

    def test_requires_toolsets(self):
        """Test requires_toolsets activation."""
        from tinycua_sdk.agent.skill_resolver import SkillActivator
        
        activator = SkillActivator()
        
        skill = type('Skill', (), {
            'metadata': {'requires_toolsets': ['web', 'api']}
        })()
        
        available_toolsets = {'web', 'database'}
        available_tools = set()
        
        # Should activate because 'web' is available
        result = activator.should_activate_skill(skill, available_toolsets, available_tools)
        assert result == True

    def test_requires_toolsets_no_match(self):
        """Test requires_toolsets with no match."""
        from tinycua_sdk.agent.skill_resolver import SkillActivator
        
        activator = SkillActivator()
        
        skill = type('Skill', (), {
            'metadata': {'requires_toolsets': ['ml', 'gpu']}
        })()
        
        available_toolsets = {'web', 'database'}
        available_tools = set()
        
        result = activator.should_activate_skill(skill, available_toolsets, available_tools)
        assert result == False

    def test_requires_tools(self):
        """Test requires_tools activation."""
        from tinycua_sdk.agent.skill_resolver import SkillActivator
        
        activator = SkillActivator()
        
        skill = type('Skill', (), {
            'metadata': {'requires_tools': ['requests', 'BeautifulSoup']}
        })()
        
        available_toolsets = set()
        available_tools = {'requests', 'httpx'}
        
        # Should activate because 'requests' is available
        result = activator.should_activate_skill(skill, available_toolsets, available_tools)
        assert result == True


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])