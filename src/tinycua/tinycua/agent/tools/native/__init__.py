"""Native tools for the Task Executor agent.

These tools provide environment interaction capabilities:
shell execution, file I/O, web fetching, and Python code execution.
"""

from tinycua.agent.tools.native.files import (
    append_file,
    list_files,
    read_file,
    str_replace,
    write_file,
)
from tinycua.agent.tools.native.python_exec import run_python
from tinycua.agent.tools.native.shell import run_shell
from tinycua.agent.tools.native.web import fetch_url
from tinycua.agent.tools.native.web_search import web_search

__all__ = [
    "run_shell",
    "read_file",
    "write_file",
    "str_replace",
    "append_file",
    "list_files",
    "fetch_url",
    "web_search",
    "run_python",
]