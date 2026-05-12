"""Integration tests for YAML agent loading and full serialization round-trip."""

from pathlib import Path

import yaml

from tinycua_sdk import Agent
from tinycua_sdk.agent.config import AgentConfig
from tinycua_sdk.agent.llm_model import LanguageModel


class TestInt07LoadingAgent:
    """Test suite for Agent YAML round-trip and file loading."""

    def test_int_01_yaml_export_import_round_trip(self):
        """YAML export -> parse -> from_dict preserves config."""
        agent = Agent(
            name="yaml-roundtrip",
            instructions="Round-trip test.",
            llm_model=LanguageModel(api_key="sk-roundtrip"),
        )
        yaml_str = agent.to_yaml(redact_sensitive=False)
        parsed = yaml.safe_load(yaml_str)
        restored = Agent.from_dict(parsed)
        assert restored.to_config() == agent.to_config()

    def test_int_02_yaml_file_load(self, tmp_path: Path):
        """Write YAML file -> from_yaml_file restores agent."""
        agent = Agent(
            name="yaml-file-load",
            instructions="Loaded from YAML file.",
            llm_model=LanguageModel(api_key="sk-file-load"),
        )
        yaml_path = tmp_path / "agent.yaml"
        yaml_path.write_text(agent.to_yaml())

        restored = Agent.from_yaml_file(yaml_path)
        assert restored.name == "yaml-file-load"
        assert restored.instructions == "Loaded from YAML file."
        assert restored.to_config()["llm_model"]["api_key"] != "***"

    def test_int_03_yaml_redacted_export(self):
        """to_yaml with redact_sensitive=True default masks api_key."""
        agent = Agent(
            name="redacted-yaml",
            llm_model=LanguageModel(api_key="sk-secret-sensitive"),
        )
        yaml_str = agent.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert parsed["llm_model"]["api_key"] == "***"

    def test_int_04_yaml_exposed_export(self):
        """to_yaml with redact_sensitive=False exposes api_key."""
        agent = Agent(
            name="exposed-yaml",
            llm_model=LanguageModel(api_key="sk-secret-exposed"),
        )
        yaml_str = agent.to_yaml(redact_sensitive=False)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["llm_model"]["api_key"] == "sk-secret-exposed"
