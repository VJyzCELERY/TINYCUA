# Unit tests for Skills Registry

from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.skills.models import Skill


class TestSkillRegistry:
    """Tests for the SkillRegistry class."""

    def test_register_skill(self):
        """Test registering a skill."""
        registry = SkillRegistry()
        skill = Skill(name="Test Skill", description="Test")

        registry.register_skill(skill)

        assert registry.get_skill("Test Skill") == skill
        assert registry.count == 1

    def test_get_skill_not_found(self):
        """Test getting a non-existent skill."""
        registry = SkillRegistry()

        assert registry.get_skill("NonExistent") is None

    def test_list_skills(self):
        """Test listing all skills."""
        registry = SkillRegistry()

        registry.register_skill(Skill(name="Skill A", category="cat1"))
        registry.register_skill(Skill(name="Skill B", category="cat2"))
        registry.register_skill(Skill(name="Skill C", category="cat1"))

        skills = registry.list_skills()

        assert len(skills) == 3
        names = [s.name for s in skills]
        assert names == ["Skill A", "Skill B", "Skill C"]

    def test_list_skills_filtered_by_category(self):
        """Test listing skills with category filter."""
        registry = SkillRegistry()

        registry.register_skill(Skill(name="Skill A", category="tools"))
        registry.register_skill(Skill(name="Skill B", category="tools"))
        registry.register_skill(Skill(name="Skill C", category="memory"))

        skills = registry.list_skills(category="tools")

        assert len(skills) == 2
        assert all(s.category == "tools" for s in skills)

    def test_get_categories(self):
        """Test getting all unique categories."""
        registry = SkillRegistry()

        registry.register_skill(Skill(name="S1", category="tools"))
        registry.register_skill(Skill(name="S2", category="tools"))
        registry.register_skill(Skill(name="S3", category="memory"))

        categories = registry.get_categories()

        assert set(categories) == {"tools", "memory"}

    def test_clear(self):
        """Test clearing all skills."""
        registry = SkillRegistry()

        registry.register_skill(Skill(name="S1"))
        registry.register_skill(Skill(name="S2"))

        registry.clear()

        assert registry.count == 0

    def test_load_skills_from_directory(self, tmp_path):
        """Test loading skills from a directory."""
        # Create skill directories
        for i in range(1, 3):
            skill_dir = tmp_path / f"skill_{i}"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                f"---\n"
                f'name: "Skill {i}"\n'
                f'description: "Skill {i} desc"\n'
                f'category: "test"\n'
                f"---\n"
                f"\n"
                f"## Instructions\n"
                f"Test instructions.\n"
            )

        registry = SkillRegistry()
        skills = registry.load_skills_from_directory(tmp_path)

        assert len(skills) == 2
        assert registry.count == 2
