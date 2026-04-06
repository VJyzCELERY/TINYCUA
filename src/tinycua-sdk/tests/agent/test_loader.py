"""Unit tests for AgentLoader."""

import pytest
from pathlib import Path

from tinycua_sdk.agent.loader import AgentLoader, AgentNotFoundError, AgentParseError
from tinycua_sdk.agent.config import AgentConfig


@pytest.fixture
def loader():
    return AgentLoader()


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent.parent / "fixtures" / "agents"


class TestAgentLoader:
    """Tests for AgentLoader class."""

    def test_load_from_file(self, loader, fixtures_dir):
        """Test loading agent from AGENT.md file."""
        agent_path = fixtures_dir / "basic" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        assert isinstance(config, AgentConfig)
        assert config.name == "basic-agent"
        assert (
            config.metadata.get("description")
            == "A basic agent with minimal configuration"
        )

    def test_load_from_directory(self, loader, fixtures_dir):
        """Test loading agent from directory (auto-discovery)."""
        agent_dir = fixtures_dir / "basic"
        config = loader.load_from_markdown(agent_dir)

        assert isinstance(config, AgentConfig)
        assert config.name == "basic-agent"

    def test_load_full_agent(self, loader, fixtures_dir):
        """Test loading agent with all fields."""
        agent_path = fixtures_dir / "full" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        assert config.name == "full-agent"
        assert (
            config.metadata.get("description")
            == "A full-featured agent with all configuration options"
        )
        assert config.model == "gpt-4o-mini"
        assert config.provider == "openai"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.api_key == "test-api-key-placeholder"

    def test_load_agent_with_tools(self, loader, fixtures_dir):
        """Test loading agent with tools specified."""
        agent_path = fixtures_dir / "full" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        tool_names = [t if isinstance(t, str) else t.name for t in config.tools]
        assert "search_web" in tool_names
        assert "calculate" in tool_names

    def test_load_agent_with_skills(self, loader, fixtures_dir):
        """Test loading agent with skills specified."""
        agent_path = fixtures_dir / "with-skills" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        # Skills should be stored in metadata
        assert config.metadata is not None
        assert "skills" in config.metadata
        assert config.metadata["skills"] == ["web-researcher", "data-analyst"]

    def test_load_agent_with_loop(self, loader, fixtures_dir):
        """Test loading agent with loop configuration."""
        agent_path = fixtures_dir / "with-loop" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        # Loop configuration should be stored
        assert config.loop is not None
        assert config.loop.get("type") == "reflective"
        assert config.loop.get("max_iterations") == 5

    def test_load_agent_with_policy(self, loader, fixtures_dir):
        """Test loading agent with policy configuration."""
        agent_path = fixtures_dir / "full" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        assert config.policy.max_tool_calls == 10
        assert config.policy.parallel_tool_calls is True
        assert config.policy.temperature == 1.0

    def test_file_not_found(self, loader, tmp_path):
        """Test error when AGENT.md doesn't exist."""
        agent_path = tmp_path / "nonexistent" / "AGENT.md"

        with pytest.raises(AgentNotFoundError):
            loader.load_from_markdown(agent_path)

    def test_invalid_yaml(self, loader, tmp_path):
        """Test error when YAML is invalid."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text(
            """---
name: invalid
- invalid: yaml: content
---

# Instructions
"""
        )

        with pytest.raises(AgentParseError):
            loader.load_from_markdown(agent_md)

    def test_missing_name_field(self, loader, tmp_path):
        """Test loading agent without name in frontmatter."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text(
            """---
description: No name agent
---

# Instructions
Test content
"""
        )

        # Should still work, using path name as fallback
        config = loader.load_from_markdown(agent_md)
        assert config.name  # Should have some name

    def test_default_system_prompt(self, loader, fixtures_dir):
        """Test that default system prompt is set."""
        agent_path = fixtures_dir / "basic" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        assert config.system_prompt == "You are a helpful assistant."

    def test_instructions_extraction(self, loader, fixtures_dir):
        """Test that markdown content is extracted as instructions."""
        agent_path = fixtures_dir / "full" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        assert config.instructions
        assert "web search" in config.instructions.lower()
        assert "calculation tools" in config.instructions.lower()

    def test_custom_system_prompt_in_yaml(self, loader, tmp_path):
        """Test custom system prompt from YAML."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text(
            """---
name: custom-prompt-agent
system_prompt: You are a specialized assistant.
---

# Instructions
Some instructions here.
"""
        )

        config = loader.load_from_markdown(agent_md)
        assert config.system_prompt == "You are a specialized assistant."

    def test_model_defaults(self, loader, tmp_path):
        """Test that model defaults are applied."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text(
            """---
name: minimal-agent
---

# Instructions
Minimal agent content.
"""
        )

        config = loader.load_from_markdown(agent_md)
        assert config.model == "gpt-5-nano"  # Default from AgentConfig
        assert config.provider == "openai"  # Default from AgentConfig

    def test_load_agent_with_skills_top_level_field(self, loader, fixtures_dir):
        """Test loading agent with skills in top-level field."""
        agent_path = fixtures_dir / "with-skills" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        # Skills should be stored in top-level field
        assert config.skills == ["web-researcher", "data-analyst"]

    def test_load_agent_with_skill_dirs(self, loader, fixtures_dir):
        """Test loading agent with skill_dirs specified."""
        agent_path = fixtures_dir / "with-skills" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        # skill_dirs should be parsed and converted to Path
        assert len(config.skill_dirs) == 1
        assert isinstance(config.skill_dirs[0], Path)
        assert str(config.skill_dirs[0]) == "/tmp/skills"

    def test_load_agent_with_auto_load_dependencies_true(self, loader, fixtures_dir):
        """Test loading agent with auto_load_dependencies true."""
        agent_path = fixtures_dir / "with-skills" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        # auto_load_dependencies should be True
        assert config.auto_load_dependencies is True

    def test_load_agent_with_auto_load_dependencies_false(self, loader, fixtures_dir):
        """Test loading agent with auto_load_dependencies false."""
        agent_path = fixtures_dir / "with-skill-dirs" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        # auto_load_dependencies should be False
        assert config.auto_load_dependencies is False

    def test_load_agent_skill_dirs_parsed_as_paths(self, loader, fixtures_dir):
        """Test that skill_dirs are parsed as Path objects."""
        agent_path = fixtures_dir / "with-skill-dirs" / "AGENT.md"
        config = loader.load_from_markdown(agent_path)

        # skill_dirs should be Path objects
        assert len(config.skill_dirs) == 2
        assert isinstance(config.skill_dirs[0], Path)
        assert isinstance(config.skill_dirs[1], Path)

    def test_load_agent_default_auto_load_dependencies(self, loader, tmp_path):
        """Test that auto_load_dependencies defaults to True."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text(
            """---
name: default-agent
---

# Instructions
Test content.
"""
        )

        config = loader.load_from_markdown(agent_md)
        assert config.auto_load_dependencies is True

    def test_load_agent_default_skill_dirs(self, loader, tmp_path):
        """Test that skill_dirs defaults to empty list."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text(
            """---
name: default-agent
---

# Instructions
Test content.
"""
        )

        config = loader.load_from_markdown(agent_md)
        assert config.skill_dirs == []

    def test_load_agent_default_skills(self, loader, tmp_path):
        """Test that skills defaults to empty list."""
        agent_md = tmp_path / "AGENT.md"
        agent_md.write_text(
            """---
name: default-agent
---

# Instructions
Test content.
"""
        )

        config = loader.load_from_markdown(agent_md)
        assert config.skills == []
