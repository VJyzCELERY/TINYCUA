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

    def test_skill_load_without_frontmatter(self):
        """Skill.load() works without YAML frontmatter."""
        from tinycua_sdk import Skill

        text = "# Helper\n\n## Description\nA simple helper skill."
        skill = Skill.load(text)
        assert skill.name == "unnamed"
        assert skill.description == ""


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
