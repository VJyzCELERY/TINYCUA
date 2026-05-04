"""Integration tests for Tool and @tool decorator.

Converts targets: 05_tool_schema_generation, 06_tool_invoke,
07_manual_tool_construction
"""

import pytest

from tinycua_sdk import Tool, tool


class TestInt01ToolCreation:
    """Test suite for Tool and @tool decorator functionality."""

    def test_int_01_tool_schema_generation(self):
        """Target 1.5: Verify @tool generates correct OpenAI function schema."""

        @tool
        def get_weather(city: str, unit: str = "celsius") -> str:
            """Fetch weather for a city.

            Args:
                city: Name of the city (e.g., "Tokyo").
                unit: Temperature unit ("celsius" or "fahrenheit").
            """
            return f"sunny in {city}"

        schema = get_weather.to_config()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "get_weather"
        assert schema["function"]["description"] == "Fetch weather for a city."
        assert "city" in schema["function"]["parameters"]["properties"]
        assert "unit" in schema["function"]["parameters"]["properties"]
        assert schema["function"]["parameters"]["required"] == ["city"]

    def test_int_02_tool_invoke_keyword_args(self):
        """Target 1.6: Verify @tool-decorated function can be invoked with keyword args."""

        @tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        result = add.invoke(a=2, b=3)
        assert result == 5

    def test_int_03_tool_invoke_positional_args(self):
        """Target 1.6: Verify @tool-decorated function rejects positional args (kwargs-only per spec)."""

        @tool
        def multiply(x: int, y: int) -> int:
            """Multiply two numbers."""
            return x * y

        with pytest.raises(TypeError):
            multiply.invoke(10, 20)

    def test_int_04_manual_tool_construction(self):
        """Target 1.7: Verify manual Tool construction works."""
        dynamic = Tool(
            name="reverse_string",
            description="Reverse a string.",
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        )

        schema = dynamic.to_config()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "reverse_string"
        assert schema["function"]["description"] == "Reverse a string."

    def test_int_05_tool_invoke_no_callable_raises(self):
        """Verify invoke raises RuntimeError when _callable is None."""
        dynamic = Tool(
            name="no_callable_tool",
            description="A tool with no function.",
            parameters={"type": "object", "properties": {}, "required": []},
        )

        with pytest.raises(RuntimeError, match="has no function to invoke"):
            dynamic.invoke()

    def test_int_06_tool_decorator_no_args(self):
        """Verify @tool works without arguments."""

        @tool
        def simple_func() -> str:
            """A simple function."""
            return "hello"

        assert simple_func.name == "simple_func"
        assert simple_func.description == "A simple function."
        assert simple_func._callable is not None

    def test_int_07_tool_decorator_with_dependencies(self):
        """Verify @tool works with dependencies argument."""

        @tool(dependencies=["requests"])
        def fetch_data(url: str) -> str:
            """Fetch data from a URL."""
            return "data"

        assert fetch_data.dependencies == ["requests"]
        assert fetch_data._callable is not None

    def test_int_08_tool_from_callable_classmethod(self):
        """Verify Tool.from_callable creates Tool from function."""
        from tinycua_sdk import Tool

        def greet(name: str, greeting: str = "Hello") -> str:
            """Greet someone by name.

            Args:
                name: The person's name.
                greeting: The greeting word.
            """
            return f"{greeting}, {name}!"

        tool_instance = Tool.from_callable(greet)

        assert tool_instance.name == "greet"
        assert tool_instance.description == "Greet someone by name."
        assert "name" in tool_instance.parameters["properties"]
        assert "greeting" in tool_instance.parameters["properties"]
        assert tool_instance.parameters["required"] == ["name"]
        assert tool_instance._callable is not None

    def test_int_09_tool_dependencies_field(self):
        """Verify Tool has dependencies field."""
        t = Tool(
            name="dep_test",
            description="Test tool with dependencies.",
            dependencies=["numpy", "pandas"],
        )
        assert t.dependencies == ["numpy", "pandas"]
