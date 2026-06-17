"""Shell execution tool.

Provides ``run_shell`` for executing arbitrary shell commands and
capturing stdout, stderr, and exit codes with configurable timeout.
"""

from __future__ import annotations

import os
import signal
import subprocess
from typing import Any

from tinycua_sdk.tools.decorators import tool

from tinycua.agent.tools.native.context import bind_workspace_to_tool, get_workspace_dir

_DEFAULT_TIMEOUT_SECONDS = 30
_MAX_TIMEOUT_SECONDS = 30


def _bounded_timeout(timeout: int) -> int:
    """Return a safe timeout for model-requested shell execution."""
    try:
        requested = int(timeout)
    except (TypeError, ValueError):
        return _DEFAULT_TIMEOUT_SECONDS
    return min(max(requested, 1), _MAX_TIMEOUT_SECONDS)


def _uses_unsafe_mkdir_braces(command: str) -> bool:
    """Detect mkdir with brace expansion that POSIX /bin/sh won't expand."""
    if "mkdir" not in command or "{" not in command or "}" not in command:
        return False
    start = command.find("{")
    end = command.find("}", start)
    return start < end and "," in command[start:end]


@tool
def run_shell(command: str, timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Execute a shell command and capture its output.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        A dict with keys: stdout, stderr, exit_code, timed_out, error.
    """
    effective_timeout = _bounded_timeout(timeout)
    if _uses_unsafe_mkdir_braces(command):
        return {
            "stdout": "", "stderr": "",
            "exit_code": -1, "timed_out": False,
            "error": "POSIX /bin/sh does not expand mkdir braces; use explicit paths instead.",
        }
    try:
        workspace = get_workspace_dir()
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            preexec_fn=os.setsid,
            cwd=str(workspace) if workspace is not None else None,
        )
        stdout, stderr = process.communicate(timeout=effective_timeout)
        return {
            "stdout": stdout or "",
            "stderr": stderr or "",
            "exit_code": process.returncode,
            "timed_out": False,
            "error": None,
        }
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        stdout, stderr = process.communicate()
        return {
            "stdout": stdout or "",
            "stderr": stderr or "",
            "exit_code": -1,
            "timed_out": True,
            "error": f"Command timed out after {effective_timeout}s",
        }
    except subprocess.SubprocessError as exc:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": str(exc),
        }


bind_workspace_to_tool(run_shell)
