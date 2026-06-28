"""Python execution tool.

Provides ``run_python`` for executing Python code in a subprocess and
capturing stdout, stderr, and exit codes with configurable timeout.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from tinycua_sdk.tools.decorators import tool

from tinycua.agent.tools.native._timeout import bounded_timeout
from tinycua.agent.tools.native.context import bind_workspace_to_tool, get_workspace_dir

_DEFAULT_TIMEOUT_SECONDS = 30
_MAX_TIMEOUT_SECONDS = 30


def _bounded_timeout(timeout: int) -> int | None:
    """Return a safe timeout, or None if the requested timeout exceeds the max.

    Returns None to signal the caller to reject the request with a clear
    error — consistent with run_shell's overflow handling.
    """
    return bounded_timeout(
        timeout,
        default=_DEFAULT_TIMEOUT_SECONDS,
        max_seconds=_MAX_TIMEOUT_SECONDS,
        reject_overflow=True,
    )


@tool
def run_python(code: str, timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Execute Python code and capture its output.

    Args:
        code: The Python code to execute.
        timeout: Maximum execution time in seconds (default 30, max 30).
            Requests above the max are rejected with a clear error.

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
    if effective_timeout is None:
        result["exit_code"] = -1
        result["error"] = (
            f"Timeout {timeout}s exceeds maximum of {_MAX_TIMEOUT_SECONDS}s. "
            "Use a shorter timeout."
        )
        return result

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
