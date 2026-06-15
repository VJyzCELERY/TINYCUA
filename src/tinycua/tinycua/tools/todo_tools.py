"""Session-bound todo tracking tools for TinyCUA nodes.

Provides concrete Tool instances for todo read/write operations.
"""

from __future__ import annotations

from tinycua.config.types import Tool
from typing import Any


class TodoReadTool(Tool):
    """Tool for reading todo list state."""

    def __init__(self) -> None:
        super().__init__(name="todo_read")
        self._todo_store: list[dict[str, Any]] = []

    def bind_todo_store(self, todo_store: list[dict[str, Any]]) -> None:
        """Bind this tool to the active session's todo list."""
        self._todo_store = todo_store

    def __call__(self) -> list[dict]:
        """Read the current todo list."""
        return [dict(item) for item in self._todo_store]


class TodoWriteTool(Tool):
    """Tool for writing/updating todo list state."""

    def __init__(self) -> None:
        super().__init__(name="todo_write")
        self._todo_store: list[dict[str, Any]] = []

    def bind_todo_store(self, todo_store: list[dict[str, Any]]) -> None:
        """Bind this tool to the active session's todo list."""
        self._todo_store = todo_store

    def __call__(
        self,
        descriptions: list[str] | None = None,
        done_index: int | None = None,
    ) -> list[dict]:
        """Append todo items or mark one done."""
        if descriptions is not None:
            for description in descriptions:
                self._todo_store.append({"description": description, "done": False})
        if done_index is not None:
            if 0 <= done_index < len(self._todo_store):
                self._todo_store[done_index]["done"] = True
        return [dict(item) for item in self._todo_store]
