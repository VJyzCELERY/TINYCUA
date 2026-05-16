"""Integration tests for agent JSON/YAML export, loading, and redaction."""

import json
from pathlib import Path

import yaml

from tinycua_sdk import Agent, Skill
from tinycua_sdk.agent.llm_model import LanguageModel


class TestAgentExport:
    """Test suite for Agent serialization and redaction."""

    def test_agent_dict_round_trip(self):
        """Agent to_config -> from_dict round-trip preserves equality."""
        agent = Agent(
            name="test-agent",
            instructions="You are a test agent.",
            llm_model=LanguageModel(api_key="sk-secret-123"),
            skills=[
                Skill(
                    name="coder",
                    description="Write code",
                    instructions="Use PEP 8.",
                ),
            ],
            metadata={"version": "1.0"},
        )
        config = agent.to_config()
        restored = Agent.from_dict(config)
        assert restored.to_config() == config

    def test_agent_json_redaction(self):
        """Redacted JSON masks api_key; non-redacted shows full value."""
        agent = Agent(
            name="test-agent",
            llm_model=LanguageModel(api_key="sk-secret-456"),
        )
        redacted = json.loads(agent.to_json(redact_sensitive=True))
        exposed = json.loads(agent.to_json(redact_sensitive=False))

        assert redacted["llm_model"]["api_key"] == "***"
        assert exposed["llm_model"]["api_key"] == "sk-secret-456"

    def test_agent_yaml_redaction(self):
        """Redacted YAML masks api_key; non-redacted shows full value."""
        agent = Agent(
            name="test-agent",
            llm_model=LanguageModel(api_key="sk-secret-789"),
        )
        redacted = yaml.safe_load(agent.to_yaml(redact_sensitive=True))
        exposed = yaml.safe_load(agent.to_yaml(redact_sensitive=False))

        assert redacted["llm_model"]["api_key"] == "***"
        assert exposed["llm_model"]["api_key"] == "sk-secret-789"

    def test_agent_json_file_round_trip(self, tmp_path: Path):
        """Write JSON file (unredacted) -> load back -> assert equivalence."""
        agent = Agent(
            name="file-agent",
            instructions="From file.",
            llm_model=LanguageModel(api_key="sk-file-key"),
        )
        json_path = tmp_path / "agent.json"
        json_path.write_text(agent.to_json(redact_sensitive=False))

        restored = Agent.from_json_file(json_path)
        assert restored.to_config() == agent.to_config()

    def test_agent_yaml_file_round_trip(self, tmp_path: Path):
        """Write YAML file (unredacted) -> load back -> assert equivalence."""
        agent = Agent(
            name="yaml-agent",
            instructions="From YAML file.",
            llm_model=LanguageModel(api_key="sk-yaml-key"),
        )
        yaml_path = tmp_path / "agent.yaml"
        yaml_path.write_text(agent.to_yaml(redact_sensitive=False))

        restored = Agent.from_yaml_file(yaml_path)
        assert restored.to_config() == agent.to_config()


class TestAgentLoading:
    """Test suite for Agent YAML round-trip and file loading."""

    def test_yaml_export_import_round_trip(self):
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

    def test_yaml_file_load(self, tmp_path: Path):
        """Write YAML file -> from_yaml_file restores agent."""
        agent = Agent(
            name="yaml-file-load",
            instructions="Loaded from YAML file.",
            llm_model=LanguageModel(api_key="sk-file-load"),
        )
        yaml_path = tmp_path / "agent.yaml"
        yaml_path.write_text(agent.to_yaml(redact_sensitive=False))

        restored = Agent.from_yaml_file(yaml_path)
        assert restored.name == "yaml-file-load"
        assert restored.instructions == "Loaded from YAML file."
        assert (
            restored.to_config()["llm_model"]["api_key"].get_secret_value()
            == "sk-file-load"
        )

    def test_yaml_exposed_export(self):
        """to_yaml with redact_sensitive=False exposes api_key."""
        agent = Agent(
            name="exposed-yaml",
            llm_model=LanguageModel(api_key="sk-secret-exposed"),
        )
        yaml_str = agent.to_yaml(redact_sensitive=False)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["llm_model"]["api_key"] == "sk-secret-exposed"
