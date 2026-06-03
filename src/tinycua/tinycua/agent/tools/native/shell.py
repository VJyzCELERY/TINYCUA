"""Backward-compatible shim for tinycua.tools.native.shell.

Re-exports the shell tool so that existing code importing from
``tinycua.agent.tools.native.shell`` continues to work.
"""

from tinycua.tools.native.shell import run_shell

__all__ = ["run_shell"]
