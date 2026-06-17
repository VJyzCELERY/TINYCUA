"""Python execution tool.

Provides ``run_python`` for executing Python code in a subprocess and
capturing stdout, stderr, and exit codes with configurable timeout.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from tinycua_sdk.tools.decorators import tool

from tinycua.agent.tools.native.context import bind_workspace_to_tool, get_workspace_dir

_DEFAULT_TIMEOUT_SECONDS = 30
_MAX_TIMEOUT_SECONDS = 30


def _bounded_timeout(timeout: int) -> int:
    """Return a safe timeout for model-requested Python execution."""
    try:
        requested = int(timeout)
    except (TypeError, ValueError):
        return _DEFAULT_TIMEOUT_SECONDS
    return min(max(requested, 1), _MAX_TIMEOUT_SECONDS)


@tool
def run_python(code: str, timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Execute Python code and capture its output.

    Args:
        code: The Python code to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        A dict with keys: stdout, stderr, exit_code, timed_out, error.
    """
    result: dict[str, Any] = {
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "timed_out": False,
        "error": None,
    }
    effective_timeout = _bounded_timeout(timeout)

    try:
        workspace = get_workspace_dir()
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            cwd=str(workspace) if workspace is not None else None,
        )
        result["stdout"] = completed.stdout or ""
        result["stderr"] = completed.stderr or ""
        result["exit_code"] = completed.returncode

    except subprocess.TimeoutExpired:
        result["exit_code"] = -1
        result["timed_out"] = True
        result["error"] = f"Execution timed out after {effective_timeout}s"
    except subprocess.SubprocessError as exc:
        result["exit_code"] = -1
        result["error"] = str(exc)
    except Exception as exc:
        result["exit_code"] = -1
        result["error"] = str(exc)

    return result


bind_workspace_to_tool(run_python)
