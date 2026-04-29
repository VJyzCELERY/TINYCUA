"""Integration tests for Agent creation and initialization."""

import pytest
from tinycua_sdk import Agent, LLMModel


class TestAgentCreation:
    """Integration tests for agent creation."""

    def test_from_dict_minimal(self):
        """Create agent from minimal dict config."""
        config = {
            "name": "test",
            "instructions": "Test agent",
            "llm_model": {
                "model_name": "gpt-4",
                "provider": "openai",
            },
        }
        agent = Agent.from_config(config)
        assert agent.name == "test"
        assert agent.instructions == "Test agent"
        assert agent.llm_model.model_name == "gpt-4"

    def test_from_dict_with_tools(self):
        """Create agent with tools from config."""
        config = {
            "name": "test",
            "llm_model": {},
            "tools": [
                {"name": "search", "description": "Search tool", "parameters": {}},
                {"name": "summarize", "description": "Summarize tool", "parameters": {}},
            ],
        }
        agent = Agent.from_config(config)
        assert len(agent.tools) == 2

    def test_from_json_file(self, tmp_path):
        """Load agent from JSON file."""
        config_file = tmp_path / "agent.json"
        config_file.write_text('{"name": "json_agent", "instructions": "From JSON"}')
        agent = Agent.from_config(config_file)
        assert agent.name == "json_agent"

    def test_from_yaml_file(self, tmp_path):
        """Load agent from YAML file."""
        config_file = tmp_path / "agent.yaml"
        config_file.write_text("name: yaml_agent\ninstructions: From YAML\n")
        agent = Agent.from_config(config_file)
        assert agent.name == "yaml_agent"

    def test_config_round_trip_file(self, tmp_path):
        """Serialize to file and restore."""
        original = Agent(
            name="roundtrip",
            llm_model=LLMModel(model_name="gpt-4"),
        )
        config_path = tmp_path / "agent.json"
        original.config.to_json_file(config_path)
        restored = Agent.from_config(config_path)
        assert restored.name == "roundtrip"
        assert restored.llm_model.model_name == "gpt-4"

    def test_coder_template(self):
        """Load built-in coder template."""
        agent = Agent.from_template("coder")
        assert agent.name == "coder"

    def test_researcher_template(self):
        """Load built-in researcher template."""
        agent = Agent.from_template("researcher")
        assert agent.name == "researcher"

    def test_assistant_template(self):
        """Load built-in assistant template."""
        agent = Agent.from_template("assistant")
        assert agent.name == "assistant"

    def test_template_with_llm_override(self):
        """Override LLMModel after template load."""
        agent = Agent.from_template("coder")
        agent.llm_model = LLMModel(model_name="custom-model")
        assert agent.llm_model.model_name == "custom-model"

    def test_invalid_template(self):
        """Unknown template raises ValueError."""
        with pytest.raises(ValueError):
            Agent.from_template("nonexistent_template")
