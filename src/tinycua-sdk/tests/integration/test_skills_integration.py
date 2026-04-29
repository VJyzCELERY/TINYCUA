# Integration tests for Skills System

import time

from tinycua_sdk.skills.models import Skill
from tinycua_sdk.skills.registry import SkillRegistry


class TestSkillsColdStart:
    """Integration tests for skills cold start performance."""

    def test_cold_start_10_skills_under_2_seconds(self, tmp_path):
        """Test cold start with 10+ skills completes in < 2 seconds."""
        # Create 10 skill directories
        for i in range(10):
            skill_dir = tmp_path / f"skill_{i}"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                f"---\n"
                f'name: "Skill {i}"\n'
                f'description: "Test skill {i}"\n'
                f'category: "test"\n'
                f'tools:\n'
                f'  - tool_{i}_a\n'
                f'  - tool_{i}_b\n'
                f"---\n"
                f"\n"
                f"## Instructions\n"
                f"Instructions for skill {i}.\n"
            )

        # Measure cold start time
        start = time.time()
        registry = SkillRegistry()
        for entry in sorted(tmp_path.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                skill_md = entry / "SKILL.md"
                if skill_md.exists():
                    content = skill_md.read_text(encoding="utf-8")
                    skill = Skill.load(content)
                    skill.source = str(entry)
                    registry.register(skill)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"Cold start took {elapsed:.2f}s, expected < 2s"
        assert len(registry.list_skills()) == 10

    def test_skills_list_and_view(self, tmp_path):
        """Test skills_list and skill_view tools work end-to-end."""
        # Create a skill
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            'name: "Test Skill"\n'
            'description: "A test skill"\n'
            'category: "testing"\n'
            "tools:\n"
            "  - tool_one\n"
            "  - tool_two\n"
            "---\n"
            "\n"
            "## Instructions\n"
            "Do something specific with tool_one and tool_two.\n"
        )

        # Load skills
        registry = SkillRegistry()
        for entry in sorted(tmp_path.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                skill_md = entry / "SKILL.md"
                if skill_md.exists():
                    content = skill_md.read_text(encoding="utf-8")
                    skill = Skill.load(content)
                    skill.source = str(entry)
                    registry.register(skill)

        # Test skills_list
        from tinycua_sdk.tools.native.skills_tools import create_skills_list_tool

        list_tool = create_skills_list_tool(registry)
        result = list_tool.invoke()

        assert "skills" in result
        assert len(result["skills"]) == 1
        assert result["skills"][0]["name"] == "Test Skill"

        # Test skill_view
        from tinycua_sdk.tools.native.skills_tools import create_skill_view_tool

        view_tool = create_skill_view_tool(registry)
        result = view_tool.invoke(skill_name="Test Skill")

        assert result["name"] == "Test Skill"
        assert result["description"] == "A test skill"
        assert "tool_one" in result["tools"]
        assert "Do something specific" in result["instructions"]
