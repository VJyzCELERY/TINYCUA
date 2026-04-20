"""Tests for ToolRegistry."""

import pytest
from tinycua_sdk.core.registry import ToolRegistry, ToolEntry


class TestToolRegistry:
    """Tests for ToolRegistry singleton."""

    def setup_method(self):
        """Clear registry before each test."""
        self.registry = ToolRegistry()
        self.registry.clear()

    def test_registry_init(self):
        """ToolRegistry initializes."""
        registry = ToolRegistry()
        assert registry is not None

    def test_register_tool(self):
        """ToolRegistry can register a tool."""
        self.registry.register(
            name="test_tool",
            toolset="test",
            schema={"name": "test_tool", "description": "A test tool"},
        )

        entry = self.registry.get("test_tool")
        assert entry is not None
        assert entry.name == "test_tool"
        assert entry.toolset == "test"

    def test_register_duplicate_raises(self):
        """Registering duplicate tool raises ValueError."""
        self.registry.register(
            name="duplicate_tool",
            toolset="test",
            schema={},
        )

        with pytest.raises(ValueError) as exc_info:
            self.registry.register(
                name="duplicate_tool",
                toolset="test",
                schema={},
            )
        assert "already registered" in str(exc_info.value)

    def test_deregister_existing(self):
        """ToolRegistry can deregister an existing tool."""
        self.registry.register(name="removable", toolset="test", schema={})

        result = self.registry.deregister("removable")
        assert result is True
        assert self.registry.get("removable") is None

    def test_deregister_nonexistent(self):
        """ToolRegistry.deregister returns False for nonexistent tool."""
        result = self.registry.deregister("nonexistent")
        assert result is False

    def test_get_nonexistent(self):
        """ToolRegistry.get returns None for nonexistent tool."""
        result = self.registry.get("nonexistent")
        assert result is None

    def test_get_definitions_all(self):
        """ToolRegistry.get_definitions returns all schemas."""
        self.registry.register(name="tool1", schema={"name": "tool1"})
        self.registry.register(name="tool2", schema={"name": "tool2"})

        defs = self.registry.get_definitions()
        assert len(defs) == 2
        names = [d["name"] for d in defs]
        assert "tool1" in names
        assert "tool2" in names

    def test_get_definitions_filtered(self):
        """ToolRegistry.get_definitions filters by tool_names."""
        self.registry.register(name="tool1", schema={"name": "tool1"})
        self.registry.register(name="tool2", schema={"name": "tool2"})

        defs = self.registry.get_definitions(tool_names=["tool1"])
        assert len(defs) == 1
        assert defs[0]["name"] == "tool1"

    def test_dispatch_success(self):
        """ToolRegistry.dispatch calls handler with args."""
        def handler(x, y):
            return x + y

        self.registry.register(name="adder", handler=handler, schema={})

        result = self.registry.dispatch("adder", {"x": 2, "y": 3})
        assert result == 5

    def test_dispatch_missing_tool(self):
        """ToolRegistry.dispatch raises KeyError for missing tool."""
        with pytest.raises(KeyError) as exc_info:
            self.registry.dispatch("nonexistent", {})
        assert "not registered" in str(exc_info.value)

    def test_dispatch_no_handler(self):
        """ToolRegistry.dispatch raises RuntimeError if no handler."""
        self.registry.register(name="no_handler", handler=None, schema={})

        with pytest.raises(RuntimeError) as exc_info:
            self.registry.dispatch("no_handler", {})
        assert "no handler" in str(exc_info.value)

    def test_is_toolset_available_true(self):
        """ToolRegistry.is_toolset_available returns True when toolset has tools."""
        self.registry.register(name="tool1", toolset="available", schema={})

        result = self.registry.is_toolset_available("available")
        assert result is True

    def test_is_toolset_available_false(self):
        """ToolRegistry.is_toolset_available returns False when no tools in toolset."""
        self.registry.register(name="tool1", toolset="other", schema={})

        result = self.registry.is_toolset_available("nonexistent")
        assert result is False

    def test_clear_removes_all(self):
        """ToolRegistry.clear removes all registered tools."""
        self.registry.register(name="tool1", schema={})
        self.registry.register(name="tool2", schema={})

        self.registry.clear()

        assert self.registry.get_definitions() == []


class TestToolEntry:
    """Tests for ToolEntry class."""

    def test_tool_entry_init(self):
        """ToolEntry initializes with all attributes."""
        entry = ToolEntry(
            name="test_entry",
            toolset="test",
            schema={"name": "test"},
            handler=lambda: None,
            check_fn=lambda: True,
            tool=None,
        )

        assert entry.name == "test_entry"
        assert entry.toolset == "test"
        assert entry.schema == {"name": "test"}
        assert entry.handler is not None
        assert entry.check_fn is not None

    def test_tool_entry_slots(self):
        """ToolEntry uses __slots__ for memory efficiency."""
        entry = ToolEntry(
            name="slots_test",
            toolset=None,
            schema={},
            handler=None,
            check_fn=None,
            tool=None,
        )

        assert hasattr(entry, "__slots__")