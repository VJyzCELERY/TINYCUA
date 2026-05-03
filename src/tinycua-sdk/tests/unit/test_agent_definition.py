"""Tests for AgentDefinition class."""

import pytest

from tinycua_sdk.agent.config import AgentPolicy
from tinycua_sdk.agent.definition import AgentDefinition
from tinycua_sdk.agent.llm_model import LLMModel
from tinycua_sdk.tools.decorators import tool


class TestAgentDefinition:
    """Test AgentDefinition properties, config, and serialization."""

    def test_agent_definition_is_not_abstract(self):
        """Test AgentDefinition can be instantiated directly."""
        agent = AgentDefinition(name="test")
        assert agent.name == "test"

    def test_agent_definition_initialization(self):
        """Test AgentDefinition initializes with defaults."""
        agent = AgentDefinition(
            name="test",
            instructions="You are a test agent.",
            llm_model=LLMModel(model_name="gpt-4o-mini"),
        )
        assert agent.name == "test"
        assert agent.instructions == "You are a test agent."
        assert agent.model == "gpt-4o-mini"
        assert isinstance(agent.policy, AgentPolicy)

    def test_agent_definition_with_tools(self):
        """Test AgentDefinition accepts tools."""

        @tool()
        def my_tool() -> None:
            """A tool."""
            pass

        agent = AgentDefinition(name="test", instructions="...", tools=[my_tool])
        assert len(agent.tools) == 1
        assert agent.tools[0].name == "my_tool"

    def test_agent_definition_to_config(self):
        """Test AgentDefinition serializes to config dict."""
        agent = AgentDefinition(name="my-agent", instructions="Be helpful.")
        config = agent.to_config()

        assert config["name"] == "my-agent"
        assert config["instructions"] == "Be helpful."
        assert "policy" in config

    def test_agent_definition_from_config(self):
        """Test AgentDefinition can be created from config dict."""
        config = {
            "name": "test",
            "instructions": "Test instructions",
            "llm_model": {
                "model_name": "test-model",
                "provider": "openai",
            },
        }

        agent = AgentDefinition.from_config(config)

        assert agent.name == "test"
        assert agent.instructions == "Test instructions"
        assert agent.model == "test-model"

    def test_str_representation(self):
        """Test __str__ returns formatted agent details."""
        agent = AgentDefinition(
            name="test-agent",
            llm_model=LLMModel(model_name="gpt-4o-mini", provider="openai"),
        )

        result = str(agent)

        assert "test-agent" in result
        assert "gpt-4o-mini" in result
        assert "openai" in result

    def test_add_tool(self):
        """Test adding a single tool."""

        @tool()
        def my_tool() -> None:
            """A tool."""
            pass

        agent = AgentDefinition(name="test")
        agent.add_tool(my_tool)

        assert len(agent.tools) == 1

    def test_add_tools(self):
        """Test adding multiple tools."""

        @tool()
        def tool_a() -> None:
            """Tool A."""
            pass

        @tool()
        def tool_b() -> None:
            """Tool B."""
            pass

        agent = AgentDefinition(name="test")
        agent.add_tools([tool_a, tool_b])

        assert len(agent.tools) == 2
