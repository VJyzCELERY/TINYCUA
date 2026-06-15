"""Todo tracking tool stubs for TinyCUA nodes.

Provides concrete Tool instances for todo read/write operations.
"""

from __future__ import annotations

from tinycua.config.types import Tool
from tinycua.models.todo import Todo


_DEFAULT_TODO = Todo()


class TodoReadTool(Tool):
    """Tool stub for reading todo list state."""

    def __init__(self) -> None:
        super().__init__(name="todo_read")

    def __call__(self) -> list[dict]:
        """Read the current todo list."""
        return [item.__dict__ for item in _DEFAULT_TODO.items]


class TodoWriteTool(Tool):
    """Tool stub for writing/updating todo list state."""

    def __init__(self) -> None:
        super().__init__(name="todo_write")

    def __call__(self, descriptions: list[str] | None = None, done_index: int | None = None) -> list[dict]:
        """Append todo items or mark one done."""
        if descriptions is not None:
            for description in descriptions:
                _DEFAULT_TODO.append(description)
        if done_index is not None:
            _DEFAULT_TODO.mark_done(done_index)
        return TodoReadTool()()
