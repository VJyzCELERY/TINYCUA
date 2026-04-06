"""Unit tests for AgentConfig skills fields."""

import pytest
from pathlib import Path

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy


class TestAgentConfigSkills:
    """Tests for AgentConfig skills-related fields."""

    def test_skills_field_default_empty_list(self):
        """Test that skills defaults to empty list."""
        config = AgentConfig()
        assert config.skills == []
        assert isinstance(config.skills, list)

    def test_skills_field_in_init(self):
        """Test that skills can be set in constructor."""
        config = AgentConfig(skills=["web-researcher", "data-analyst"])
        assert config.skills == ["web-researcher", "data-analyst"]

    def test_skill_dirs_field_default_empty_list(self):
        """Test that skill_dirs defaults to empty list."""
        config = AgentConfig()
        assert config.skill_dirs == []
        assert isinstance(config.skill_dirs, list)

    def test_skill_dirs_field_in_init(self):
        """Test that skill_dirs can be set in constructor."""
        config = AgentConfig(
            skill_dirs=[Path("/tmp/skills"), Path("~/my-skills")]
        )
        assert len(config.skill_dirs) == 2
        assert isinstance(config.skill_dirs[0], Path)

    def test_auto_load_dependencies_field_default_true(self):
        """Test that auto_load_dependencies defaults to True."""
        config = AgentConfig()
        assert config.auto_load_dependencies is True

    def test_auto_load_dependencies_field_in_init(self):
        """Test that auto_load_dependencies can be set in constructor."""
        config = AgentConfig(auto_load_dependencies=False)
        assert config.auto_load_dependencies is False

    def test_to_config_serializes_skills(self):
        """Test that to_config() includes skills field."""
        config = AgentConfig(
            name="test-agent",
            skills=["web-researcher", "data-analyst"],
        )
        config_dict = config.to_config()
        assert "skills" in config_dict
        assert config_dict["skills"] == ["web-researcher", "data-analyst"]

    def test_to_config_serializes_skill_dirs(self):
        """Test that to_config() includes skill_dirs field."""
        config = AgentConfig(
            name="test-agent",
            skill_dirs=[Path("/tmp/skills"), Path("~/my-skills")],
        )
        config_dict = config.to_config()
        assert "skill_dirs" in config_dict
        assert len(config_dict["skill_dirs"]) == 2

    def test_to_config_serializes_auto_load_dependencies(self):
        """Test that to_config() includes auto_load_dependencies field."""
        config = AgentConfig(
            name="test-agent",
            auto_load_dependencies=False,
        )
        config_dict = config.to_config()
        assert "auto_load_dependencies" in config_dict
        assert config_dict["auto_load_dependencies"] is False

    def test_to_config_includes_metadata(self):
        """Test that to_config() includes metadata field."""
        config = AgentConfig(
            name="test-agent",
            metadata={"custom_key": "custom_value"},
        )
        config_dict = config.to_config()
        assert "metadata" in config_dict
        assert config_dict["metadata"] == {"custom_key": "custom_value"}

    def test_from_config_parses_skills(self):
        """Test that from_config() parses skills from top-level field."""
        data = {
            "name": "test-agent",
            "skills": ["web-researcher", "data-analyst"],
        }
        config = AgentConfig.from_config(data)
        assert config.skills == ["web-researcher", "data-analyst"]

    def test_from_config_parses_skill_dirs(self):
        """Test that from_config() parses skill_dirs from top-level field."""
        data = {
            "name": "test-agent",
            "skill_dirs": ["/tmp/skills", "~/my-skills"],
        }
        config = AgentConfig.from_config(data)
        assert len(config.skill_dirs) == 2
        assert isinstance(config.skill_dirs[0], Path)

    def test_from_config_parses_auto_load_dependencies(self):
        """Test that from_config() parses auto_load_dependencies."""
        data = {
            "name": "test-agent",
            "auto_load_dependencies": False,
        }
        config = AgentConfig.from_config(data)
        assert config.auto_load_dependencies is False

    def test_from_config_parses_metadata(self):
        """Test that from_config() parses metadata field."""
        data = {
            "name": "test-agent",
            "metadata": {"custom_key": "custom_value", "description": "A test agent"},
        }
        config = AgentConfig.from_config(data)
        assert config.metadata == {"custom_key": "custom_value", "description": "A test agent"}

    def test_from_config_backward_compat_skills_in_metadata(self):
        """Test backward compatibility - skills in metadata still works."""
        data = {
            "name": "test-agent",
            "metadata": {"skills": ["web-researcher", "data-analyst"]},
        }
        config = AgentConfig.from_config(data)
        assert config.skills == ["web-researcher", "data-analyst"]

    def test_from_config_top_level_skills_takes_precedence(self):
        """Test that top-level skills takes precedence over metadata."""
        data = {
            "name": "test-agent",
            "skills": ["top-level-skill"],
            "metadata": {"skills": ["metadata-skill"]},
        }
        config = AgentConfig.from_config(data)
        # Top-level should take precedence
        assert config.skills == ["top-level-skill"]

    def test_from_config_no_skills_returns_empty_list(self):
        """Test that from_config() returns empty list when no skills specified."""
        data = {"name": "test-agent"}
        config = AgentConfig.from_config(data)
        assert config.skills == []

    def test_from_config_no_skill_dirs_returns_empty_list(self):
        """Test that from_config() returns empty list when no skill_dirs specified."""
        data = {"name": "test-agent"}
        config = AgentConfig.from_config(data)
        assert config.skill_dirs == []

    def test_from_config_default_auto_load_dependencies_true(self):
        """Test that auto_load_dependencies defaults to True when not specified."""
        data = {"name": "test-agent"}
        config = AgentConfig.from_config(data)
        assert config.auto_load_dependencies is True

    def test_roundtrip_skills(self):
        """Test that skills survive roundtrip serialization/deserialization."""
        original = AgentConfig(
            name="test-agent",
            skills=["web-researcher", "data-analyst"],
            skill_dirs=[Path("/tmp/skills")],
            auto_load_dependencies=False,
            metadata={"custom": "value"},
        )
        config_dict = original.to_config()
        restored = AgentConfig.from_config(config_dict)
        assert restored.skills == original.skills
        assert restored.skill_dirs == original.skill_dirs
        assert restored.auto_load_dependencies == original.auto_load_dependencies
        assert restored.metadata == original.metadata
