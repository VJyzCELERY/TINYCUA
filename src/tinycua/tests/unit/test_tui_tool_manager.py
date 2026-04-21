"""Unit tests for TUI ToolManager."""

import pytest
from unittest.mock import MagicMock, patch


class TestToolManager:
    """Tests for ToolManager."""

    def test_tool_manager_initializes(self):
        """Test tool manager initializes correctly."""
        from tinycua.tui.tool_manager import ToolManager

        manager = ToolManager()
        assert manager is not None

    def test_list_tools(self):
        """Test listing tools."""
        from tinycua.tui.tool_manager import ToolManager

        manager = ToolManager()
        tools = manager.list_tools()

        assert isinstance(tools, list)

    def test_get_toolsets(self):
        """Test getting toolsets."""
        from tinycua.tui.tool_manager import ToolManager

        manager = ToolManager()
        toolsets = manager.get_toolsets()

        assert isinstance(toolsets, list)


class TestToolInfo:
    """Tests for ToolInfo dataclass."""

    def test_tool_info_creation(self):
        """Test ToolInfo creation."""
        from tinycua.tui.tool_manager import ToolInfo

        info = ToolInfo(
            name="test_tool",
            description="A test tool",
            toolset="test_toolset",
        )

        assert info.name == "test_tool"
        assert info.description == "A test tool"
        assert info.toolset == "test_toolset"