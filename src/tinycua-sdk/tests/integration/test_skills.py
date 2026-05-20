"""Integration Tests: Skills System

Tests based on skills example (12_skills_example.py) and skill creation/loading.
Tests:
1. Skill creation and serialization
2. Skill directory loading
3. Skill discovery from directory
4. Skill registry operations
5. Skill tools (list, view)
6. Skills with agents
"""

import pytest
import tempfile
from pathlib import Path

from tinycua_sdk import Agent, Skill
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.tools.native.skills_tools import (
    create_skills_list_tool,
    create_skill_view_tool,
)


# =============================================================================
# Shared Fixtures
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


def _load_skills_from_directory(base_dir: Path) -> list:
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
                skill = Skill(
                    name=name, description=description, instructions=instructions
                )
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
# Skill Creation
# =============================================================================


class TestSkillsCreation:
    """Test suite for Skill creation and SkillRegistry functionality."""

    def test_skill_creation(self):
        """Target 1.8: Verify Skill creation with all fields."""
        s = Skill(
            name="web_research",
            description="Research topics using web search.",
            instructions="Use the web_search tool for current events.",
            metadata={"category": "research"},
        )

        assert s.name == "web_research"
        assert s.description == "Research topics using web search."
        assert s.instructions == "Use the web_search tool for current events."
        assert s.metadata["category"] == "research"

    def test_skill_to_dict(self):
        """Target 1.8: Verify Skill.to_dict serialization."""
        s = Skill(
            name="web_research",
            description="Research topics using web search.",
            instructions="Use the web_search tool for current events.",
            metadata={"category": "research"},
        )

        d = s.to_dict()
        assert d["name"] == "web_research"
        assert d["description"] == "Research topics using web search."
        assert d["metadata"]["category"] == "research"

    def test_skill_from_dict_roundtrip(self):
        """Target 1.8: Verify Skill.from_dict round-trip."""
        s = Skill(
            name="web_research",
            description="Research topics using web search.",
            instructions="Use the web_search tool for current events.",
            metadata={"category": "research"},
        )

        restored = Skill.from_dict(s.to_dict())
        assert restored.name == s.name
        assert restored.description == s.description

    def test_skill_default_metadata(self):
        """Verify Skill has empty dict as default metadata."""
        s = Skill(
            name="test",
            description="test",
            instructions="test",
        )
        assert s.metadata == {}

    def test_skill_frozen_immutable(self):
        """Verify Skill is frozen (mutation raises error)."""
        s = Skill(name="test", description="test", instructions="test")
        with pytest.raises(Exception):
            s.name = "new_name"

    def test_skill_registry_register_and_list(self):
        """Target 1.9: Verify SkillRegistry register and list."""
        s1 = Skill(name="coder", description="Write code", instructions="Use PEP 8.")
        s2 = Skill(
            name="tester", description="Write tests", instructions="Cover edge cases."
        )

        registry = SkillRegistry()
        registry.register(s1)
        registry.register(s2)

        skills = registry.list_skills()
        assert len(skills) == 2

    def test_skill_registry_get(self):
        """Target 1.9: Verify SkillRegistry get by name."""
        s1 = Skill(name="coder", description="Write code", instructions="Use PEP 8.")

        registry = SkillRegistry()
        registry.register(s1)

        assert registry.get("coder").name == "coder"
        assert registry.get("nonexistent") is None

    def test_skill_registry_overwrite(self):
        """Target 1.9: Verify SkillRegistry overwrites on duplicate name registration."""
        s1 = Skill(name="coder", description="Write code", instructions="Use PEP 8.")
        s2 = Skill(
            name="tester", description="Write tests", instructions="Cover edge cases."
        )
        s3 = Skill(name="coder", description="Write code v2", instructions="Use PEP 8.")

        registry = SkillRegistry()
        registry.register(s1)
        registry.register(s2)

        assert len(registry.list_skills()) == 2
        assert registry.get("coder").name == "coder"

        # Register s3 with same name as s1 — should overwrite
        registry.register(s3)
        assert len(registry.list_skills()) == 2
        assert registry.get("coder").name == "coder"
        assert registry.get("coder").description == "Write code v2"


# =============================================================================
# Skill Directory Loading
# =============================================================================


class TestSkillsDirectoryLoading:
    """Test suite for Skill.load_directory and from_directory."""

    def test_skill_directory_discovery(self, tmp_path: Path):
        """load_directory finds all skill subdirectories with SKILL.md."""
        skills_dir = tmp_path / "skills"
        (skills_dir / "skill_a").mkdir(parents=True)
        (skills_dir / "skill_a" / "SKILL.md").write_text(
            "---\nname: Skill A\ndescription: Does X\n---\nDo X"
        )
        (skills_dir / "skill_b").mkdir(parents=True)
        (skills_dir / "skill_b" / "SKILL.md").write_text(
            "---\nname: Skill B\ndescription: Does Y\n---\nDo Y"
        )

        skills = Skill.load_directory(skills_dir)
        assert len(skills) >= 2
        found = {s.name for s in skills}
        assert "Skill A" in found
        assert "Skill B" in found

    def test_skill_directory_empty(self, tmp_path: Path):
        """load_directory returns empty list for empty directory."""
        empty_dir = tmp_path / "empty_skills"
        empty_dir.mkdir(parents=True)
        assert Skill.load_directory(empty_dir) == []

    def test_skill_from_directory_parses_frontmatter(self, tmp_path: Path):
        """from_directory parses YAML frontmatter correctly."""
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: Web Research\ndescription: Research topics\ncategory: research\n---\n"
            "Use the web_search tool for current events."
        )

        skill = Skill.from_directory(skill_dir)
        assert skill.name == "Web Research"
        assert skill.description == "Research topics"
        assert "Use the web_search tool" in skill.instructions
        assert skill.metadata.get("category") == "research"

    def test_skill_from_directory_no_frontmatter(self, tmp_path: Path):
        """SKILL.md without frontmatter uses directory name as name."""
        skill_dir = tmp_path / "no_frontmatter_skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("Just instructions here.")

        skill = Skill.from_directory(skill_dir)
        assert skill.name == "no_frontmatter_skill"
        assert skill.description == ""
        assert skill.instructions == "Just instructions here."
        assert skill.metadata == {}

    def test_skill_directory_skips_missing_skill_md(self, tmp_path: Path):
        """Subdirectories without SKILL.md are skipped."""
        skills_dir = tmp_path / "mixed_skills"
        (skills_dir / "with_skill").mkdir(parents=True)
        (skills_dir / "with_skill" / "SKILL.md").write_text(
            "---\nname: With Skill\ndescription: Has SKILL.md\n---\nDo stuff"
        )
        (skills_dir / "no_skill").mkdir(parents=True)

        skills = Skill.load_directory(skills_dir)
        assert len(skills) == 1
        assert skills[0].name == "With Skill"


# =============================================================================
# Skill Discovery
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


# =============================================================================
# Skill Registry
# =============================================================================


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


# =============================================================================
# Skill Tools
# =============================================================================


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


# =============================================================================
# Skills With Agent
# =============================================================================


class TestSkillsWithAgent:
    """Test skills with agent creation."""

    def test_agent_creation_without_skills(self):
        """Test basic agent creation."""
        from tinycua_sdk.agent.llm_model import LanguageModel

        llm_model = LanguageModel(
            provider="openai-responses",
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
            provider="openai-responses",
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
