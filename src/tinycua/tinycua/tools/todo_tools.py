"""Todo tracking tool stubs for TinyCUA nodes.

Provides concrete Tool instances for todo read/write operations.
"""

from __future__ import annotations

from tinycua.config.types import Tool


class TodoReadTool(Tool):
    """Tool stub for reading todo list state."""

    def __init__(self) -> None:
        super().__init__(name="todo_read")


class TodoWriteTool(Tool):
    """Tool stub for writing/updating todo list state."""

    def __init__(self) -> None:
        super().__init__(name="todo_write")
