"""Integration tests for agent JSON/YAML export and redaction."""

import json
from pathlib import Path

import yaml

from tinycua_sdk import Agent, Skill
from tinycua_sdk.agent.llm_model import LanguageModel


class TestInt06ExportingAgent:
    """Test suite for Agent serialization and redaction."""

    def test_int_01_agent_dict_round_trip(self):
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

    def test_int_02_agent_json_redaction(self):
        """Redacted JSON masks api_key; non-redacted shows full value."""
        agent = Agent(
            name="test-agent",
            llm_model=LanguageModel(api_key="sk-secret-456"),
        )
        redacted = json.loads(agent.to_json(redact_sensitive=True))
        exposed = json.loads(agent.to_json(redact_sensitive=False))

        assert redacted["llm_model"]["api_key"] == "***"
        assert exposed["llm_model"]["api_key"] == "sk-secret-456"

    def test_int_03_agent_yaml_redaction(self):
        """Redacted YAML masks api_key; non-redacted shows full value."""
        agent = Agent(
            name="test-agent",
            llm_model=LanguageModel(api_key="sk-secret-789"),
        )
        redacted = yaml.safe_load(agent.to_yaml(redact_sensitive=True))
        exposed = yaml.safe_load(agent.to_yaml(redact_sensitive=False))

        assert redacted["llm_model"]["api_key"] == "***"
        assert exposed["llm_model"]["api_key"] == "sk-secret-789"

    def test_int_04_agent_json_file_round_trip(self, tmp_path: Path):
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

    def test_int_05_agent_yaml_file_round_trip(self, tmp_path: Path):
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
