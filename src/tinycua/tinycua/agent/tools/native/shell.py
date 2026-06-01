"""Shell execution tool.

Provides ``run_shell`` for executing arbitrary shell commands and
capturing stdout, stderr, and exit codes with configurable timeout.
"""

from __future__ import annotations

import os
import signal
import subprocess
from typing import TYPE_CHECKING, Any

from tinycua_sdk.tools.decorators import Tool, tool

if TYPE_CHECKING:
    from tinycua.agent.tools.context import ExecutorContext


@tool
def run_shell(command: str, timeout: int = 30) -> dict[str, Any]:
    """Execute a shell command and capture its output.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        A dict with keys: stdout, stderr, exit_code, timed_out, error.
    """
    return _execute_shell(command, timeout)


def create_run_shell(context: ExecutorContext) -> Tool:
    """Create a ``run_shell`` tool bound to the given *context*.

    The returned tool clamps its *timeout* parameter to
    ``context.config.shell_timeout``, enforcing the operator's safety
    limit while still allowing shorter timeouts when explicitly requested.
    """
    def _execute(command: str, timeout: int = 30) -> dict[str, Any]:
        effective_timeout = min(timeout, context.config.shell_timeout)
        return _execute_shell(command, effective_timeout)

    return Tool.from_callable(_execute, name="run_shell")


def _execute_shell(command: str, timeout: int) -> dict[str, Any]:
    """Core shell execution logic shared by ``run_shell`` and factory tools."""
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        preexec_fn=os.setsid,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout)
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
            "error": f"Command timed out after {timeout}s",
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


__all__ = [
    "run_shell",
    "create_run_shell",
]
