"""File I/O tools.

Provides ``read_file``, ``write_file``, ``edit_file``, and ``list_files``
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


def _count_lines(text: str) -> int:
    """Return the number of lines in a string (including trailing empty line)."""
    if not text:
        return 0
    return len(text.split("\n")) - 1 if text.endswith("\n") else len(text.split("\n"))


# --- read_file ---


@tool
def read_file(path: str, start: int | None = None, offset: int | None = None) -> str | dict[str, Any]:
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
    resolved = _resolve_path(path)

    if not resolved.exists():
        return {"error": f"File not found: {path}"}
    if not resolved.is_file():
        return {"error": f"Not a file: {path}"}

    try:
        content = resolved.read_text()
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as exc:
        return {"error": f"Failed to read file: {exc}"}

    # Split into lines, handling trailing newline correctly.
    # When content ends with "\n", the trailing empty element from split is
    # an artifact — strip it so line counting is accurate.
    if content.endswith("\n"):
        lines = content.split("\n")[:-1]
    else:
        lines = content.split("\n")

    total_lines = len(lines)
    content_bytes = content.encode("utf-8")

    # --- Bounded range mode: offset is explicitly set ---
    # Only bounded ranges (start + offset) bypass the truncation limit.
    if offset is not None:
        if start is None:
            start = 1  # default to beginning when only offset is given
        if start < 1:
            return {"error": f"Invalid start line: {start}. Must be >= 1."}
        if start > total_lines:
            return {
                "error": f"Start line {start} exceeds file length ({total_lines} lines). Range out of bounds."
            }

        start_idx = start - 1
        if start_idx + offset > total_lines:
            return {
                "error": f"Start line {start} + offset {offset} exceeds file length "
                f"({total_lines} lines). Range out of bounds."
            }
        selected = lines[start_idx : start_idx + offset]
        result = "\n".join(selected)
        if content.endswith("\n"):
            result += "\n"
        return result

    # --- Start-only mode: unbounded read from N to end ---
    # This is still subject to truncation since the range is open-ended.
    if start is not None:
        if start < 1:
            return {"error": f"Invalid start line: {start}. Must be >= 1."}
        if start > total_lines:
            return {
                "error": f"Start line {start} exceeds file length ({total_lines} lines). Range out of bounds."
            }

        start_idx = start - 1
        selected = lines[start_idx:]
        result = "\n".join(selected)
        if content.endswith("\n"):
            result += "\n"

        # Apply truncation to the selected range
        result_bytes = result.encode("utf-8")
        if len(result_bytes) <= _FULL_FILE_TRUNCATION_BYTES:
            return result

        truncated = result_bytes[:_FULL_FILE_TRUNCATION_BYTES].decode("utf-8", errors="replace")
        remaining_bytes = len(result_bytes) - _FULL_FILE_TRUNCATION_BYTES
        remaining_content = result_bytes[_FULL_FILE_TRUNCATION_BYTES:].decode("utf-8", errors="replace")
        remaining_lines = remaining_content.count("\n")
        lines_read = truncated.count("\n")
        next_start = start + lines_read
        truncated += (
            f"\n[Truncated: {remaining_lines} lines remaining, ~{remaining_bytes} bytes not shown."
            f" Set start={next_start} to continue reading.]"
        )
        return truncated

    # --- Full-file mode: no start, no offset ---
    if len(content_bytes) <= _FULL_FILE_TRUNCATION_BYTES:
        return content

    truncated = content_bytes[:_FULL_FILE_TRUNCATION_BYTES].decode("utf-8", errors="replace")
    remaining_bytes = len(content_bytes) - _FULL_FILE_TRUNCATION_BYTES
    remaining_content = content_bytes[_FULL_FILE_TRUNCATION_BYTES:].decode("utf-8", errors="replace")
    remaining_lines = remaining_content.count("\n")
    lines_read = truncated.count("\n")
    next_start = 1 + lines_read
    truncated += (
        f"\n[Truncated: {remaining_lines} lines remaining, ~{remaining_bytes} bytes not shown."
        f" Set start={next_start} to continue reading.]"
    )
    return truncated


# --- write_file ---


@tool
def write_file(path: str, content: str) -> dict[str, Any]:
    """Write content to a file, creating parent directories if needed.

    Args:
        path: Path to the file. Absolute paths start with '/', relative
            paths are resolved from the current working directory.
        content: The content to write to the file.

    Returns:
        A dict with keys: success, path, bytes_written, error.
    """
    resolved = _resolve_path(path)

    # Create parent directories
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "bytes_written": 0,
            "error": f"Permission denied creating directory: {resolved.parent}",
        }

    try:
        bytes_written = resolved.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "path": str(resolved),
            "bytes_written": bytes_written,
            "error": None,
        }
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "bytes_written": 0,
            "error": f"Permission denied: {path}",
        }
    except Exception as exc:
        return {
            "success": False,
            "path": str(resolved),
            "bytes_written": 0,
            "error": str(exc),
        }


# --- edit_file ---


@tool
def edit_file(
    path: str,
    start: int,
    content: str,
    offset: int | None = None,
) -> dict[str, Any]:
    """Replace a range of lines in an existing file.

    Args:
        path: Path to the file. Absolute paths start with '/', relative
            paths are resolved from the current working directory.
        start: The 1-indexed line number to start replacing from (inclusive).
        content: The new content to insert (replaces the specified lines).
        offset: The number of lines to replace. If None, replaces from
            *start* to the end of the file.

    Returns:
        A dict with keys: success, path, start_line, lines_replaced,
        bytes_written, error.
    """
    resolved = _resolve_path(path)

    if not resolved.exists():
        return {
            "success": False,
            "path": str(resolved),
            "start_line": start,
            "lines_replaced": 0,
            "bytes_written": 0,
            "error": f"File not found: {path}",
        }

    try:
        original = resolved.read_text()
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "start_line": start,
            "lines_replaced": 0,
            "bytes_written": 0,
            "error": f"Permission denied: {path}",
        }
    except Exception as exc:
        return {
            "success": False,
            "path": str(resolved),
            "start_line": start,
            "lines_replaced": 0,
            "bytes_written": 0,
            "error": str(exc),
        }

    # Split into lines, handling trailing newline correctly.
    trailing_newline = original.endswith("\n")
    if trailing_newline:
        lines = original.split("\n")[:-1]
    else:
        lines = original.split("\n")
    total_lines = len(lines)

    if start < 1:
        return {
            "success": False,
            "path": str(resolved),
            "start_line": start,
            "lines_replaced": 0,
            "bytes_written": 0,
            "error": f"Invalid start line: {start}. Must be >= 1.",
        }

    if start > total_lines:
        return {
            "success": False,
            "path": str(resolved),
            "start_line": start,
            "lines_replaced": 0,
            "bytes_written": 0,
            "error": f"Start line {start} exceeds file length ({total_lines} lines). Range out of bounds.",
        }

    start_idx = start - 1  # convert to 0-indexed

    if offset is not None:
        if start_idx + offset > total_lines:
            return {
                "success": False,
                "path": str(resolved),
                "start_line": start,
                "lines_replaced": 0,
                "bytes_written": 0,
                "error": f"Start line {start} + offset {offset} exceeds file length "
                f"({total_lines} lines). Range out of bounds.",
            }
        end_idx = start_idx + offset
    else:
        end_idx = total_lines

    lines_replaced = end_idx - start_idx
    new_lines = content.split("\n")
    # If new content ends with newline, trim the trailing empty element
    if content.endswith("\n") and new_lines and new_lines[-1] == "":
        new_lines = new_lines[:-1]

    result_lines = lines[:start_idx] + new_lines + lines[end_idx:]
    result = "\n".join(result_lines)
    # Preserve trailing newline only when NOT replacing to end of file.
    # When replacing to end (offset is None), the new content's own
    # trailing newline (if any) will dictate the result.
    if trailing_newline and offset is not None:
        result += "\n"

    bytes_written = len(result.encode("utf-8"))
    resolved.write_text(result, encoding="utf-8")

    return {
        "success": True,
        "path": str(resolved),
        "start_line": start,
        "lines_replaced": lines_replaced,
        "bytes_written": bytes_written,
        "error": None,
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
