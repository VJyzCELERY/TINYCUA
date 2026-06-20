"""Tool implementations for the Task Executor agent.

Provides native tools for shell execution, file I/O, web fetching,
and Python code execution, as well as CUA-specific tools.
"""

from tinycua.agent.tools.native import (
    append_file,
    fetch_url,
    list_files,
    read_file,
    run_python,
    run_shell,
    str_replace,
    write_file,
)

__all__ = [
    "run_shell",
    "read_file",
    "write_file",
    "str_replace",
    "append_file",
    "list_files",
    "fetch_url",
    "run_python",
]