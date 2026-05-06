# Unit tests for Skills Registry

from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.skills.models import Skill


class TestSkillRegistry:
    """Tests for the SkillRegistry class."""

    def test_register(self):
        """Test registering a skill."""
        registry = SkillRegistry()
        skill = Skill(name="Test Skill", description="Test", instructions="")

        registry.register(skill)

        assert registry.get("Test Skill") == skill

    def test_get_not_found(self):
        """Test getting a non-existent skill."""
        registry = SkillRegistry()

        assert registry.get("NonExistent") is None

    def test_list_skills(self):
        """Test listing all skills."""
        registry = SkillRegistry()

        registry.register(Skill(name="Skill A", description="A", instructions="A"))
        registry.register(Skill(name="Skill B", description="B", instructions="B"))
        registry.register(Skill(name="Skill C", description="C", instructions="C"))

        skills = registry.list_skills()

        assert len(skills) == 3
        names = [s.name for s in skills]
        assert names == ["Skill A", "Skill B", "Skill C"]

    def test_registry_instances_are_independent(self):
        """Test that two SkillRegistry instances are independent."""
        r1 = SkillRegistry()
        r2 = SkillRegistry()

        r1.register(Skill(name="only_in_r1", description="", instructions=""))
        r2.register(Skill(name="only_in_r2", description="", instructions=""))

        assert r1.get("only_in_r1") is not None
        assert r1.get("only_in_r2") is None
        assert r2.get("only_in_r1") is None
        assert r2.get("only_in_r2") is not None
