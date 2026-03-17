"""Tool registry for managing custom tools."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ToolRegistry:
    """In-memory registry for custom tools."""

    def __init__(self):
        """Initialize the registry."""
        self._tools: dict[str, dict[str, Any]] = {}
        self._materialized: dict[str, Callable] = {}

    def register(self, tool_bundle: dict[str, Any]) -> None:
        """Register a tool from bundle.

        Args:
            tool_bundle: Tool bundle containing name, source, etc.
        """
        name = tool_bundle.get("name", "")
        self._tools[name] = tool_bundle
        self._materialized.pop(name, None)
        logger.info(f"Registered tool: {name}")

    def get(self, name: str) -> dict[str, Any] | None:
        """Get a tool bundle by name.

        Args:
            name: Tool name

        Returns:
            Tool bundle or None
        """
        return self._tools.get(name)

    def get_materialized(self, name: str) -> Callable | None:
        """Get a materialized tool function.

        Args:
            name: Tool name

        Returns:
            Callable tool function or None
        """
        if name in self._materialized:
            return self._materialized[name]

        tool_bundle = self._tools.get(name)
        if tool_bundle is None:
            return None

        try:
            fn = materialize_tool(tool_bundle)
            self._materialized[name] = fn
            return fn
        except Exception as e:
            logger.error(f"Failed to materialize tool {name}: {e}")
            return None

    def list_all(self) -> list[dict[str, Any]]:
        """List all registered tools.

        Returns:
            List of tool bundles
        """
        return list(self._tools.values())

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._materialized.clear()


_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry.

    Returns:
        ToolRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def materialize_tool(tool_bundle: dict[str, Any]) -> Callable:
    """Materialize a tool from source code.

    Args:
        tool_bundle: Tool bundle with source code

    Returns:
        Callable tool function

    Raises:
        ValueError: If tool cannot be materialized
    """
    source = tool_bundle.get("source", "")
    name = tool_bundle.get("name", "")

    if not source:
        raise ValueError(f"Tool {name} has no source code")

    # Remove @tool decorator if present
    import re

    cleaned_source = re.sub(r"^@tool[^\n]*\n", "", source, count=1)

    namespace: dict[str, Any] = {}
    try:
        exec(cleaned_source, namespace)
    except SyntaxError as e:
        raise ValueError(f"Syntax error in tool {name}: {e}")

    if name not in namespace:
        raise ValueError(f"Tool {name} not found in source")

    return namespace[name]
