"""Long-term memory management using file-based storage."""

from pathlib import Path
from threading import RLock
from typing import Any


class LongTermMemory:
    """Manages persistent long-term memory using file-based storage."""

    def __init__(self, storage_path: str | None = None):
        """Initialize long-term memory.

        Args:
            storage_path: Custom storage path. Defaults to ~/.tinycua/

        """
        self._storage_path = Path(storage_path) if storage_path else self._default_storage_path()
        self._lock = RLock()
        self._ensure_storage()

    def _default_storage_path(self) -> Path:
        """Get default storage path."""
        return Path.home() / ".tinycua"

    def _ensure_storage(self) -> None:
        """Ensure storage directory exists."""
        with self._lock:
            self._storage_path.mkdir(parents=True, exist_ok=True)

    def _file_path(self, name: str) -> Path:
        """Get file path for a memory file.

        Args:
            name: Memory file name (e.g., 'MEMORY.md', 'USER.md')

        Returns:
            Path to the memory file

        """
        return self._storage_path / name

    def read(self, name: str = "MEMORY.md") -> str:
        """Read content from a memory file.

        Args:
            name: Memory file name (default: 'MEMORY.md')

        Returns:
            File content or empty string if file doesn't exist

        """
        with self._lock:
            file_path = self._file_path(name)
            if not file_path.exists():
                return ""
            return file_path.read_text(encoding="utf-8")

    def write(self, content: str, name: str = "MEMORY.md") -> dict[str, Any]:
        """Write content to a memory file.

        Args:
            content: Content to write
            name: Memory file name (default: 'MEMORY.md')

        Returns:
            Result dictionary with success status

        """
        with self._lock:
            file_path = self._file_path(name)
            file_path.write_text(content, encoding="utf-8")
            return {"success": True, "name": name, "path": str(file_path)}

    def read_memory(self) -> str:
        """Read from MEMORY.md for persistent facts.

        Returns:
            MEMORY.md content or empty string

        """
        return self.read("MEMORY.md")

    def write_memory(self, content: str) -> dict[str, Any]:
        """Write to MEMORY.md for persistent facts.

        Args:
            content: Content to write

        Returns:
            Result dictionary

        """
        return self.write(content, "MEMORY.md")

    def read_user(self) -> str:
        """Read from USER.md for user preferences.

        Returns:
            USER.md content or empty string

        """
        return self.read("USER.md")

    def write_user(self, content: str) -> dict[str, Any]:
        """Write to USER.md for user preferences.

        Args:
            content: Content to write

        Returns:
            Result dictionary

        """
        return self.write(content, "USER.md")

    def update(self, key: str, value: str, name: str = "MEMORY.md") -> dict[str, Any]:
        """Update a specific key in memory file.

        Args:
            key: Key to update
            value: Value to set
            name: Memory file name

        Returns:
            Result dictionary

        """
        content = self.read(name)
        lines = content.split("\n") if content else []
        found = False
        new_lines = []

        for line in lines:
            if line.startswith(f"{key}:"):
                new_lines.append(f"{key}: {value}")
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(f"{key}: {value}")

        return self.write("\n".join(new_lines), name)

    def delete(self, key: str, name: str = "MEMORY.md") -> dict[str, Any]:
        """Delete a key from memory file.

        Args:
            key: Key to delete
            name: Memory file name

        Returns:
            Result dictionary

        """
        content = self.read(name)
        lines = content.split("\n") if content else []
        new_lines = [line for line in lines if not line.startswith(f"{key}:")]

        return self.write("\n".join(new_lines), name)


__all__ = ["LongTermMemory"]
