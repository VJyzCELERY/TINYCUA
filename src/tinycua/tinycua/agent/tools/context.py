"""Shared execution context for all tools.

Provides :class:`ExecutorConfig` and :class:`ExecutorContext` dataclasses
that act as the shared state container for tool configuration, todo list,
and a reserved slot for Session state (M2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass
class ExecutorConfig:
    """Configuration for the tool executor.

    Attributes:
        shell_timeout: Maximum execution time for shell commands (seconds).
        python_timeout: Maximum execution time for Python code (seconds).
        fetch_timeout: Maximum request timeout for HTTP fetches (seconds).
        max_file_size: Maximum file size in bytes for full-file reads (100 KB).
        max_fetch_size: Maximum HTTP response body size in bytes (100 KB).
        allowed_paths: List of allowed directory paths for file operations.
            ``None`` means no restriction.
        enable_fetch: Whether the ``fetch_url`` tool is enabled.
        enable_python_exec: Whether the ``run_python`` tool is enabled.
    """

    shell_timeout: int = 30
    python_timeout: int = 30
    fetch_timeout: int = 30
    max_file_size: int = 102400  # 100 KB
    max_fetch_size: int = 102400  # 100 KB
    allowed_paths: list[str] | None = None  # None = no restriction
    enable_fetch: bool = True
    enable_python_exec: bool = True


@dataclass
class ExecutorContext:
    """Shared state container for all tools.

    Every tool created via the tool factories receives a reference to the
    same :class:`ExecutorContext` instance, enabling shared state (todo list)
    and consistent configuration (timeouts, feature flags, allowed paths).

    Attributes:
        session: Reserved for M2 (Session state). Always ``None`` in M1.
        todo_list: In-memory todo list instance. Created on demand if ``None``.
        config: The :class:`ExecutorConfig` instance with tool configuration.
    """

    session: Any | None = None  # Reserved for M2 — always None in M1
    todo_list: Any | None = None  # Lazy-initialised TodoList
    config: ExecutorConfig = field(default_factory=ExecutorConfig)

    def get_todo_list(self):
        """Return the todo list, creating one on first access.

        This avoids forcing consumers to create a :class:`TodoList` instance
        when only native tools are used.
        """
        if self.todo_list is None:
            from tinycua.agent.tools.todo.todo_list import TodoList  # noqa: PLC0415

            self.todo_list = TodoList()
        return self.todo_list


__all__ = [
    "ExecutorConfig",
    "ExecutorContext",
]
