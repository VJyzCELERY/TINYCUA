"""Session-scoped memory facade over LocalStorage."""

from __future__ import annotations

import uuid
from typing import Any

from tinycua_sdk.storage.sqlite import LocalStorage


class MemorySession:
    """High-level API for session-scoped memory operations.

    Provides semantic memory operations (add, get, list, search, delete, clear)
    that delegate to LocalStorage. Auto-generates UUIDs for memory entries.
    """

    def __init__(self, session_id: str, storage: LocalStorage | None = None):
        """Initialize MemorySession.

        Args:
            session_id: Unique session identifier.
            storage: Optional LocalStorage instance. Defaults to a new
                LocalStorage using the default data directory.
        """
        self.session_id = session_id
        self._storage = storage or LocalStorage()

    def add(
        self,
        content: str,
        memory_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a memory entry to this session.

        Args:
            content: Memory content.
            memory_type: Type of memory (e.g., "fact", "conversation").
            metadata: Optional metadata dictionary.

        Returns:
            Auto-generated memory ID (UUID).
        """
        memory_id = str(uuid.uuid4())
        self._storage.save_memory(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            session_id=self.session_id,
            metadata=metadata,
        )
        return memory_id

    def get(self, memory_id: str) -> dict[str, Any] | None:
        """Retrieve a memory by ID.

        Args:
            memory_id: ID of the memory to retrieve.

        Returns:
            Memory dictionary or None if not found.
        """
        return self._storage.load_memory(memory_id)

    def list(self, memory_type: str | None = None) -> list[dict[str, Any]]:
        """List all memories for this session.

        Args:
            memory_type: Optional filter by memory type.

        Returns:
            List of memory dictionaries.
        """
        return self._storage.list_memory(
            session_id=self.session_id,
            memory_type=memory_type,
        )

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search memories by case-insensitive substring match on content.

        Args:
            query: Search query string.

        Returns:
            List of matching memory dictionaries.
        """
        all_memories = self.list()
        query_lower = query.lower()
        return [
            m for m in all_memories
            if query_lower in m.get("content", "").lower()
        ]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: ID of the memory to delete.

        Returns:
            True if deleted, False if not found.
        """
        return self._storage.delete_memory(memory_id)

    def clear(self) -> bool:
        """Delete all memories for this session.

        Returns:
            True if operation completed.
        """
        memories = self.list()
        for memory in memories:
            self._storage.delete_memory(memory["id"])
        return True
