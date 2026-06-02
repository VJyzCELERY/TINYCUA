"""Session model for tool state management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    """Per-session state container for tool execution.

    Carries the mutable state that session-aware tools (task tools,
    TodoList) access via closure injection.  A fresh ``Session`` is
    created for each top-level run and passed to tool factories so that
    tools can read/write state without explicit session parameters.
    """

    task_tree: dict[str, Any] | None = None
    """Root of the task tree (``TaskInit`` replaces this entirely)."""

    todo_list: list[dict[str, str]] | None = None
    """Per-session todo items.

    Each item has the shape ``{"status": "incomplete" | "completed",
    "todo": str}``.
    """


__all__ = ["Session"]
