"""Shell execution tool.

Provides ``run_shell`` for executing arbitrary shell commands and
capturing stdout, stderr, and exit codes with configurable timeout.
"""

from __future__ import annotations

import subprocess
import threading
from typing import Any

from tinycua_sdk.tools.decorators import tool


@tool
def run_shell(command: str, timeout: int = 30) -> dict[str, Any]:
    """Execute a shell command and capture its output.

    Args:
        command: The shell command to execute.
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

    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        timer = threading.Timer(timeout, lambda p: p.kill(), [process])
        timer.daemon = True
        timer.start()

        try:
            stdout_data, stderr_data = process.communicate()
            result["stdout"] = stdout_data or ""
            result["stderr"] = stderr_data or ""
            result["exit_code"] = process.returncode or 0
            if process.returncode == -9:
                result["timed_out"] = True
                result["exit_code"] = -1
        finally:
            timer.cancel()

    except FileNotFoundError:
        result["exit_code"] = 127
        result["stderr"] = f"Command not found: {command}"
        result["error"] = f"Command not found: {command}"
    except Exception as exc:
        result["exit_code"] = -1
        result["error"] = str(exc)
        result["timed_out"] = False

    return result
