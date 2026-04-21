"""Tool manager for TinyCUA TUI."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from tinycua_sdk.core.registry import ToolRegistry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """Tool information for display.

    Attributes:
        name: Tool name.
        description: Tool description.
        toolset: Toolset the tool belongs to.
    """

    name: str
    description: str
    toolset: str | None = None


class ToolManager:
    """Tool manager for TUI.

    Provides tool listing and execution capabilities using
    the SDK's ToolRegistry.
    """

    def __init__(self) -> None:
        """Initialize the tool manager."""
        self._registry = ToolRegistry()
        self._loaded_tools: dict[str, ToolInfo] = {}

    def list_tools(self) -> list[ToolInfo]:
        """List all available tools.

        Returns:
            List of ToolInfo instances.
        """
        self._loaded_tools.clear()
        tools = []

        for tool_name, entry in self._registry._tools.items():
            # WORKAROUND: ToolRegistry does not expose a public method to list all tools.
            # Accessing _tools directly is a temporary solution until a public API is added.
            tool_info = ToolInfo(
                name=tool_name,
                description=entry.description or "No description",
                toolset=entry.toolset,
            )
            self._loaded_tools[tool_name] = tool_info
            tools.append(tool_info)

        return tools

    def get_tool(self, name: str) -> ToolInfo | None:
        """Get tool information by name.

        Args:
            name: Tool name.

        Returns:
            ToolInfo or None if not found.
        """
        if name in self._loaded_tools:
            return self._loaded_tools[name]

        entry = self._registry._tools.get(name)
        if entry is None:
            return None

        tool_info = ToolInfo(
            name=name,
            description=entry.description or "No description",
            toolset=entry.toolset,
        )
        return tool_info

    async def execute_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> str:
        """Execute a tool with given arguments.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.

        Returns:
            Tool execution result or error message.
        """
        try:
            entry = self._registry._tools.get(tool_name)
            if entry is None:
                return f"Tool '{tool_name}' not found"

            handler = entry.handler
            if handler is None:
                return f"Tool '{tool_name}' has no handler"

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: handler(arguments)
            )
            return str(result)
        except Exception:
            logger.exception(f"Failed to execute tool {tool_name}")
            return f"Error executing tool '{tool_name}'"

    def get_tools_by_toolset(self, toolset: str) -> list[ToolInfo]:
        """Get tools belonging to a specific toolset.

        Args:
            toolset: Toolset name.

        Returns:
            List of ToolInfo instances.
        """
        return [
            tool
            for tool in self.list_tools()
            if tool.toolset == toolset
        ]

    def get_toolsets(self) -> list[str]:
        """Get list of available toolsets.

        Returns:
            List of toolset names.
        """
        toolsets = set()
        for entry in self._registry._tools.values():
            if entry.toolset is not None:
                toolsets.add(entry.toolset)
        return sorted(toolsets)
