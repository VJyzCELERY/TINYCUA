"""Tests for Skill dataclass, Skill.load(), and SkillRegistry."""

import pytest


class TestSkillConstruction:
    """Tests for Skill construction."""

    def test_skill_default_construction(self):
        """Skill can be constructed with minimal parameters."""
        from tinycua_sdk import Skill

        skill = Skill(name="coder")
        assert skill.name == "coder"
        assert skill.description == ""
        assert skill.category == "general"
        assert skill.is_active is True
        assert skill.version == "1.0.0"

    def test_skill_full_construction(self):
        """Skill can be constructed with all parameters."""
        from tinycua_sdk import Skill

        skill = Skill(
            name="coder",
            description="Write code",
            category="development",
            instructions="Write clean code.",
            tools=["read_file", "write_file"],
            dependencies=["git"],
            source="inline",
            metadata={"author": "test"},
            is_active=True,
            version="2.0.0",
        )
        assert skill.name == "coder"
        assert skill.description == "Write code"
        assert skill.category == "development"
        assert skill.instructions == "Write clean code."
        assert skill.tools == ["read_file", "write_file"]
        assert skill.dependencies == ["git"]
        assert skill.source == "inline"
        assert skill.metadata == {"author": "test"}
        assert skill.version == "2.0.0"

    def test_skill_to_dict(self):
        """Skill.to_dict() returns a plain dict."""
        from tinycua_sdk import Skill

        skill = Skill(name="coder", category="dev")
        d = skill.to_dict()
        assert d["name"] == "coder"
        assert d["category"] == "dev"

    def test_skill_from_dict(self):
        """Skill.from_dict() reconstructs a Skill."""
        from tinycua_sdk import Skill

        data = {
            "name": "coder",
            "description": "Write code",
            "category": "dev",
            "instructions": "Write clean code.",
            "tools": ["read_file"],
            "dependencies": ["git"],
            "source": "inline",
            "metadata": {"author": "test"},
            "is_active": False,
            "version": "2.0.0",
        }
        skill = Skill.from_dict(data)
        assert skill.name == "coder"
        assert skill.description == "Write code"
        assert skill.category == "dev"
        assert skill.instructions == "Write clean code."
        assert skill.tools == ["read_file"]
        assert skill.dependencies == ["git"]
        assert skill.source == "inline"
        assert skill.metadata == {"author": "test"}
        assert skill.is_active is False
        assert skill.version == "2.0.0"

    def test_skill_round_trip_dict(self):
        """Skill.to_dict() and Skill.from_dict() are round-trippable."""
        from tinycua_sdk import Skill

        original = Skill(
            name="coder",
            description="Write code",
            category="dev",
            instructions="Write clean code.",
            tools=["read_file"],
            dependencies=["git"],
            source="inline",
            metadata={"author": "test"},
            is_active=False,
            version="2.0.0",
        )
        restored = Skill.from_dict(original.to_dict())
        assert restored == original


class TestSkillLoad:
    """Tests for Skill.load() from Markdown."""

    def test_skill_load_markdown(self):
        """Skill.load() parses Markdown text with YAML frontmatter."""
        from tinycua_sdk import Skill

        text = """
---
name: researcher
category: research
tools:
  - search
---
# Researcher

## Description
Research topics thoroughly.

## Instructions
Find accurate information from reliable sources.
"""
        skill = Skill.load(text)
        assert skill.name == "researcher"
        assert skill.category == "research"
        assert "search" in skill.tools
        assert skill.description == "Research topics thoroughly."
        assert "Find accurate information" in skill.instructions

    def test_skill_load_without_frontmatter(self):
        """Skill.load() works without YAML frontmatter."""
        from tinycua_sdk import Skill

        text = "# Helper\n\n## Description\nA simple helper skill."
        skill = Skill.load(text)
        assert skill.name == "unnamed"
        assert skill.description == "A simple helper skill."

    def test_skill_load_invalid_yaml(self):
        """Skill.load() raises ValueError for invalid YAML."""
        from tinycua_sdk import Skill

        text = "---\nname: test\n  invalid yaml:\n---\n"
        with pytest.raises(ValueError, match="Invalid YAML"):
            Skill.load(text)

    def test_skill_load_invalid_frontmatter_format(self):
        """Skill.load() raises ValueError for malformed frontmatter."""
        from tinycua_sdk import Skill

        text = "---\nonly one delimiter"
        with pytest.raises(ValueError, match="Invalid YAML frontmatter"):
            Skill.load(text)

    def test_skill_load_no_sections(self):
        """Skill.load() uses full markdown as instructions when no sections."""
        from tinycua_sdk import Skill

        text = "Just some plain text."
        skill = Skill.load(text)
        assert skill.instructions == "Just some plain text."


class TestSkillRegistry:
    """Tests for SkillRegistry."""

    def test_registry_explicit_instance(self):
        """SkillRegistry can be instantiated explicitly."""
        from tinycua_sdk import SkillRegistry

        registry = SkillRegistry()
        assert registry is not None

    def test_registry_not_singleton(self):
        """SkillRegistry instances are independent."""
        from tinycua_sdk import SkillRegistry, Skill

        r1 = SkillRegistry()
        r2 = SkillRegistry()
        r1.register(Skill(name="a"))
        assert r2.get("a") is None

    def test_registry_register_and_get(self):
        """SkillRegistry can register and retrieve skills."""
        from tinycua_sdk import SkillRegistry, Skill

        registry = SkillRegistry()
        skill = Skill(name="coder", description="Write code")
        registry.register(skill)
        retrieved = registry.get("coder")
        assert retrieved is not None
        assert retrieved.name == "coder"

    def test_registry_unregister(self):
        """SkillRegistry can unregister skills."""
        from tinycua_sdk import SkillRegistry, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="coder"))
        registry.unregister("coder")
        assert registry.get("coder") is None
        assert registry.count == 0

    def test_registry_list_skills(self):
        """SkillRegistry.list_skills() returns all skills."""
        from tinycua_sdk import SkillRegistry, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="a", category="dev"))
        registry.register(Skill(name="b", category="research"))
        assert len(registry.list_skills()) == 2

    def test_registry_filter_by_category(self):
        """SkillRegistry.list_skills() can filter by category."""
        from tinycua_sdk import SkillRegistry, Skill

        registry = SkillRegistry()
        registry.register(Skill(name="a", category="dev"))
        registry.register(Skill(name="b", category="research"))
        dev_skills = registry.list_skills(category="dev")
        assert len(dev_skills) == 1
        assert dev_skills[0].name == "a"
