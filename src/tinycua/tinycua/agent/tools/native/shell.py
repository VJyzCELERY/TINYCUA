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


@tool
def run_shell(command: str, timeout: int = 30) -> dict[str, Any]:
    """Execute a shell command and capture its output.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        A dict with keys: stdout, stderr, exit_code, timed_out, error.
    """
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
