"""Backward-compatible shim for tinycua.tools.native.python_exec.

Re-exports the Python execution tool so that existing code importing from
``tinycua.agent.tools.native.python_exec`` continues to work.
"""

from tinycua.tools.native.python_exec import run_python

__all__ = ["run_python"]
