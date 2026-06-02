"""M1-scoped tool constants.

Provides ``NATIVE_BASE_TOOLS`` (the six native execution tools) and
``READ_ONLY_TASK_TOOLS`` (forward reference to M2).
"""

from __future__ import annotations

from tinycua.tools.native.files import list_files, read_file, write_file
from tinycua.tools.native.python_exec import run_python
from tinycua.tools.native.shell import run_shell
from tinycua.tools.native.web import fetch_url

# The six M1 native execution tools — stateless convenience reference.
NATIVE_BASE_TOOLS = [
    run_shell,
    read_file,
    write_file,
    list_files,
    fetch_url,
    run_python,
]

# Forward reference to M2 task read tools (ReadActiveTask, ReadTask, ListTask).
# Placeholder only — not implemented until M2.
READ_ONLY_TASK_TOOLS: list = []
