"""Centralized singleton registry for all tools."""

from __future__ import annotations

import threading
from typing import Any, Callable, ClassVar


class ToolEntry:
    """Lightweight registry entry for a tool.

    Uses __slots__ for memory efficiency.

    Attributes:
        name: Unique tool name.
        toolset: Optional toolset group (e.g., "builtin", "custom").
        schema: Tool schema dict for API calls.
        handler: Callable to invoke when tool is dispatched.
        check_fn: Optional availability check function.
        tool: Original Tool object (if applicable).
    """

    __slots__ = ("name", "toolset", "schema", "handler", "check_fn", "tool")

    def __init__(
        self,
        name: str,
        toolset: str | None,
        schema: dict[str, Any],
        handler: Callable | None,
        check_fn: Callable | None,
        tool: Any,
    ) -> None:
        """Initialize a tool entry.

        Args:
            name: Unique tool name.
            toolset: Optional toolset group.
            schema: Tool schema dict for API calls.
            handler: Callable to invoke when tool is dispatched.
            check_fn: Optional availability check function.
            tool: Original Tool object (if applicable).
        """
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.tool = tool


class ToolRegistry:
    """Centralized singleton registry for all tools.

    Provides a single source of truth for tool registration, lookup,
    and dispatch. Uses a singleton pattern with thread-safe registration.
    """

    _instance: ClassVar["ToolRegistry | None"] = None
    _tools: dict[str, ToolEntry]
    _lock: threading.Lock

    def __new__(cls) -> "ToolRegistry":
        """Create or return the singleton instance.

        Returns:
            The singleton ToolRegistry instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def register(
        self,
        name: str,
        toolset: str | None = None,
        schema: dict[str, Any] | None = None,
        handler: Callable | None = None,
        check_fn: Callable | None = None,
        tool: Any | None = None,
    ) -> None:
        """Register a tool in the registry.

        Args:
            name: Unique tool name.
            toolset: Optional toolset group (e.g., "builtin", "custom").
            schema: Tool schema dict for API calls.
            handler: Callable to invoke when tool is dispatched.
            check_fn: Optional availability check function.
            tool: Original Tool object (if applicable).

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        with self._lock:
            if name in self._tools:
                raise ValueError(f"Tool '{name}' is already registered")
            self._tools[name] = ToolEntry(
                name=name,
                toolset=toolset,
                schema=schema or {},
                handler=handler,
                check_fn=check_fn,
                tool=tool,
            )

    def deregister(self, name: str) -> bool:
        """Remove a tool from the registry.

        Args:
            name: Tool name to remove.

        Returns:
            True if found and removed, False otherwise.
        """
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                return True
            return False

    def get(self, name: str) -> ToolEntry | None:
        """Get a tool entry by name.

        Args:
            name: Tool name to look up.

        Returns:
            ToolEntry if found, None otherwise.
        """
        return self._tools.get(name)

    def get_definitions(self, tool_names: list[str] | None = None) -> list[dict]:
        """Get tool definitions (schemas) for API calls.

        Args:
            tool_names: If provided, filter by these names.
                If None, return all registered tool schemas.

        Returns:
            List of schema dicts.
        """
        if tool_names is None:
            return [entry.schema for entry in self._tools.values()]
        return [self._tools[name].schema for name in tool_names if name in self._tools]

    def dispatch(self, name: str, args: dict[str, Any], **kwargs: Any) -> Any:
        """Dispatch a tool call by name.

        Args:
            name: Tool name to dispatch.
            args: Arguments to pass to the handler.
            **kwargs: Additional keyword arguments.

        Returns:
            Result from the tool handler (any type).

        Raises:
            KeyError: If the tool is not registered.
            RuntimeError: If the tool has no handler.
        """
        entry = self._tools.get(name)
        if entry is None:
            raise KeyError(f"Tool '{name}' is not registered")
        if entry.handler is None:
            raise RuntimeError(f"Tool '{name}' has no handler")
        return entry.handler(**args, **kwargs)

    def is_toolset_available(self, toolset: str) -> bool:
        """Check if any tools in the given toolset are registered.

        Args:
            toolset: Toolset name to check.

        Returns:
            True if any tool with the given toolset is registered.
        """
        return any(entry.toolset == toolset for entry in self._tools.values())

    def clear(self) -> None:
        """Clear all registered tools.

        Useful for testing to ensure isolation between tests.
        """
        with self._lock:
            self._tools.clear()
