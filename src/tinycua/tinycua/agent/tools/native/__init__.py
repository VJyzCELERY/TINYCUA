"""Backward-compatible shims for tinycua.tools.native.

This package re-exports all native tools so that existing code importing
from ``tinycua.agent.tools.native.*`` continues to work.
"""

from tinycua.tools.native.files import edit_file, list_files, read_file, write_file
from tinycua.tools.native.python_exec import run_python
from tinycua.tools.native.shell import run_shell
from tinycua.tools.native.web import fetch_url

__all__ = [
    "run_shell",
    "read_file",
    "write_file",
    "edit_file",
    "list_files",
    "fetch_url",
    "run_python",
]
