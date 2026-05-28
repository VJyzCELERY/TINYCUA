"""Tests for ToolRegistry singleton."""

import pytest

from tinycua_sdk.core.registry import ToolEntry, ToolRegistry


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the registry before and after each test."""
    registry = ToolRegistry()
    registry.clear()
    yield
    registry.clear()


class TestToolEntry:
    """Tests for ToolEntry data class."""

    def test_tool_entry_uses_slots(self):
        """Verify ToolEntry uses __slots__ for memory efficiency."""
        entry = ToolEntry(
            name="test_tool",
            toolset="test",
            schema={"type": "function"},
            handler=lambda: None,
            check_fn=None,
            tool=None,
        )
        assert not hasattr(entry, "__dict__")


class TestToolRegistrySingleton:
    """Tests for ToolRegistry singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Verify singleton pattern."""
        r1 = ToolRegistry()
        r2 = ToolRegistry()
        assert r1 is r2


class TestToolRegistryRegistration:
    """Tests for tool registration and retrieval."""

    def test_register_and_get_tool(self):
        """Register a tool, retrieve it."""
        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            toolset="test",
            schema={"type": "function", "name": "test_tool"},
            handler=lambda x: x * 2,
            check_fn=None,
            tool=None,
        )
        entry = registry.get("test_tool")
        assert entry is not None
        assert entry.name == "test_tool"
        assert entry.toolset == "test"

    def test_deregister_tool(self):
        """Register then deregister, verify removal."""
        registry = ToolRegistry()
        registry.register(
            name="temp_tool",
            toolset="test",
            schema={"type": "function"},
            handler=lambda: None,
            check_fn=None,
            tool=None,
        )
        result = registry.deregister("temp_tool")
        assert result is True
        assert registry.get("temp_tool") is None

    def test_register_duplicate_raises_value_error(self):
        """Register same name twice, assert ValueError."""
        registry = ToolRegistry()
        registry.register(
            name="dup_tool",
            schema={"type": "function"},
            handler=lambda: None,
        )
        with pytest.raises(ValueError):
            registry.register(
                name="dup_tool",
                schema={"type": "function"},
                handler=lambda: None,
            )


class TestToolRegistryDefinitions:
    """Tests for get_definitions method."""

    def test_get_definitions_returns_all_when_no_filter(self):
        """Verify all schemas returned."""
        registry = ToolRegistry()
        registry.register(
            name="tool_a",
            schema={"type": "function", "name": "tool_a"},
            handler=lambda: None,
        )
        registry.register(
            name="tool_b",
            schema={"type": "function", "name": "tool_b"},
            handler=lambda: None,
        )
        definitions = registry.get_definitions()
        assert len(definitions) == 2
        names = [d["name"] for d in definitions]
        assert "tool_a" in names
        assert "tool_b" in names

    def test_get_definitions_filters_by_name(self):
        """Verify filtering works."""
        registry = ToolRegistry()
        registry.register(
            name="tool_a",
            schema={"type": "function", "name": "tool_a"},
            handler=lambda: None,
        )
        registry.register(
            name="tool_b",
            schema={"type": "function", "name": "tool_b"},
            handler=lambda: None,
        )
        definitions = registry.get_definitions(tool_names=["tool_a"])
        assert len(definitions) == 1
        assert definitions[0]["name"] == "tool_a"


class TestToolRegistryDispatch:
    """Tests for dispatch method."""

    def test_dispatch_calls_tool_handler(self):
        """Verify dispatch invokes handler."""
        registry = ToolRegistry()
        registry.register(
            name="add_tool",
            schema={"type": "function"},
            handler=lambda x, y: x + y,
        )
        result = registry.dispatch("add_tool", {"x": 1, "y": 2})
        assert result == 3

    def test_dispatch_raises_for_unknown_tool(self):
        """Verify error on unknown tool."""
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.dispatch("nonexistent", {})

    def test_dispatch_raises_runtime_error_when_no_handler(self):
        """Register tool with handler=None, dispatch, assert RuntimeError."""
        registry = ToolRegistry()
        registry.register(
            name="no_handler_tool",
            schema={"type": "function"},
            handler=None,
        )
        with pytest.raises(RuntimeError):
            registry.dispatch("no_handler_tool", {})


class TestToolRegistryToolset:
    """Tests for toolset availability checking."""

    def test_is_toolset_available_returns_true(self):
        """Register tool with toolset, check availability."""
        registry = ToolRegistry()
        registry.register(
            name="my_tool",
            toolset="my_toolset",
            schema={"type": "function"},
            handler=lambda: None,
        )
        assert registry.is_toolset_available("my_toolset") is True

    def test_is_toolset_available_returns_false(self):
        """Check unregistered toolset."""
        registry = ToolRegistry()
        assert registry.is_toolset_available("nonexistent_toolset") is False


class TestToolRegistryClear:
    """Tests for clear method."""

    def test_clear_removes_all_tools(self):
        """Verify clear works."""
        registry = ToolRegistry()
        registry.register(
            name="tool_1",
            schema={"type": "function"},
            handler=lambda: None,
        )
        registry.register(
            name="tool_2",
            schema={"type": "function"},
            handler=lambda: None,
        )
        registry.clear()
        assert registry.get("tool_1") is None
        assert registry.get("tool_2") is None
        assert registry.get_definitions() == []
