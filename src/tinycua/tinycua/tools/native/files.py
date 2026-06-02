"""File I/O tools.

Provides ``read_file``, ``write_file``, and ``list_files``
for file system interaction with path resolution and error handling.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tinycua_sdk.tools.decorators import tool

# Internal truncation limit for full-file reads (100 KB)
_FULL_FILE_TRUNCATION_BYTES = 100 * 1024


def _resolve_path(path: str) -> Path:
    """Resolve a path to an absolute Path.

    If the path starts with ``/`` it is treated as absolute; otherwise it
    is resolved relative to ``os.getcwd()``.
    """
    if path.startswith("/"):
        return Path(path)
    return Path(os.getcwd()) / path


# --- Helper functions for read_file ---


def _truncate_content(
    content_bytes: bytes, max_bytes: int, start_line: int = 1
) -> str:
    """Truncate *content_bytes* to *max_bytes* and append a truncation notice.

    Truncation is performed at a byte boundary. Any trailing incomplete
    multi-byte UTF-8 sequence is silently ignored to avoid inserting
    replacement characters that could confuse LLMs.

    Args:
        content_bytes: The content to truncate, already UTF-8 encoded.
        max_bytes: Maximum number of bytes to keep.
        start_line: The starting line number (for the resume hint).

    Returns:
        Truncated content string with a truncation notice appended.
    """
    truncated = content_bytes[:max_bytes].decode("utf-8", errors="ignore")
    remaining_bytes = len(content_bytes) - max_bytes
    remaining_lines = content_bytes[max_bytes:].count(b"\n")
    lines_read = truncated.count("\n")
    next_start = start_line + lines_read
    return (
        f"{truncated}"
        f"\n[Truncated: {remaining_lines} lines remaining, ~{remaining_bytes} bytes not shown."
        f" Set start={next_start} to continue reading.]"
    )


def _read_lines(path: str) -> tuple[list[str], str, bool] | dict[str, Any]:
    """Read a file and split into lines, returning (lines, content, trailing_newline).

    Returns an error dict if the file cannot be read.
    """
    resolved = _resolve_path(path)

    if not resolved.exists():
        return {"error": f"File not found: {path}"}
    if not resolved.is_file():
        return {"error": f"Not a file: {path}"}

    try:
        content = resolved.read_text()
        content = content.replace("\r\n", "\n")
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as exc:
        return {"error": f"Failed to read file: {exc}"}

    trailing_newline = content.endswith("\n")
    lines = content.split("\n")
    if trailing_newline:
        lines = lines[:-1]
    return (lines, content, trailing_newline)


# --- read_file ---


@tool
def read_file(
    path: str, start: int | None = None, offset: int | None = None
) -> str | dict[str, Any]:
    """Read the contents of a file, optionally specifying a line range.

    When neither *start* nor *offset* are set, the entire file is read with
    an internal 100 KB truncation limit. When a range is specified (start
    and/or offset), truncation is bypassed.

    Args:
        path: Path to the file. Absolute paths start with '/', relative
            paths are resolved from the current working directory.
        start: The 1-indexed line number to start reading from (inclusive).
        offset: The number of lines to read from start.
            If None (and start is set), reads to end of file.

    Returns:
        The file content as a string on success, or an error dict on failure.
    """
    result = _read_lines(path)
    if isinstance(result, dict):
        return result  # error dict
    lines, content, trailing_newline = result

    total_lines = len(lines)
    content_bytes = content.encode("utf-8")

    # --- Bounded range mode: offset is explicitly set ---
    # Only bounded ranges (start + offset) bypass the truncation limit.
    if offset is not None:
        actual_start = start if start is not None else 1
        if actual_start < 1:
            return {"error": f"Invalid start line: {actual_start}. Must be >= 1."}
        if actual_start > total_lines:
            return {
                "error": f"Start line {actual_start} exceeds file length ({total_lines} lines). Range out of bounds."
            }
        start_idx = actual_start - 1
        if start_idx + offset > total_lines:
            return {
                "error": f"Start line {actual_start} + offset {offset} exceeds file length "
                f"({total_lines} lines). Range out of bounds."
            }
        selected = lines[start_idx : start_idx + offset]
        result_str = "\n".join(selected)
        if trailing_newline:
            result_str += "\n"
        return result_str

    # --- Start-only mode: unbounded read from N to end ---
    # This is still subject to truncation since the range is open-ended.
    if start is not None:
        if start < 1:
            return {"error": f"Invalid start line: {start}. Must be >= 1."}
        if start > total_lines:
            return {
                "error": f"Start line {start} exceeds file length ({total_lines} lines). Range out of bounds."
            }
        result_str = "\n".join(lines[start - 1 :])
        if trailing_newline:
            result_str += "\n"
        result_bytes = result_str.encode("utf-8")
        if len(result_bytes) <= _FULL_FILE_TRUNCATION_BYTES:
            return result_str
        return _truncate_content(result_bytes, _FULL_FILE_TRUNCATION_BYTES, start)

    # --- Full-file mode: no start, no offset ---
    if len(content_bytes) <= _FULL_FILE_TRUNCATION_BYTES:
        return content
    return _truncate_content(content_bytes, _FULL_FILE_TRUNCATION_BYTES)


# --- write_file ---


@tool
def write_file(path: str, content: str) -> dict[str, Any]:
    """Write content to a file, creating parent directories if needed.

    Args:
        path: Path to the file. Absolute paths start with '/', relative
            paths are resolved from the current working directory.
        content: The content to write to the file.

    Returns:
        A dict with keys: success, path, chars_written, error.
    """
    resolved = _resolve_path(path)

    # Create parent directories
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "chars_written": 0,
            "error": f"Permission denied creating directory: {resolved.parent}",
        }

    try:
        chars_written = resolved.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "path": str(resolved),
            "chars_written": chars_written,
            "error": None,
        }
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "chars_written": 0,
            "error": f"Permission denied: {path}",
        }
    except Exception as exc:
        return {
            "success": False,
            "path": str(resolved),
            "chars_written": 0,
            "error": str(exc),
        }


# --- list_files ---


@tool
def list_files(path: str = ".", pattern: str = "*") -> list[str] | dict[str, Any]:
    """List files in a directory, optionally filtered by a glob pattern.

    Args:
        path: Directory path. Absolute paths start with '/', relative
            paths are resolved from the current working directory.
        pattern: Glob pattern for filtering files (default: '*').

    Returns:
        A list of absolute file paths on success, or an error dict on failure.
    """
    resolved = _resolve_path(path)

    if not resolved.exists():
        return {"error": f"Directory not found: {path}"}
    if not resolved.is_dir():
        return {"error": f"Not a directory: {path}"}

    try:
        files = [str(p) for p in sorted(resolved.glob(pattern)) if p.is_file()]
        return files
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as exc:
        return {"error": str(exc)}
