"""Integration tests for configuration."""

import pytest
from tinycua_sdk import SDKConfig
from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.llm_model import LLMModel


class TestSDKConfig:
    """Integration tests for SDKConfig."""

    def test_sdk_config_from_yaml(self, tmp_path):
        """SDKConfig from YAML file."""
        config_path = tmp_path / "sdk.yaml"
        config_path.write_text("llm:\n  provider: openai\n  model: gpt-4\n")
        config = SDKConfig.from_yaml(config_path)
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4"

    def test_sdk_config_from_json(self, tmp_path):
        """SDKConfig from JSON file."""
        config_path = tmp_path / "sdk.json"
        config_path.write_text('{"llm": {"provider": "openai", "model": "gpt-4"}}')
        config = SDKConfig.from_json(config_path)
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4"


class TestAgentConfig:
    """Integration tests for AgentConfig."""

    def test_agent_config_round_trip(self):
        """AgentConfig round-trip through dict."""
        original = AgentConfig(
            name="test",
            instructions="Test instructions",
            llm_model=LLMModel(model_name="gpt-4"),
            policy=AgentPolicy(temperature=0.5),
        )
        config = original.to_config()
        restored = AgentConfig.from_config(config)
        assert restored.name == "test"
        assert restored.instructions == "Test instructions"
        assert restored.llm_model.model_name == "gpt-4"
        assert restored.policy.temperature == 0.5
