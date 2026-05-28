"""Integration tests for Agent creation and initialization."""

from tinycua_sdk import Agent


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
                {
                    "name": "summarize",
                    "description": "Summarize tool",
                    "parameters": {},
                },
            ],
        }
        agent = Agent.from_config(config)
        assert len(agent.tools) == 2
