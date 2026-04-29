"""Tests for config serialization and deserialization."""

import json
import os
import tempfile

import pytest
import yaml


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


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_llm_config_defaults(self):
        """LLMConfig has sensible defaults."""
        from tinycua_sdk.core.config import LLMConfig

        config = LLMConfig()
        assert config.provider == "openai-compatible"
        assert config.model == "gpt-4o-mini"
        assert config.base_url == "http://localhost:1234/v1"
        assert config.temperature == 1.0

    def test_llm_config_frozen(self):
        """LLMConfig is immutable."""
        from tinycua_sdk.core.config import LLMConfig

        config = LLMConfig()
        with pytest.raises(Exception):
            config.model = "other"

    def test_llm_config_round_trip(self):
        """LLMConfig serializes and deserializes correctly."""
        from tinycua_sdk.core.config import LLMConfig

        original = LLMConfig(model="gpt-4", temperature=0.5)
        d = original.to_dict()
        restored = LLMConfig.from_dict(d)
        assert restored.model == "gpt-4"
        assert restored.temperature == 0.5


class TestLoopConfig:
    """Tests for LoopConfig."""

    def test_loop_config_defaults(self):
        """LoopConfig has sensible defaults."""
        from tinycua_sdk.core.config import LoopConfig

        config = LoopConfig()
        assert config.max_iterations == 5
        assert not hasattr(config, "type")

    def test_loop_config_frozen(self):
        """LoopConfig is immutable."""
        from tinycua_sdk.core.config import LoopConfig

        config = LoopConfig()
        with pytest.raises(Exception):
            config.max_iterations = 10

    def test_loop_config_round_trip(self):
        """LoopConfig serializes and deserializes correctly."""
        from tinycua_sdk.core.config import LoopConfig

        original = LoopConfig(max_iterations=10)
        d = original.to_dict()
        restored = LoopConfig.from_dict(d)
        assert restored.max_iterations == 10


class TestSkillsConfig:
    """Tests for SkillsConfig."""

    def test_skills_config_defaults(self):
        """SkillsConfig has sensible defaults."""
        from tinycua_sdk.core.config import SkillsConfig

        config = SkillsConfig()
        assert config.directories == ["./skills"]
        assert config.auto_load is True
        assert not hasattr(config, "auto_improve")

    def test_skills_config_frozen(self):
        """SkillsConfig is immutable."""
        from tinycua_sdk.core.config import SkillsConfig

        config = SkillsConfig()
        with pytest.raises(Exception):
            config.auto_load = False

    def test_skills_config_round_trip(self):
        """SkillsConfig serializes and deserializes correctly."""
        from tinycua_sdk.core.config import SkillsConfig

        original = SkillsConfig(directories=["./custom"], auto_load=False)
        d = original.to_dict()
        restored = SkillsConfig.from_dict(d)
        assert restored.directories == ["./custom"]
        assert restored.auto_load is False


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

    def test_sdk_config_frozen(self):
        """SDKConfig is immutable."""
        from tinycua_sdk import SDKConfig

        config = SDKConfig()
        with pytest.raises(Exception):
            config.backend_url = "http://other"

    def test_sdk_config_from_env(self, monkeypatch):
        """SDKConfig.from_env() reads environment variables."""
        from tinycua_sdk import SDKConfig

        monkeypatch.setenv("TINYCUA_MODEL", "gpt-4")
        monkeypatch.setenv("TINYCUA_BACKEND_URL", "http://prod.example.com")

        config = SDKConfig.from_env()
        assert config.llm.model == "gpt-4"
        assert config.backend_url == "http://prod.example.com"

    def test_sdk_config_from_yaml(self):
        """SDKConfig.from_yaml() loads from a YAML file."""
        from tinycua_sdk import SDKConfig

        yaml_content = """
llm:
  model: gpt-4
backend_url: http://prod.example.com
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config = SDKConfig.from_yaml(f.name)

        assert config.llm.model == "gpt-4"
        assert config.backend_url == "http://prod.example.com"

        os.unlink(f.name)

    def test_sdk_config_from_json(self):
        """SDKConfig.from_json() loads from a JSON file."""
        from tinycua_sdk import SDKConfig

        data = {"llm": {"model": "gpt-4"}, "backend_url": "http://prod.example.com"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            config = SDKConfig.from_json(f.name)

        assert config.llm.model == "gpt-4"
        assert config.backend_url == "http://prod.example.com"

        os.unlink(f.name)

    def test_sdk_config_to_yaml(self):
        """SDKConfig.to_yaml() writes to a YAML file."""
        from tinycua_sdk import SDKConfig

        config = SDKConfig(backend_url="http://out.example.com")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config.to_yaml(f.name)
            with open(f.name, "r") as rf:
                loaded = yaml.safe_load(rf)
            assert loaded["backend_url"] == "http://out.example.com"
            os.unlink(f.name)

    def test_sdk_config_to_json(self):
        """SDKConfig.to_json() writes to a JSON file."""
        from tinycua_sdk import SDKConfig

        config = SDKConfig(backend_url="http://out.example.com")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config.to_json(f.name)
            with open(f.name, "r") as rf:
                loaded = json.load(rf)
            assert loaded["backend_url"] == "http://out.example.com"
            os.unlink(f.name)

    def test_sdk_config_round_trip(self):
        """SDKConfig serializes and deserializes correctly."""
        from tinycua_sdk import SDKConfig

        original = SDKConfig(backend_url="http://test.example.com")
        d = original.to_dict()
        restored = SDKConfig.from_dict(d)
        assert restored.backend_url == "http://test.example.com"


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
