"""Tool implementations for the Task Executor agent.

Provides native tools for shell execution, file I/O, web fetching,
and Python code execution, as well as CUA-specific tools.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua.agent.tools.native import (
    create_edit_file,
    create_fetch_url,
    create_list_files,
    create_read_file,
    create_run_python,
    create_run_shell,
    create_write_file,
    edit_file,
    fetch_url,
    list_files,
    read_file,
    run_python,
    run_shell,
    write_file,
)
from tinycua.agent.tools.todo import create_todo_list, reset_default_todo, todo_list

if TYPE_CHECKING:
    from tinycua.agent.tools.context import ExecutorContext

# ---------------------------------------------------------------------------
# register_all
# ---------------------------------------------------------------------------

_DEFAULT_CONTEXT: ExecutorContext | None = None


def register_all(context: ExecutorContext | None = None) -> list[Any]:
    """Return all basic tools with an optional shared *context*.

    If *context* is ``None``, a default ``ExecutorContext`` is created on
    first call (and cached for subsequent calls). Tools share the context
    so that state (e.g. todo list) is consistent across tool invocations.

    Returns a list of 8 ``Tool`` instances (7 native + 1 todo).
    """
    global _DEFAULT_CONTEXT

    if context is None:
        if _DEFAULT_CONTEXT is None:
            from tinycua.agent.tools.context import ExecutorContext  # noqa: PLC0415

            _DEFAULT_CONTEXT = ExecutorContext()
        context = _DEFAULT_CONTEXT

    return [
        create_run_shell(context),
        create_read_file(context),
        create_write_file(context),
        create_edit_file(context),
        create_list_files(context),
        create_fetch_url(context),
        create_run_python(context),
        create_todo_list(context),
    ]


__all__ = [
    "create_edit_file",
    "create_fetch_url",
    "create_list_files",
    "create_read_file",
    "create_run_python",
    "create_run_shell",
    "create_write_file",
    "edit_file",
    "fetch_url",
    "list_files",
    "read_file",
    "register_all",
    "run_python",
    "run_shell",
    "todo_list",
    "write_file",
]
