"""Python execution tool.

Provides ``run_python`` for executing Python code in a subprocess and
capturing stdout, stderr, and exit codes with configurable timeout.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, Any

from tinycua_sdk.tools.decorators import Tool, tool

if TYPE_CHECKING:
    from tinycua.agent.tools.context import ExecutorContext


@tool
def run_python(code: str, timeout: int = 30) -> dict[str, Any]:
    """Execute Python code and capture its output.

    Args:
        code: The Python code to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        A dict with keys: stdout, stderr, exit_code, timed_out, error.
    """
    return _execute_python(code, timeout)


def _execute_python(code: str, timeout: int) -> dict[str, Any]:
    """Core Python execution logic shared by ``run_python`` and factory tools."""
    result: dict[str, Any] = {
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "timed_out": False,
        "error": None,
    }

    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result["stdout"] = completed.stdout or ""
        result["stderr"] = completed.stderr or ""
        result["exit_code"] = completed.returncode

    except subprocess.TimeoutExpired:
        result["exit_code"] = -1
        result["timed_out"] = True
        result["error"] = f"Execution timed out after {timeout}s"
    except subprocess.SubprocessError as exc:
        result["exit_code"] = -1
        result["error"] = str(exc)
    except Exception as exc:
        result["exit_code"] = -1
        result["error"] = str(exc)

    return result


def create_run_python(context: ExecutorContext) -> Tool:
    """Create a ``run_python`` tool bound to the given *context*.

    Checks ``context.config.enable_python_exec`` feature flag and clamps
    timeout to ``context.config.python_timeout``.
    """
    def _execute(code: str, timeout: int = 30) -> dict[str, Any]:
        if not context.config.enable_python_exec:
            return {
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "timed_out": False,
                "error": "run_python is disabled by executor configuration (enable_python_exec=False)",
            }
        effective_timeout = min(timeout, context.config.python_timeout)
        return _execute_python(code, effective_timeout)

    return Tool.from_callable(_execute, name="run_python")


__all__ = [
    "create_run_python",
    "run_python",
]
