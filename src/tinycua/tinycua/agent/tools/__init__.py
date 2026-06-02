"""Tool implementations for the Task Executor agent.

Provides native tools for shell execution, file I/O, web fetching,
and Python code execution, as well as CUA-specific tools.

Backward-compatible re-exports from tinycua.tools.
"""

from tinycua.tools import (
    edit_file,
    fetch_url,
    list_files,
    read_file,
    run_python,
    run_shell,
    write_file,
)

__all__ = [
    "run_shell",
    "read_file",
    "write_file",
    "edit_file",
    "list_files",
    "fetch_url",
    "run_python",
]
