"""Backward-compatible shim for tinycua.tools.native.files.

Re-exports all file tools so that existing code importing from
``tinycua.agent.tools.native.files`` continues to work.
"""

from tinycua.tools.native.files import edit_file, list_files, read_file, write_file

__all__ = ["read_file", "write_file", "edit_file", "list_files"]
