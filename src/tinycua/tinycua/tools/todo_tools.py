"""Session-bound todo tracking tools for TinyCUA nodes.

Provides concrete Tool instances for todo read/write operations.
"""

from __future__ import annotations

from tinycua.config.types import Tool
from typing import Any


class SessionTodoToolMixin:
    """Mixin providing ``bind_todo_store`` for session-bound todo tools.

    Centralises the identical 2-line ``bind_todo_store`` pattern that was
    duplicated between ``TodoReadTool`` and ``TodoWriteTool``, mirroring
    ``SessionTaskToolMixin`` in ``task_tools.py``.
    """

    _todo_store: list[dict[str, Any]]

    def bind_todo_store(self, todo_store: list[dict[str, Any]]) -> None:
        """Bind this tool to the active session's todo list."""
        self._todo_store = todo_store


class TodoReadTool(SessionTodoToolMixin, Tool):
    """Tool for reading todo list state."""

    def __init__(self) -> None:
        super().__init__(name="todo_read")
        self._todo_store: list[dict[str, Any]] = []

    def __call__(self) -> list[dict]:
        """Read the current todo list."""
        return [dict(item) for item in self._todo_store]


class TodoWriteTool(SessionTodoToolMixin, Tool):
    """Tool for writing/updating todo list state."""

    def __init__(self) -> None:
        super().__init__(name="todo_write")
        self._todo_store: list[dict[str, Any]] = []

    def __call__(
        self,
        descriptions: list[str] | None = None,
        done_index: int | None = None,
        update_index: int | None = None,
        update_description: str | None = None,
        update_status: str | None = None,
        delete_index: int | None = None,
    ) -> list[dict]:
        """Append, update, mark done, or delete todo items.

        Args:
            descriptions: Append new todo items with these descriptions.
            done_index: Mark the item at this index as done.
            update_index: Index of the item to update in-place.
            update_description: New description for the item at update_index.
            update_status: New status for the item at update_index
                ("pending", "in_progress", "done").
            delete_index: Remove the item at this index.
        """
        if descriptions is not None:
            for description in descriptions:
                self._todo_store.append({"description": description, "status": "pending"})
        if done_index is not None:
            if 0 <= done_index < len(self._todo_store):
                self._todo_store[done_index]["status"] = "done"
                self._todo_store[done_index]["done"] = True
        if update_index is not None and 0 <= update_index < len(self._todo_store):
            if update_description is not None:
                self._todo_store[update_index]["description"] = update_description
            if update_status is not None:
                self._todo_store[update_index]["status"] = update_status
                self._todo_store[update_index]["done"] = update_status == "done"
        if delete_index is not None and 0 <= delete_index < len(self._todo_store):
            self._todo_store.pop(delete_index)
        return [dict(item) for item in self._todo_store]
