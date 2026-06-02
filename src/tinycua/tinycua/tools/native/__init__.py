"""Native execution tools adapted from tinycua.agent.tools.native.

Provides ``run_shell``, ``read_file``, ``write_file``, ``list_files``,
``fetch_url``, and ``run_python`` for environment interaction.
"""

from tinycua.tools.native.files import list_files, read_file, write_file
from tinycua.tools.native.python_exec import run_python
from tinycua.tools.native.shell import run_shell
from tinycua.tools.native.web import fetch_url

__all__ = [
    "run_shell",
    "read_file",
    "write_file",
    "list_files",
    "fetch_url",
    "run_python",
]
