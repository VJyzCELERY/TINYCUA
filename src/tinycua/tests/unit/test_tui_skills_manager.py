"""Unit tests for TUI SkillsManager."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestSkillsManager:
    """Tests for SkillsManager."""

    def test_skills_manager_initializes(self):
        """Test skills manager initializes correctly."""
        from tinycua.tui.skills_manager import SkillsManager

        manager = SkillsManager()
        assert manager is not None

    def test_load_skills(self):
        """Test loading skills."""
        from tinycua.tui.skills_manager import SkillsManager

        manager = SkillsManager(skill_directories=[Path("/tmp/nonexistent")])
        result = manager.load_skills()

        assert isinstance(result, bool)

    def test_reload_skills(self):
        """Test reloading skills."""
        from tinycua.tui.skills_manager import SkillsManager

        manager = SkillsManager(skill_directories=[Path("/tmp/nonexistent")])
        result = manager.reload_skills()

        assert isinstance(result, bool)

    def test_list_skills(self):
        """Test listing skills."""
        from tinycua.tui.skills_manager import SkillsManager

        manager = SkillsManager(skill_directories=[Path("/tmp/nonexistent")])
        skills = manager.list_skills()

        assert isinstance(skills, list)

    def test_get_categories(self):
        """Test getting skill categories."""
        from tinycua.tui.skills_manager import SkillsManager

        manager = SkillsManager(skill_directories=[Path("/tmp/nonexistent")])
        categories = manager.get_categories()

        assert isinstance(categories, list)

    def test_add_skill_directory(self):
        """Test adding a skill directory."""
        from tinycua.tui.skills_manager import SkillsManager

        manager = SkillsManager()
        new_dir = Path("/tmp/test_skills")
        manager.add_skill_directory(new_dir)

        assert new_dir in manager._skill_directories


class TestSkillInfo:
    """Tests for SkillInfo dataclass."""

    def test_skill_info_creation(self):
        """Test SkillInfo creation."""
        from tinycua.tui.skills_manager import SkillInfo

        info = SkillInfo(
            name="test_skill",
            description="A test skill",
            category="testing",
            source="/tmp/test_skill",
        )

        assert info.name == "test_skill"
        assert info.description == "A test skill"
        assert info.category == "testing"
        assert info.source == "/tmp/test_skill"
