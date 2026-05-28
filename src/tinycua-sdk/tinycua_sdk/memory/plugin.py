"""Memory plugin system with file, in-memory, and SQLite backends."""

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class MemoryPlugin(ABC):
    """Abstract base class for memory storage plugins."""

    @abstractmethod
    def read(self, key: str) -> str | None:
        """Read a value by key.

        Args:
            key: Key to read

        Returns:
            Value or None if not found

        """
        pass

    @abstractmethod
    def write(self, key: str, value: str) -> dict[str, Any]:
        """Write a key-value pair.

        Args:
            key: Key to write
            value: Value to store

        Returns:
            Result dictionary

        """
        pass

    @abstractmethod
    def delete(self, key: str) -> dict[str, Any]:
        """Delete a key.

        Args:
            key: Key to delete

        Returns:
            Result dictionary

        """
        pass

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List all keys.

        Returns:
            List of all keys

        """
        pass

    def clear(self) -> dict[str, Any]:
        """Clear all memory (optional override)."""
        keys = self.list_keys()
        for key in keys:
            self.delete(key)
        return {"success": True}


class FileMemoryPlugin(MemoryPlugin):
    """File-based memory storage plugin."""

    def __init__(self, storage_path: str | None = None):
        """Initialize file memory plugin.

        Args:
            storage_path: Custom storage path. Defaults to ~/.tinycua/plugin_memory.json

        """
        self._storage_path = Path(storage_path or self._default_storage_path())
        self._lock = threading.RLock()
        self._ensure_storage()

    def _default_storage_path(self) -> str:
        """Get default storage path."""
        home = Path.home()
        return str(home / ".tinycua" / "plugin_memory.json")

    def _ensure_storage(self) -> None:
        """Ensure storage file exists."""
        with self._lock:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self._storage_path.exists():
                self._storage_path.write_text("{}", encoding="utf-8")

    def _read_data(self) -> dict[str, Any]:
        """Read data from file."""
        with self._lock:
            return json.loads(self._storage_path.read_text(encoding="utf-8"))

    def _write_data(self, data: dict[str, Any]) -> None:
        """Write data to file."""
        with self._lock:
            self._storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def read(self, key: str) -> str | None:
        """Read a value by key."""
        data = self._read_data()
        return data.get(key)

    def write(self, key: str, value: str) -> dict[str, Any]:
        """Write a key-value pair."""
        data = self._read_data()
        data[key] = value
        self._write_data(data)
        return {"success": True, "key": key}

    def delete(self, key: str) -> dict[str, Any]:
        """Delete a key."""
        data = self._read_data()
        if key in data:
            del data[key]
            self._write_data(data)
            return {"success": True, "key": key}
        return {"success": False, "key": key, "error": "Key not found"}

    def list_keys(self) -> list[str]:
        """List all keys."""
        data = self._read_data()
        return list(data.keys())

    def clear(self) -> dict[str, Any]:
        """Clear all memory."""
        self._write_data({})
        return {"success": True}


class InMemoryPlugin(MemoryPlugin):
    """In-memory storage plugin."""

    def __init__(self):
        """Initialize in-memory plugin."""
        self._data: dict[str, str] = {}
        self._lock = threading.RLock()

    def read(self, key: str) -> str | None:
        """Read a value by key."""
        with self._lock:
            return self._data.get(key)

    def write(self, key: str, value: str) -> dict[str, Any]:
        """Write a key-value pair."""
        with self._lock:
            self._data[key] = value
            return {"success": True, "key": key}

    def delete(self, key: str) -> dict[str, Any]:
        """Delete a key."""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return {"success": True, "key": key}
            return {"success": False, "key": key, "error": "Key not found"}

    def list_keys(self) -> list[str]:
        """List all keys."""
        with self._lock:
            return list(self._data.keys())

    def clear(self) -> dict[str, Any]:
        """Clear all memory."""
        with self._lock:
            self._data.clear()
            return {"success": True}


class SQLiteMemoryPlugin(MemoryPlugin):
    """SQLite-based memory storage plugin."""

    def __init__(self, db_path: str | None = None):
        """Initialize SQLite memory plugin.

        Args:
            db_path: Custom database path. Defaults to ~/.tinycua/memory.db

        """
        self._db_path = db_path or self._default_db_path()
        self._lock = threading.RLock()
        self._ensure_storage()

    def _default_db_path(self) -> str:
        """Get default database path."""
        home = Path.home()
        return str(home / ".tinycua" / "memory.db")

    def _ensure_storage(self) -> None:
        """Ensure database exists."""
        with self._lock:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.commit()
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self._db_path)

    def read(self, key: str) -> str | None:
        """Read a value by key."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT value FROM memory WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None

    def write(self, key: str, value: str) -> dict[str, Any]:
        """Write a key-value pair."""
        with self._lock:
            conn = self._get_connection()
            conn.execute(
                "INSERT OR REPLACE INTO memory (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()
            conn.close()
            return {"success": True, "key": key}

    def delete(self, key: str) -> dict[str, Any]:
        """Delete a key."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("DELETE FROM memory WHERE key = ?", (key,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            if deleted:
                return {"success": True, "key": key}
            return {"success": False, "key": key, "error": "Key not found"}

    def list_keys(self) -> list[str]:
        """List all keys."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute("SELECT key FROM memory")
            keys = [row[0] for row in cursor.fetchall()]
            conn.close()
            return keys

    def clear(self) -> dict[str, Any]:
        """Clear all memory."""
        with self._lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM memory")
            conn.commit()
            conn.close()
            return {"success": True}


def get_memory_plugin(
    plugin_type: str = "memory",
    **kwargs: Any,
) -> MemoryPlugin:
    """Get a memory plugin by type.

    Args:
        plugin_type: Type of plugin ('file', 'memory', 'sqlite')
        **kwargs: Plugin-specific arguments

    Returns:
        MemoryPlugin instance

    """
    plugins = {
        "file": FileMemoryPlugin,
        "memory": InMemoryPlugin,
        "sqlite": SQLiteMemoryPlugin,
    }

    plugin_class = plugins.get(plugin_type, InMemoryPlugin)
    return plugin_class(**kwargs)


__all__ = [
    "MemoryPlugin",
    "FileMemoryPlugin",
    "InMemoryPlugin",
    "SQLiteMemoryPlugin",
    "get_memory_plugin",
]
