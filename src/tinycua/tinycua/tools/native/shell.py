"""Shell execution tool.

Provides ``run_shell`` for executing arbitrary shell commands and
capturing stdout, stderr, and exit codes with configurable timeout.
"""

import os
import signal
import subprocess
from typing import Any

from tinycua_sdk.tools.decorators import tool

_IS_POSIX = os.name == "posix"


@tool
def run_shell(command: str, timeout: int = 30) -> dict[str, Any]:
    """Execute a shell command and capture its output.

    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        A dict with keys: stdout, stderr, exit_code, timed_out, error.
    """
    # Validate inputs before spawning
    if not isinstance(command, str):
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": f"Invalid command type: expected str, got {type(command).__name__}",
        }
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": f"Invalid timeout: {timeout}. Must be a positive number.",
        }

    process = None
    try:
        popen_kwargs: dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
        }
        if _IS_POSIX:
            popen_kwargs["preexec_fn"] = os.setsid
        else:
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        process = subprocess.Popen(
            command,
            shell=True,
            **popen_kwargs,
        )

        stdout, stderr = process.communicate(timeout=timeout)
        return {
            "stdout": stdout or "",
            "stderr": stderr or "",
            "exit_code": process.returncode,
            "timed_out": False,
            "error": None,
        }
    except subprocess.TimeoutExpired:
        try:
            if process is not None:
                if _IS_POSIX:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
        except ProcessLookupError:
            pass  # process already exited
        stdout, stderr = process.communicate() if process else ("", "")
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
