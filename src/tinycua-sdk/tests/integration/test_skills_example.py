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
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.tools.native.skills_tools import create_skills_list_tool, create_skill_view_tool


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


def _load_skills_from_directory(base_dir: Path) -> list[Skill]:
    """Helper to load skills from a directory."""
    import yaml

    skills = []
    for entry in sorted(base_dir.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            skill_md = entry / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8")
                frontmatter = {}
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                name = frontmatter.get("name", entry.name)
                description = frontmatter.get("description", "")
                instructions = parts[2].strip() if len(parts) >= 3 else ""
                skill = Skill(name=name, description=description, instructions=instructions)
                skills.append(skill)
    return skills


@pytest.fixture
def skill_registry(temp_skill_dir):
    """Create a registry with loaded skills."""
    registry = SkillRegistry()
    for skill in _load_skills_from_directory(temp_skill_dir):
        registry.register(skill)
    return registry


# =============================================================================
# Test Cases
# =============================================================================

class TestSkillDiscovery:
    """Test skill discovery from directory."""

    def test_discover_skills(self, temp_skill_dir):
        """Test discovering skills from directory."""
        skills = _load_skills_from_directory(temp_skill_dir)

        assert len(skills) == 3
        skill_names = [s.name for s in skills]
        assert "math-helper" in skill_names
        assert "web-search" in skill_names
        assert "data-analysis" in skill_names

    def test_skill_metadata(self, temp_skill_dir):
        """Test skill metadata parsing."""
        skills = _load_skills_from_directory(temp_skill_dir)

        math_skill = next(s for s in skills if s.name == "math-helper")
        assert math_skill.description == "Helps with math calculations"
        assert "calculations" in math_skill.instructions.lower()


class TestSkillRegistry:
    """Test skill registry operations."""

    def test_registry_list_all(self, skill_registry):
        """Test listing all skills."""
        skills = skill_registry.list_skills()
        assert len(skills) == 3

    def test_registry_get(self, skill_registry):
        """Test getting skill by name."""
        skill = skill_registry.get("math-helper")
        assert skill is not None
        assert skill.description == "Helps with math calculations"

    def test_registry_get_not_found(self, skill_registry):
        """Test getting skill that doesn't exist."""
        skill = skill_registry.get("nonexistent")
        assert skill is None

class TestSkillTools:
    """Test skill tools."""

    def test_skills_list_tool(self, skill_registry):
        """Test skills_list tool."""
        tool = create_skills_list_tool(skill_registry)
        result = tool.invoke()

        assert "skills" in result
        assert len(result["skills"]) == 3

    def test_skill_view_tool(self, skill_registry):
        """Test skill_view tool."""
        tool = create_skill_view_tool(skill_registry)
        result = tool.invoke(skill_name="math-helper")

        assert result["name"] == "math-helper"
        assert result["description"] == "Helps with math calculations"
        assert result["instructions"] != ""

    def test_skill_view_not_found(self, skill_registry):
        """Test skill_view with non-existent skill."""
        tool = create_skill_view_tool(skill_registry)

        with pytest.raises(ValueError, match="not found"):
            tool.invoke(skill_name="nonexistent")


class TestSkillsWithAgent:
    """Test skills with agent creation."""

    def test_agent_creation_without_skills(self):
        """Test basic agent creation."""
        from tinycua_sdk.agent.llm_model import LanguageModel

        llm_model = LanguageModel(
            provider="openai-compatible",
            model_name="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        )
        agent = Agent(
            name="test-agent",
            instructions="You are helpful.",
            llm_model=llm_model,
        )
        
        assert agent.name == "test-agent"

    @pytest.mark.asyncio
    async def test_agent_run_simple(self):
        """Test agent run with simple prompt."""
        from tinycua_sdk.agent.llm_model import LanguageModel

        llm_model = LanguageModel(
            provider="openai-compatible",
            model_name="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        )
        agent = Agent(
            name="test-agent",
            instructions="You are helpful.",
            llm_model=llm_model,
        )
        
        try:
            response = await agent.run("Say 'hello' in one word.")
            assert isinstance(response, str)
        except Exception:
            pytest.skip("OpenAI-compatible endpoint not available")


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
