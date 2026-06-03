"""Python execution tool.

Provides ``run_python`` for executing Python code in a subprocess and
capturing stdout, stderr, and exit codes with configurable timeout.
"""

import os
import signal
import subprocess
import sys
from typing import Any

from tinycua_sdk.tools.decorators import tool

_IS_POSIX = os.name == "posix"


@tool
def run_python(code: str, timeout: int = 30) -> dict[str, Any]:
    """Execute Python code and capture its output.

    Args:
        code: The Python code to execute.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        A dict with keys: stdout, stderr, exit_code, timed_out, error.
    """
    # Validate inputs before spawning
    if not isinstance(code, str):
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "timed_out": False,
            "error": f"Invalid code type: expected str, got {type(code).__name__}",
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
            [sys.executable, "-c", code],
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
            "error": f"Execution timed out after {timeout}s",
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
