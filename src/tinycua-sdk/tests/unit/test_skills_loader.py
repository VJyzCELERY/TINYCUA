# Unit tests for Skill.load()

import pytest
from tinycua_sdk.skills.models import Skill


class TestSkillLoad:
    """Tests for Skill.load() classmethod."""

    def test_load_skill_basic(self):
        """Test loading a basic skill from markdown text."""
        text = (
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
        skill = Skill.load(text)

        assert skill.name == "Test Skill"
        assert skill.description == "A test skill"
        assert skill.category == "testing"
        assert "tool_one" in skill.tools
        assert "tool_two" in skill.tools
        assert "dep_one" in skill.dependencies
        assert "Detailed instructions" in skill.instructions

    def test_load_skill_no_frontmatter(self):
        """Test loading markdown without YAML frontmatter."""
        text = "# Helper\n\n## Description\nA simple helper skill.\n\n## Instructions\nDo something helpful.\n"
        skill = Skill.load(text)

        assert skill.name == "unnamed"
        assert skill.description == "A simple helper skill."
        assert "Do something helpful" in skill.instructions

    def test_load_skill_invalid_yaml(self):
        """Test handling of invalid YAML in frontmatter."""
        text = (
            "---\n"
            'name: "Invalid Skill"\n'
            "description: This has invalid yaml:\n"
            "  - broken: yaml:\n"
            "---\n"
            "\n"
            "## Instructions\n"
            "This should fail.\n"
        )

        with pytest.raises(ValueError, match="Invalid YAML"):
            Skill.load(text)

    def test_load_skill_invalid_frontmatter_format(self):
        """Test handling of malformed frontmatter."""
        text = "---\nname: test\n"

        with pytest.raises(ValueError, match="Invalid YAML frontmatter"):
            Skill.load(text)

    def test_load_skill_with_sections(self):
        """Test parsing description and instructions sections."""
        text = (
            "---\n"
            'name: "Sectioned Skill"\n'
            "---\n"
            "\n"
            "## Description\n"
            "This is the description.\n"
            "\n"
            "## Instructions\n"
            "This is the instruction.\n"
            "\n"
            "## Tools\n"
            "- tool_a\n"
        )
        skill = Skill.load(text)

        assert skill.name == "Sectioned Skill"
        assert skill.description == "This is the description."
        assert "This is the instruction." in skill.instructions

    def test_load_skill_empty_text(self):
        """Test loading empty text."""
        skill = Skill.load("")
        assert skill.name == "unnamed"
        assert skill.description == ""
        assert skill.instructions == ""

    def test_load_skill_special_chars(self):
        """Test loading a skill with special characters in content."""
        text = (
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
        skill = Skill.load(text)

        assert skill.name == "Special Skill"
        assert "```python" in skill.instructions
        assert "`tool1`" in skill.instructions
