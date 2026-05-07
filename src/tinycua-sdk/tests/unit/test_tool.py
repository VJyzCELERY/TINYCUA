"""Tests for @tool decorator and Tool dataclass."""

import pytest


class TestToolDecorator:
    """Tests for the @tool decorator."""

    def test_decorator_returns_tool_instance(self):
        """@tool converts a function into a Tool instance."""
        from tinycua_sdk import tool

        @tool
        def search(query: str) -> str:
            """Search for information."""
            return f"Results for {query}"

        assert search.name == "search"
        assert "Search for information" in search.description
        assert "query" in search.parameters["properties"]

    def test_decorator_with_dependencies(self):
        """@tool captures external dependencies."""
        from tinycua_sdk import tool

        @tool(dependencies=["requests"])
        def fetch_data(url: str) -> str:
            """Fetch data from URL."""
            return "data"

        assert "requests" in fetch_data.dependencies

    def test_decorator_without_parentheses(self):
        """@tool works without parentheses."""
        from tinycua_sdk import tool

        @tool
        def simple_func() -> str:
            """A simple function."""
            return "result"

        assert simple_func.name == "simple_func"


class TestToolSchema:
    """Tests for Tool schema generation."""

    def test_tool_schema_generation(self):
        """Tool parameters are inferred from type hints."""
        from tinycua_sdk import tool

        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        params = add.parameters
        assert params["type"] == "object"
        assert "a" in params["properties"]
        assert "b" in params["properties"]
        assert "a" in params["required"]
        assert "b" in params["required"]

    def test_tool_schema_with_defaults(self):
        """Optional parameters with defaults are not required."""
        from tinycua_sdk import tool

        @tool
        def greet(name: str, greeting: str = "Hello") -> str:
            """Greet someone."""
            return f"{greeting}, {name}!"

        params = greet.parameters
        assert "name" in params["required"]
        assert "greeting" not in params["required"]


class TestToolInvoke:
    """Tests for Tool.invoke()."""

    def test_tool_invoke(self):
        """Tool.invoke() calls the underlying function."""
        from tinycua_sdk import tool

        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        result = add.invoke(a=1, b=2)
        assert result == 3

    def test_tool_invoke_with_defaults(self):
        """Tool.invoke() works with default arguments."""
        from tinycua_sdk import tool

        @tool
        def greet(name: str, greeting: str = "Hello") -> str:
            """Greet someone."""
            return f"{greeting}, {name}!"

        result = greet.invoke(name="World")
        assert result == "Hello, World!"

    def test_tool_invoke_missing_required(self):
        """Tool.invoke() raises TypeError for missing required args."""
        from tinycua_sdk import tool

        @tool
        def require_arg(x: str) -> str:
            """Require an argument."""
            return x

        with pytest.raises(TypeError):
            require_arg.invoke()


class TestToolConfig:
    """Tests for Tool serialization."""

    def test_tool_to_config(self):
        """Tool.to_config() returns a serialization-friendly dict."""
        from tinycua_sdk import tool

        @tool
        def search(query: str) -> str:
            """Search for information."""
            return f"Results for {query}"

        config = search.to_config()
        assert config["function"]["name"] == "search"
        assert "parameters" in config["function"]

    def test_tool_from_dict(self):
        """Tool can be reconstructed from a dict."""
        from tinycua_sdk import Tool

        data = {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {"type": "object", "properties": {}},
        }

        tool = Tool.from_dict(data)
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"


class TestToolStatelessness:
    """Tests verifying Tool framework has no global state."""

    def test_no_global_registry(self):
        """@tool does not register into a global singleton."""
        from tinycua_sdk import tool

        @tool
        def my_tool():
            pass

        assert hasattr(my_tool, "name")
        assert hasattr(my_tool, "invoke")
        # No global registry should exist
        assert not hasattr(my_tool, "_registry")
