"""Tests for tool schema generation with complex types."""

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Union


from tinycua_sdk.tools.schema import type_to_json_schema
from tinycua_sdk.tools.decorators import tool


class TestTypeToJsonSchema:
    """Test type_to_json_schema for all supported types."""

    def test_str_type(self):
        """Test str maps to string type."""
        result = type_to_json_schema(str)
        assert result == {"type": "string"}

    def test_int_type(self):
        """Test int maps to number type."""
        result = type_to_json_schema(int)
        assert result == {"type": "number"}

    def test_float_type(self):
        """Test float maps to number type."""
        result = type_to_json_schema(float)
        assert result == {"type": "number"}

    def test_bool_type(self):
        """Test bool maps to boolean type."""
        result = type_to_json_schema(bool)
        assert result == {"type": "boolean"}

    def test_list_str_type(self):
        """Test list[str] maps to array of strings."""
        result = type_to_json_schema(list[str])
        assert result == {"type": "array", "items": {"type": "string"}}

    def test_list_int_type(self):
        """Test list[int] maps to array of numbers."""
        result = type_to_json_schema(list[int])
        assert result == {"type": "array", "items": {"type": "number"}}

    def test_typing_list_str_type(self):
        """Test typing.List[str] maps to array of strings."""
        result = type_to_json_schema(List[str])
        assert result == {"type": "array", "items": {"type": "string"}}

    def test_dict_type(self):
        """Test dict[str, Any] maps to object type."""
        result = type_to_json_schema(dict[str, Any])
        assert result == {"type": "object"}

    def test_typing_dict_type(self):
        """Test typing.Dict[str, Any] maps to object type."""
        result = type_to_json_schema(Dict[str, Any])
        assert result == {"type": "object"}

    def test_optional_str_type(self):
        """Test Optional[str] maps to string type (not required)."""
        result = type_to_json_schema(Optional[str])
        assert result == {"type": "string"}

    def test_union_str_int_type(self):
        """Test Union[str, int] maps to anyOf schema."""
        result = type_to_json_schema(Union[str, int])
        assert "anyOf" in result
        assert len(result["anyOf"]) == 2
        types = [s["type"] for s in result["anyOf"]]
        assert "string" in types
        assert "number" in types

    def test_enum_type(self):
        """Test Enum subclass maps to string enum schema."""

        class Priority(Enum):
            LOW = "low"
            HIGH = "high"

        result = type_to_json_schema(Priority)
        assert result == {"type": "string", "enum": ["low", "high"]}

    def test_annotated_str_type(self):
        """Test Annotated[str, 'desc'] includes description."""
        result = type_to_json_schema(Annotated[str, "A string parameter"])
        assert result == {"type": "string", "description": "A string parameter"}

    def test_annotated_int_type(self):
        """Test Annotated[int, 'desc'] includes description."""
        result = type_to_json_schema(Annotated[int, "An integer count"])
        assert result == {"type": "number", "description": "An integer count"}

    def test_annotated_list_type(self):
        """Test Annotated[list[str], 'desc'] includes description."""
        result = type_to_json_schema(Annotated[list[str], "List of tags"])
        assert result["type"] == "array"
        assert result["items"] == {"type": "string"}
        assert result["description"] == "List of tags"

    def test_unknown_type_defaults_to_string(self):
        """Test unknown types default to string."""
        result = type_to_json_schema(object)
        assert result == {"type": "string"}


class TestToolSchemaGeneration:
    """Test that @tool decorator generates correct schemas."""

    def test_tool_with_list_param(self):
        """Test @tool with list[str] param generates array schema."""

        @tool()
        def process_tags(tags: list[str]) -> dict:
            """Process a list of tags."""
            return {"count": len(tags)}

        props = process_tags.parameters["properties"]
        assert props["tags"]["type"] == "array"

    def test_tool_with_dict_param(self):
        """Test @tool with dict[str, Any] param generates object schema."""

        @tool()
        def store_metadata(metadata: dict[str, Any]) -> dict:
            """Store metadata."""
            return {"stored": True}

        props = store_metadata.parameters["properties"]
        assert props["metadata"]["type"] == "object"

    def test_tool_with_optional_param(self):
        """Test @tool with Optional[str] param generates schema for the inner type."""

        @tool()
        def search(query: str, filter: Optional[str] = None) -> dict:
            """Search with optional filter."""
            return {"results": []}

        props = search.parameters["properties"]
        assert "filter" in props
        assert props["filter"]["type"] == "string"
        assert "filter" not in search.parameters["required"]
        assert "query" in search.parameters["required"]

    def test_tool_with_union_param(self):
        """Test @tool with Union[str, int] param generates schema for the first non-None type."""

        @tool()
        def process_value(value: Union[str, int]) -> dict:
            """Process a value that can be string or int."""
            return {"value": value}

        props = process_value.parameters["properties"]
        assert "value" in props
        assert props["value"]["type"] == "string"

    def test_tool_with_enum_param(self):
        """Test @tool with Enum param generates enum schema."""

        class Priority(Enum):
            LOW = "low"
            HIGH = "high"

        @tool()
        def create_task(title: str, priority: Priority) -> dict:
            """Create a task with priority."""
            return {"title": title, "priority": priority.value}

        props = create_task.parameters["properties"]
        assert "priority" in props
        assert props["priority"]["type"] == "string"
        assert "low" in props["priority"]["enum"]

    def test_tool_with_annotated_param(self):
        """Test @tool with Annotated param includes description."""

        @tool()
        def create_task(
            title: str,
            description: Annotated[str, "Detailed task description"] = "",
        ) -> dict:
            """Create a task."""
            return {"title": title}

        props = create_task.parameters["properties"]
        assert "description" in props
        assert props["description"]["description"] == "Detailed task description"

    def test_tool_complex_types(self):
        """Test @tool with multiple complex types in one function."""

        class Priority(Enum):
            LOW = "low"
            HIGH = "high"

        @tool()
        def create_task(
            title: str,
            priority: Priority,
            tags: list[str] | None = None,
            metadata: dict[str, Any] | None = None,
            due_date: Optional[str] = None,
            description: Annotated[str, "Detailed task description"] = "",
        ) -> dict:
            """Create a new task."""
            return {"title": title}

        props = create_task.parameters["properties"]
        required = create_task.parameters["required"]

        # Required fields
        assert "title" in required
        assert "priority" in required

        # Optional fields
        assert "tags" not in required
        assert "metadata" not in required
        assert "due_date" not in required
        assert "description" not in required

        # Type checks
        assert props["title"]["type"] == "string"
