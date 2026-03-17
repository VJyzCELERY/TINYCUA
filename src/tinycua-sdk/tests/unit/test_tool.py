"""Tests for tool decorator."""

import pytest


class TestToolDecorator:
    def test_tool_decorator_creates_tool(self):
        from tinycua_sdk.tools import tool

        @tool()
        def get_weather(location: str) -> dict:
            """Return current weather for a location."""
            return {"weather": "sunny"}

        assert get_weather.name == "get_weather"
        assert get_weather.description == "Return current weather for a location."
        assert "location" in get_weather.parameters["properties"]

    def test_tool_to_config(self):
        from tinycua_sdk.tools import tool

        @tool()
        def test_func(x: int) -> int:
            """Test function."""
            return x

        config = test_func.to_config()
        assert config["name"] == "test_func"
        assert "parameters" in config

    def test_tool_with_dependencies(self):
        from tinycua_sdk.tools import tool

        @tool(dependencies=["requests"])
        def fetch_data(url: str) -> str:
            """Fetch data from URL."""
            return "data"

        assert "requests" in fetch_data._external_dependencies

    def test_tool_invokes_function(self):
        from tinycua_sdk.tools import tool

        @tool()
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        result = add.invoke(a=1, b=2)
        assert result == 3

    def test_tool_without_parentheses(self):
        from tinycua_sdk.tools import tool

        @tool
        def simple_func() -> str:
            """A simple function."""
            return "result"

        assert simple_func.name == "simple_func"


class TestToolModel:
    def test_tool_from_config(self):
        from tinycua_sdk.tools import Tool

        config = {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {"type": "object", "properties": {}},
        }

        tool = Tool.from_config(config)
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"

    def test_tool_to_bundle(self):
        from tinycua_sdk.tools import tool

        @tool()
        def my_tool() -> None:
            """My tool."""
            pass

        bundle = my_tool.to_bundle()
        assert "source" in bundle
        assert "external_dependencies" in bundle
        assert "tool_dependencies" in bundle
        assert "version" in bundle
