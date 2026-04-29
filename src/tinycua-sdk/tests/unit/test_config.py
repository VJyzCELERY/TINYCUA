"""Tests for config serialization and deserialization."""

import os
import tempfile

import pytest


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_agent_config_defaults(self):
        """AgentConfig has sensible defaults."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig()
        assert config.name == "assistant"
        assert config.instructions == ""
        assert config.max_depth == 3

    def test_agent_config_to_dict(self):
        """AgentConfig.to_dict() returns a plain dict."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig(name="test")
        d = config.to_dict()
        assert d["name"] == "test"

    def test_agent_config_from_dict(self):
        """AgentConfig.from_dict() reconstructs the config."""
        from tinycua_sdk import AgentConfig

        d = {"name": "test", "instructions": "Be helpful"}
        config = AgentConfig.from_dict(d)
        assert config.name == "test"
        assert config.instructions == "Be helpful"

    def test_agent_config_no_system_prompt_field(self):
        """AgentConfig does not have a system_prompt field."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig()
        assert not hasattr(config, "system_prompt")

    def test_agent_config_no_session_id_field(self):
        """AgentConfig does not have a session_id field."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig()
        assert not hasattr(config, "session_id")

    def test_agent_config_no_memory_fields(self):
        """AgentConfig does not have memory fields."""
        from tinycua_sdk import AgentConfig

        config = AgentConfig()
        assert not hasattr(config, "short_term_memory")
        assert not hasattr(config, "long_term_memory")


class TestSDKConfig:
    """Tests for SDKConfig."""

    def test_sdk_config_defaults(self):
        """SDKConfig has sensible defaults."""
        from tinycua_sdk import SDKConfig

        config = SDKConfig()
        assert hasattr(config, "llm")
        assert hasattr(config, "loop")
        assert hasattr(config, "skills")
        assert hasattr(config, "backend_url")

    def test_sdk_config_no_memory_field(self):
        """SDKConfig does not have a memory field."""
        from tinycua_sdk import SDKConfig

        config = SDKConfig()
        assert not hasattr(config, "memory")

    def test_sdk_config_no_session_field(self):
        """SDKConfig does not have a session field."""
        from tinycua_sdk import SDKConfig

        config = SDKConfig()
        assert not hasattr(config, "session")

    def test_sdk_config_no_environment_field(self):
        """SDKConfig does not have an environment field."""
        from tinycua_sdk import SDKConfig

        config = SDKConfig()
        assert not hasattr(config, "environment")

    def test_sdk_config_from_env(self, monkeypatch):
        """SDKConfig.from_env() reads environment variables."""
        from tinycua_sdk import SDKConfig

        monkeypatch.setenv("TINYCUA_MODEL", "gpt-4")
        monkeypatch.setenv("TINYCUA_BACKEND_URL", "http://prod.example.com")

        config = SDKConfig.from_env()
        assert config.llm.model_name == "gpt-4"
        assert config.backend_url == "http://prod.example.com"

    def test_sdk_config_from_yaml(self):
        """SDKConfig.from_yaml() loads from a YAML file."""
        from tinycua_sdk import SDKConfig

        yaml_content = """
llm:
  model_name: gpt-4
backend_url: http://prod.example.com
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = SDKConfig.from_yaml(f.name)

        assert config.llm.model_name == "gpt-4"
        assert config.backend_url == "http://prod.example.com"

        os.unlink(f.name)


class TestConfigRoundTrip:
    """Tests for config serialization round-trips."""

    def test_agent_config_round_trip(self):
        """AgentConfig serializes and deserializes correctly."""
        from tinycua_sdk import AgentConfig, LLMModel

        original = AgentConfig(
            name="test",
            llm_model=LLMModel(model_name="gpt-4"),
        )
        d = original.to_dict()
        restored = AgentConfig.from_dict(d)
        assert restored.name == "test"
        assert restored.llm_model.model_name == "gpt-4"
