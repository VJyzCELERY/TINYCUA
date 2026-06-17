"""Unit tests for AgentConfig and config loader."""

from __future__ import annotations

import pytest
import yaml

from agents_benchmark.config import AgentConfig, load_config


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_config_dataclass_fields(self):
        """AgentConfig must have expected fields with correct defaults."""
        config = AgentConfig(
            name="hermes",
            model="gpt-4",
            api_base="https://api.openai.com/v1",
            api_key_env="HERMES_API_KEY",
            docker_image="hermes-agent",
            dockerfile_path="docker/Dockerfile.hermes",
        )
        assert config.name == "hermes"
        assert config.model == "gpt-4"
        assert config.api_base == "https://api.openai.com/v1"
        assert config.api_key_env == "HERMES_API_KEY"
        assert config.docker_image == "hermes-agent"
        assert config.dockerfile_path == "docker/Dockerfile.hermes"
        assert config.timeout_seconds == 300
        assert config.extra_env == {}


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_path):
        """load_config must return AgentConfig for valid YAML."""
        config_path = tmp_path / "valid.yaml"
        data = {
            "name": "hermes",
            "model": "claude-3",
            "api_base": "https://api.anthropic.com/v1",
            "api_key_env": "ANTHROPIC_API_KEY",
            "docker_image": "hermes-agent",
        }
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        config = load_config(str(config_path))
        assert config.name == "hermes"
        assert config.model == "claude-3"
        assert config.api_base == "https://api.anthropic.com/v1"
        assert config.api_key_env == "ANTHROPIC_API_KEY"
        assert config.docker_image == "hermes-agent"

    def test_load_config_missing_required_fields(self, tmp_path):
        """load_config must raise ValueError for missing required fields."""
        config_path = tmp_path / "bad.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"name": "hermes", "model": "gpt-4"}, f)

        with pytest.raises(ValueError, match="missing required fields"):
            load_config(str(config_path))

    def test_load_config_env_var_interpolation(self, tmp_path, monkeypatch):
        """load_config must resolve ${VAR} references from environment."""
        monkeypatch.setenv("TEST_API_KEY", "sk-secret-123")
        config_path = tmp_path / "env.yaml"
        data = {
            "name": "hermes",
            "model": "gpt-4",
            "api_base": "https://api.openai.com/v1",
            "api_key_env": "TEST_API_KEY",
            "docker_image": "hermes-agent",
        }
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        config = load_config(str(config_path))
        assert config.api_key_env == "TEST_API_KEY"

    def test_load_config_default_values(self, tmp_path):
        """load_config must apply defaults for optional fields."""
        config_path = tmp_path / "defaults.yaml"
        data = {
            "name": "hermes",
            "model": "gpt-4",
            "api_base": "https://api.openai.com/v1",
            "api_key_env": "HERMES_API_KEY",
            "docker_image": "hermes-agent",
        }
        with open(config_path, "w") as f:
            yaml.dump(data, f)

        config = load_config(str(config_path))
        assert config.timeout_seconds == 300
        assert config.extra_env == {}

    def test_load_config_missing_file(self):
        """load_config must raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path.yaml")

    def test_load_config_not_a_mapping(self, tmp_path):
        """load_config must raise ValueError for non-mapping YAML."""
        config_path = tmp_path / "scalar.yaml"
        with open(config_path, "w") as f:
            f.write("just a string\n")

        with pytest.raises(ValueError, match="YAML mapping"):
            load_config(str(config_path))
