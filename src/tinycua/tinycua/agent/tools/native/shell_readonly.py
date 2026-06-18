"""Read-only shell tool for reviewer nodes.

Provides ``run_shell_readonly`` — same execution engine as ``run_shell``
but rejects commands that appear to modify the filesystem.  Reviewer
nodes use this to verify outcomes and check for regressions without
risk of accidental writes.
"""

from __future__ import annotations

import re
from typing import Any

from tinycua_sdk.tools.decorators import tool

from tinycua.agent.tools.native.context import bind_workspace_to_tool
from tinycua.agent.tools.native.shell import run_shell

# Heuristic patterns that indicate filesystem mutation.
# Matched against the command string before execution.
_WRITE_PATTERNS: list[tuple[str, str]] = [
    # More specific patterns first (pip install before install, >> before >)
    (r">>", "append redirection (>> file)"),
    (r">", "output redirection (> file)"),
    (r"\bpip\b.*install", "pip install modifies environment"),
    (r"\bapt\b.*install", "apt install modifies system"),
    (r"\bbrew\b.*install", "brew install modifies environment"),
    (r"\bcargo\b.*install", "cargo install modifies environment"),
    (r"\bnpm\b.*install", "npm install modifies environment"),
    (r"\bsed\b.*-i", "sed -i edits files in place"),
    (r"\bgit\b.*(commit|push|merge|rebase|checkout|reset|stash)", "git mutation"),
    (r"\bcurl\b.*-o\b", "curl -o writes to file"),
    (r"\bwget\b.*-O\b", "wget -O writes to file"),
    # Less specific patterns after
    (r"\bmv\b", "mv moves/renames files"),
    (r"\bcp\b", "cp copies files"),
    (r"\brm\b", "rm deletes files"),
    (r"\bmkdir\b", "mkdir creates directories"),
    (r"\btouch\b", "touch creates files"),
    (r"\bchmod\b", "chmod changes permissions"),
    (r"\bchown\b", "chown changes ownership"),
    (r"\bchgrp\b", "chgrp changes group ownership"),
    (r"\bln\b", "ln creates links"),
    (r"\btee\b", "tee writes to files"),
    (r"\binstall\b", "install copies files"),
    (r"\bdpkg\b", "dpkg modifies system packages"),
    (r"\byum\b", "yum modifies system packages"),
    (r"\bdd\b", "dd writes raw data"),
    (r"\btruncate\b", "truncate modifies files"),
]


def _detect_write_intent(command: str) -> str | None:
    """Return a reason string if the command looks like it modifies the filesystem.

    This is a heuristic guard rail, not a security boundary.  It catches
    obvious write operations so the reviewer cannot accidentally mutate the
    workspace while verifying outcomes.
    """
    for pattern, reason in _WRITE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return reason
    return None


@tool
def run_shell_readonly(command: str, timeout: int = 30) -> dict[str, Any]:
    """Execute a read-only shell command for verification and regression checks.

    This is the reviewer's shell tool.  It runs the same execution engine as
    ``run_shell`` but rejects commands that appear to modify the filesystem
    (write, delete, move, install packages, etc.).  Use it to run tests,
    inspect files, check diffs, and verify that previous work still works.

    Allowed: ``ls``, ``cat``, ``head``, ``tail``, ``grep``, ``find``,
    ``diff``, ``python -c``, ``pytest``, ``git status``, ``git log``,
    ``git diff``, ``wc``, ``file``, ``stat``, ``which``, ``env``, etc.

    Blocked: ``rm``, ``mv``, ``cp``, ``touch``, ``mkdir``, ``chmod``,
    ``pip install``, redirections (> >>), ``sed -i``, ``tee``, etc.

    Args:
        command: The shell command to execute. Runs under ``/bin/sh``.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        A dict with keys: stdout, stderr, exit_code, timed_out, error.
    """
    reason = _detect_write_intent(command)
    if reason is not None:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": (
                f"Command rejected — read-only shell cannot run commands that "
                f"modify the filesystem: {reason}. Use run_shell in the "
                f"executor node for write operations."
            ),
        }
    return run_shell(command, timeout=timeout)


bind_workspace_to_tool(run_shell_readonly)