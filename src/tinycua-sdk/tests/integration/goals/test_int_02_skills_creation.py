"""Integration tests for Skill and SkillRegistry.

Converts targets: 08_skill_creation, 09_skill_registry
"""

import pytest

from tinycua_sdk import Skill
from tinycua_sdk.skills.registry import SkillRegistry


class TestInt02SkillsCreation:
    """Test suite for Skill creation and SkillRegistry functionality."""

    def test_int_01_skill_creation(self):
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

    def test_int_02_skill_to_dict(self):
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

    def test_int_03_skill_from_dict_roundtrip(self):
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

    def test_int_04_skill_default_metadata(self):
        """Verify Skill has empty dict as default metadata."""
        s = Skill(
            name="test",
            description="test",
            instructions="test",
        )
        assert s.metadata == {}

    def test_int_05_skill_frozen_immutable(self):
        """Verify Skill is frozen (mutation raises error)."""
        s = Skill(name="test", description="test", instructions="test")
        with pytest.raises(Exception):
            s.name = "new_name"

    def test_int_06_skill_registry_register_and_list(self):
        """Target 1.9: Verify SkillRegistry register and list."""
        s1 = Skill(name="coder", description="Write code", instructions="Use PEP 8.")
        s2 = Skill(name="tester", description="Write tests", instructions="Cover edge cases.")

        registry = SkillRegistry()
        registry.register(s1)
        registry.register(s2)

        skills = registry.list_skills()
        assert len(skills) == 2

    def test_int_07_skill_registry_get(self):
        """Target 1.9: Verify SkillRegistry get by name."""
        s1 = Skill(name="coder", description="Write code", instructions="Use PEP 8.")

        registry = SkillRegistry()
        registry.register(s1)

        assert registry.get("coder").name == "coder"
        assert registry.get("nonexistent") is None

    def test_int_08_skill_registry_overwrite(self):
        """Target 1.9: Verify SkillRegistry overwrites on duplicate name registration."""
        s1 = Skill(name="coder", description="Write code", instructions="Use PEP 8.")
        s2 = Skill(name="tester", description="Write tests", instructions="Cover edge cases.")
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
