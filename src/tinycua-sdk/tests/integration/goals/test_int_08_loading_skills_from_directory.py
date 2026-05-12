"""Integration tests for skill directory loading."""

from pathlib import Path

from tinycua_sdk import Skill


class TestInt08LoadingSkillsFromDirectory:
    """Test suite for Skill.load_directory and from_directory."""

    def test_int_01_skill_directory_discovery(self, tmp_path: Path):
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

    def test_int_02_skill_directory_empty(self, tmp_path: Path):
        """load_directory returns empty list for empty directory."""
        empty_dir = tmp_path / "empty_skills"
        empty_dir.mkdir(parents=True)
        assert Skill.load_directory(empty_dir) == []

    def test_int_03_skill_from_directory_parses_frontmatter(self, tmp_path: Path):
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

    def test_int_04_skill_from_directory_no_frontmatter(self, tmp_path: Path):
        """SKILL.md without frontmatter uses directory name as name."""
        skill_dir = tmp_path / "no_frontmatter_skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("Just instructions here.")

        skill = Skill.from_directory(skill_dir)
        assert skill.name == "no_frontmatter_skill"
        assert skill.description == ""
        assert skill.instructions == "Just instructions here."
        assert skill.metadata == {}

    def test_int_05_skill_directory_skips_missing_skill_md(self, tmp_path: Path):
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
