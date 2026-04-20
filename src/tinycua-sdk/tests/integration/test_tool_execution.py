"""Integration tests for Tool execution."""

import pytest
from unittest.mock import MagicMock
from tinycua_sdk.tools import tool
from tinycua_sdk.tools.decorators import Tool


class TestToolExecution:
    """Integration tests for tool execution."""

    def test_basic_tool_invocation(self):
        """Test basic tool invocation."""
        @tool
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        result = greet.invoke(name="World")
        assert result == "Hello, World!"

    def test_tool_with_multiple_params(self):
        """Test tool with multiple parameters."""
        @tool
        def add(a: int, b: int, c: int = 0) -> int:
            """Add numbers."""
            return a + b + c

        result = add.invoke(a=1, b=2, c=3)
        assert result == 6

    def test_tool_with_optional_params(self):
        """Test tool with optional parameters."""
        @tool
        def configure(option: str, value: str = "default") -> str:
            """Configure something."""
            return f"{option}={value}"

        result = configure.invoke(option="debug")
        assert result == "debug=default"

    def test_tool_with_kwargs(self):
        """Test tool passing kwargs to handler."""
        @tool
        def process(**kwargs) -> dict:
            """Process kwargs."""
            return kwargs

        result = process.invoke(foo="bar", baz=123)
        assert result == {"foo": "bar", "baz": 123}


class TestToolSchema:
    """Integration tests for tool schema generation."""

    def test_tool_generates_schema(self):
        """Test tool generates correct schema."""
        @tool
        def calculate(x: int, y: int, operation: str = "add") -> int:
            """Calculate result."""
            if operation == "add":
                return x + y
            return x - y

        schema = calculate.schema
        assert "name" in schema
        assert schema["name"] == "calculate"
        assert "parameters" in schema

    def test_tool_schema_includes_descriptions(self):
        """Test tool schema includes parameter descriptions."""
        @tool
        def search(query: str, limit: int = 10) -> list:
            """Search for items."""
            return []

        schema = search.schema
        params = schema["parameters"]["properties"]
        assert "query" in params
        assert "description" in params["query"]


class TestToolErrorHandling:
    """Integration tests for tool error handling."""

    def test_tool_missing_required_param(self):
        """Test tool raises error for missing required param."""
        @tool
        def required_param(name: str) -> str:
            """Required param tool."""
            return name

        with pytest.raises(TypeError):
            required_param.invoke()

    def test_tool_invalid_param_type(self):
        """Test tool handles invalid param type."""
        @tool
        def numeric(value: int) -> int:
            """Numeric tool."""
            return value

        result = numeric.invoke(value="42")
        assert result == 42


class TestToolWithAgent:
    """Integration tests for tools used with agents."""

    def test_multiple_tools_in_agent(self):
        """Test agent with multiple tools."""
        @tool
        def tool1() -> str:
            return "tool1"

        @tool
        def tool2() -> str:
            return "tool2"

        @tool
        def tool3() -> str:
            return "tool3"

        from tinycua_sdk.agent.agent import Agent

        agent = Agent(
            name="multi-tool-agent",
            model="test",
            provider="test",
            tools=[tool1, tool2, tool3],
        )

        assert len(agent.tools) == 3
        names = [t.name for t in agent.tools]
        assert "tool1" in names
        assert "tool2" in names
        assert "tool3" in names

    def test_tool_dispatch_by_name(self):
        """Test dispatching tool by name from agent."""
        @tool
        def echo(message: str) -> str:
            """Echo message."""
            return message

        from tinycua_sdk.agent.agent import Agent

        agent = Agent(
            name="dispatch-agent",
            model="test",
            provider="test",
            tools=[echo],
        )

        tool_instance = None
        for t in agent.tools:
            if t.name == "echo":
                tool_instance = t
                break

        assert tool_instance is not None
        result = tool_instance.invoke(message="test")
        assert result == "test"