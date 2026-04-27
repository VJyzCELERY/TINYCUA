# Unit tests for Skills Loader

import pytest
from tinycua_sdk.skills.loader import SkillLoader, SkillParseError, SkillNotFoundError


class TestSkillLoader:
    """Tests for the SkillLoader class."""

    def test_load_skill_basic(self, tmp_path):
        """Test loading a basic skill."""
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            'name: "Test Skill"\n'
            'description: "A test skill"\n'
            'category: "testing"\n'
            "tools:\n"
            "  - tool_one\n"
            "  - tool_two\n"
            "dependencies:\n"
            "  - dep_one\n"
            "---\n"
            "\n"
            "## Instructions\n"
            "Detailed instructions for the agent...\n"
        )

        loader = SkillLoader()
        skill = loader.load_skill(skill_dir)

        assert skill.name == "Test Skill"
        assert skill.description == "A test skill"
        assert skill.category == "testing"
        assert "tool_one" in skill.tools
        assert "tool_two" in skill.tools
        assert "dep_one" in skill.dependencies
        assert "Detailed instructions" in skill.instructions

    def test_load_skill_missing_skill_md(self, tmp_path):
        """Test loading from a directory without SKILL.md."""
        skill_dir = tmp_path / "missing_skill"
        skill_dir.mkdir()

        loader = SkillLoader()
        with pytest.raises(SkillNotFoundError):
            loader.load_skill(skill_dir)

    def test_load_skill_invalid_yaml(self, tmp_path):
        """Test handling of invalid YAML in frontmatter."""
        skill_dir = tmp_path / "invalid_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            'name: "Invalid Skill"\n'
            "description: This has invalid yaml:\n"
            "  - broken: yaml:\n"
            "---\n"
            "\n"
            "## Instructions\n"
            "This should fail.\n"
        )

        loader = SkillLoader()
        with pytest.raises(SkillParseError):
            loader.load_skill(skill_dir)

    def test_discover_skills_multiple(self, tmp_path):
        """Test discovering multiple skills."""
        for i in range(1, 4):
            skill_dir = tmp_path / f"skill_{i}"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                f"---\n"
                f'name: "Skill {i}"\n'
                f'description: "Skill {i} description"\n'
                f'category: "test"\n'
                f"---\n"
                f"\n"
                f"## Instructions\n"
                f"Instructions for skill {i}\n"
            )

        loader = SkillLoader()
        skills = loader.discover_skills(tmp_path)

        assert len(skills) == 3
        skill_names = [s.name for s in skills]
        assert "Skill 1" in skill_names
        assert "Skill 2" in skill_names
        assert "Skill 3" in skill_names

    def test_discover_skills_empty_directory(self, tmp_path):
        """Test discovering skills in an empty directory."""
        loader = SkillLoader()
        skills = loader.discover_skills(tmp_path)

        assert len(skills) == 0

    def test_discover_skills_nested(self, tmp_path):
        """Test that discover_skills only finds direct children."""
        parent_dir = tmp_path / "parent_skill"
        parent_dir.mkdir()
        (parent_dir / "SKILL.md").write_text(
            "---\n"
            'name: "Parent Skill"\n'
            'description: "Parent"\n'
            'category: "test"\n'
            "---\n"
            "\n"
            "## Instructions\n"
            "Parent instructions.\n"
        )

        child_dir = parent_dir / "child_skill"
        child_dir.mkdir()
        (child_dir / "SKILL.md").write_text(
            "---\n"
            'name: "Child Skill"\n'
            'description: "Child"\n'
            'category: "test"\n'
            "---\n"
            "\n"
            "## Instructions\n"
            "Child instructions.\n"
        )

        loader = SkillLoader()
        skills = loader.discover_skills(tmp_path)

        # Should only find parent skill (direct child)
        assert len(skills) == 1
        assert skills[0].name == "Parent Skill"

    def test_load_skill_with_special_chars(self, tmp_path):
        """Test loading a skill with special characters in content."""
        skill_dir = tmp_path / "special_skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n"
            'name: "Special Skill"\n'
            'description: "Testing special chars"\n'
            'category: "test"\n'
            "---\n"
            "\n"
            "## Instructions\n"
            "Use these tools: `tool1`, `tool2`\n"
            "Code: ```python\n"
            "print('hello')\n"
            "```\n"
        )

        loader = SkillLoader()
        skill = loader.load_skill(skill_dir)

        assert skill.name == "Special Skill"
        assert "```python" in skill.instructions
        assert "`tool1`" in skill.instructions
