"""File manager tool — main entry point.

This tool demonstrates a tool that wraps a whole mini-library:
  file_manager.py  → @tool decorators
  validators.py    → path validation logic
  permissions.py   → read/write permission checks
"""

from pathlib import Path

from tinycua_sdk import tool

from .validators import validate_path
from .permissions import check_access


@tool
def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read the contents of a file.

    Args:
        path: Absolute or relative file path.
        encoding: File encoding (default: utf-8).
    """
    resolved = validate_path(path)
    check_access(resolved, mode="read")
    return resolved.read_text(encoding=encoding)


@tool
def write_file(path: str, content: str, encoding: str = "utf-8") -> str:
    """Write content to a file (creates parent directories if needed).

    Args:
        path: Absolute or relative file path.
        content: Text to write.
        encoding: File encoding (default: utf-8).
    """
    resolved = validate_path(path)
    check_access(resolved, mode="write")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding=encoding)
    return f"Wrote {len(content)} chars to {resolved}"


@tool
def list_directory(path: str = ".") -> list[str]:
    """List files and directories at the given path.

    Args:
        path: Directory path (default: current directory).
    """
    resolved = validate_path(path)
    check_access(resolved, mode="read")
    return [str(p.name) for p in resolved.iterdir()]
