"""Tests for AgentDefinition class."""

import pytest

from tinycua_sdk.agent.config import AgentPolicy
from tinycua_sdk.agent.definition import AgentDefinition
from tinycua_sdk.agent.llm_model import LanguageModel
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
            llm_model=LanguageModel(model_name="gpt-4o-mini"),
        )

    def test_agent_definition_config_serialization(self):
        """Test AgentDefinition config serialization."""
        from tinycua_sdk.tools.decorators import Tool, tool

        @tool
        def greet(name: str) -> str:
            """Greet someone by name.

            Args:
                name: The person's name.
            """
            return f"Hello, {name}!"

        definition = AgentDefinition(
            name="test-agent",
            instructions="You are a helpful assistant.",
            llm_model=LanguageModel(model_name="gpt-4o-mini", provider="openai"),
            tools=[greet],
        )

        result = str(definition)

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
