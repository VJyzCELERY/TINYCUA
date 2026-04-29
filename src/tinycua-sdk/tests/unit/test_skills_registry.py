# Unit tests for Skills Registry

from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.skills.models import Skill


class TestSkillRegistry:
    """Tests for the SkillRegistry class."""

    def test_register(self):
        """Test registering a skill."""
        registry = SkillRegistry()
        skill = Skill(name="Test Skill", description="Test")

        registry.register(skill)

        assert registry.get("Test Skill") == skill
        assert registry.count == 1

    def test_get_not_found(self):
        """Test getting a non-existent skill."""
        registry = SkillRegistry()

        assert registry.get("NonExistent") is None

    def test_unregister(self):
        """Test unregistering a skill."""
        registry = SkillRegistry()
        registry.register(Skill(name="Test Skill"))

        registry.unregister("Test Skill")

        assert registry.get("Test Skill") is None
        assert registry.count == 0

    def test_unregister_nonexistent(self):
        """Test unregistering a skill that doesn't exist."""
        registry = SkillRegistry()
        registry.unregister("NonExistent")  # Should not raise
        assert registry.count == 0

    def test_list_skills(self):
        """Test listing all skills."""
        registry = SkillRegistry()

        registry.register(Skill(name="Skill A", category="cat1"))
        registry.register(Skill(name="Skill B", category="cat2"))
        registry.register(Skill(name="Skill C", category="cat1"))

        skills = registry.list_skills()

        assert len(skills) == 3
        names = [s.name for s in skills]
        assert names == ["Skill A", "Skill B", "Skill C"]

    def test_list_skills_filtered_by_category(self):
        """Test listing skills with category filter."""
        registry = SkillRegistry()

        registry.register(Skill(name="Skill A", category="tools"))
        registry.register(Skill(name="Skill B", category="tools"))
        registry.register(Skill(name="Skill C", category="memory"))

        skills = registry.list_skills(category="tools")

        assert len(skills) == 2
        assert all(s.category == "tools" for s in skills)

    def test_get_categories(self):
        """Test getting all unique categories."""
        registry = SkillRegistry()

        registry.register(Skill(name="S1", category="tools"))
        registry.register(Skill(name="S2", category="tools"))
        registry.register(Skill(name="S3", category="memory"))

        categories = registry.get_categories()

        assert set(categories) == {"tools", "memory"}

    def test_clear(self):
        """Test clearing all skills."""
        registry = SkillRegistry()

        registry.register(Skill(name="S1"))
        registry.register(Skill(name="S2"))

        registry.clear()

        assert registry.count == 0

    def test_registry_instances_are_independent(self):
        """Test that two SkillRegistry instances are independent."""
        r1 = SkillRegistry()
        r2 = SkillRegistry()

        r1.register(Skill(name="only_in_r1"))
        r2.register(Skill(name="only_in_r2"))

        assert r1.get("only_in_r1") is not None
        assert r1.get("only_in_r2") is None
        assert r2.get("only_in_r1") is None
        assert r2.get("only_in_r2") is not None
