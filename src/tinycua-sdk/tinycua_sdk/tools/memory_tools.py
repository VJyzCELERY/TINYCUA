"""Memory tools for agents."""

import os

from tinycua_sdk.tools.decorators import tool
from tinycua_sdk.tools.memory import (
    MemoryBackend,
    get_memory_backend,
)


_memory_backend: MemoryBackend | None = None


def _get_memory_backend() -> MemoryBackend:
    """Get or create the memory backend instance."""
    global _memory_backend
    if _memory_backend is None:
        backend_url = os.environ.get("TINYCUA_BACKEND_URL")
        api_key = os.environ.get("TINYCUA_API_KEY")
        local_only = (
            os.environ.get("TINYCUA_MEMORY_LOCAL_ONLY", "false").lower() == "true"
        )
        _memory_backend = get_memory_backend(backend_url, api_key, local_only)
    return _memory_backend


def set_memory_backend(backend: MemoryBackend) -> None:
    """Set a custom memory backend (useful for testing)."""
    global _memory_backend
    _memory_backend = backend


def reset_memory_backend() -> None:
    """Reset memory backend to default."""
    global _memory_backend
    _memory_backend = None


@tool()
def remember(key: str, value: str) -> dict:
    """Store a value in memory.

    Args:
        key: The key to store the value under
        value: The value to store

    Returns:
        Result dict with success status

    """
    backend = _get_memory_backend()
    return backend.set(key, value)


@tool()
def recall(key: str) -> dict:
    """Retrieve a value from memory.

    Args:
        key: The key to retrieve

    Returns:
        Result dict with value and found status

    """
    backend = _get_memory_backend()
    value, found = backend.get(key)
    if found:
        return {"key": key, "value": value, "found": True}
    return {"key": key, "value": None, "found": False}


@tool()
def forget(key: str) -> dict:
    """Delete a value from memory.

    Args:
        key: The key to delete

    Returns:
        Result dict with success status

    """
    backend = _get_memory_backend()
    return backend.delete(key)


@tool()
def list_memory() -> dict:
    """List all keys in memory.

    Returns:
        Result dict with list of keys

    """
    backend = _get_memory_backend()
    return {"keys": backend.list_keys()}


@tool()
def clear_memory() -> dict:
    """Clear all memory.

    Returns:
        Result dict with success status

    """
    backend = _get_memory_backend()
    return backend.clear()


__all__ = [
    "remember",
    "recall",
    "forget",
    "list_memory",
    "clear_memory",
    "set_memory_backend",
    "reset_memory_backend",
    "get_memory_backend",
]
