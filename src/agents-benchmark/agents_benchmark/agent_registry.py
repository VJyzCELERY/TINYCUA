"""Central registry for agent adapter lookup by name."""

from __future__ import annotations

from typing import Any


class AgentRegistry:
    """Registry for agent adapter classes.

    Agents are registered by name and can be retrieved by name.
    Supports register, get, and list_all operations.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._adapters: dict[str, Any] = {}

    def register(self, name: str, adapter_class: Any) -> None:
        """Register an adapter class under the given name.

        Args:
            name: Agent identifier (e.g., "hermes").
            adapter_class: Class implementing the BaseAgent interface.
        """
        self._adapters[name] = adapter_class

    def get(self, name: str) -> Any:
        """Get an adapter class by name.

        Args:
            name: Agent identifier.

        Returns:
            The registered adapter class.

        Raises:
            KeyError: If no adapter is registered under the given name.
        """
        if name not in self._adapters:
            raise KeyError(f"No adapter registered for '{name}'")
        return self._adapters[name]

    def list_all(self) -> list[str]:
        """List all registered adapter names.

        Returns:
            List of registered agent names.
        """
        return list(self._adapters.keys())
