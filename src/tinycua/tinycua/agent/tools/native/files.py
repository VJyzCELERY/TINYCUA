"""File I/O tools.

Provides ``read_file``, ``write_file``, ``str_replace``, ``append_file``,
and ``list_files`` for file system interaction with path resolution,
fuzzy matching, and error handling.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from tinycua_sdk.tools.decorators import tool

from tinycua.agent.tools.native.context import (
    bind_workspace_to_tool,
    resolve_workspace_path,
    to_workspace_relative,
)

# Internal truncation limit for full-file reads (100 KB)
_FULL_FILE_TRUNCATION_BYTES = 100 * 1024


def _resolve_path(path: str) -> Path:
    """Resolve a path to an absolute Path.

    When the tool is bound to a session workspace, paths must remain inside
    that workspace. Otherwise legacy cwd-relative resolution is used.
    """
    return resolve_workspace_path(path)


# --- Helper functions for read_file ---


def _detect_literal_newline_warning(content: str) -> str:
    r"""Detect literal backslash-n on long lines and return a warning string.

    Local models sometimes write ``\\n`` (two literal characters) instead of
    real newlines, producing one giant line. This detects that pattern and
    returns a warning the model can see in the read_file output, so the
    reviewer can catch the malformation.

    Returns an empty string if no issue is detected.
    """
    lines = content.split("\n")
    for line in lines:
        if len(line) > 500 and "\\n" in line:
            return (
                "\n[Warning: this line contains literal \\n characters "
                "(backslash-n), not actual newlines. The file may be "
                "formatted intentionally or may be malformed; inspect the "
                "expected file format before changing it.]"
            )
    return ""


def _truncate_content(content_bytes: bytes, max_bytes: int, start_line: int = 1) -> str:
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
    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return {"error": str(exc)}

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


def _read_bounded_range(
    lines: list[str],
    trailing_newline: bool,
    start: int | None,
    offset: int,
    total_lines: int,
) -> str | dict[str, Any]:
    """Read a bounded [start, start+offset) range. Bypasses truncation."""
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


def _read_start_only(
    lines: list[str],
    trailing_newline: bool,
    start: int,
    total_lines: int,
) -> str:
    """Read from start to end of file. Subject to truncation."""
    if start < 1:
        return {"error": f"Invalid start line: {start}. Must be >= 1."}
    if start > total_lines:
        return {
            "error": f"Start line {start} exceeds file length ({total_lines} lines). Range out of bounds."
        }
    result_str = "\n".join(lines[start - 1 :])
    if trailing_newline:
        result_str += "\n"
    result_str += _detect_literal_newline_warning(result_str)
    result_bytes = result_str.encode("utf-8")
    if len(result_bytes) <= _FULL_FILE_TRUNCATION_BYTES:
        return result_str
    return _truncate_content(result_bytes, _FULL_FILE_TRUNCATION_BYTES, start)


def _read_full_file(content: str) -> str:
    """Read the entire file. Subject to truncation."""
    content += _detect_literal_newline_warning(content)
    if len(content.encode("utf-8")) <= _FULL_FILE_TRUNCATION_BYTES:
        return content
    return _truncate_content(content.encode("utf-8"), _FULL_FILE_TRUNCATION_BYTES)


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
    # ponytail: defensive int() — local models often emit "7" for line args
    # even though the schema declares integer. The SDK coerces too, but this
    # keeps direct tool() calls and any bypass path from crashing.
    try:
        if start is not None:
            start = int(start)
        if offset is not None:
            offset = int(offset)
    except (TypeError, ValueError) as exc:
        return {
            "error": f"Invalid line argument (start/offset must be integers): {exc}"
        }
    result = _read_lines(path)
    if isinstance(result, dict):
        return result  # error dict
    lines, content, trailing_newline = result

    total_lines = len(lines)

    # --- Bounded range mode: offset is explicitly set ---
    # Only bounded ranges (start + offset) bypass the truncation limit.
    if offset is not None:
        return _read_bounded_range(lines, trailing_newline, start, offset, total_lines)

    # --- Start-only mode: unbounded read from N to end ---
    # This is still subject to truncation since the range is open-ended.
    if start is not None:
        return _read_start_only(lines, trailing_newline, start, total_lines)

    # --- Full-file mode: no start, no offset ---
    return _read_full_file(content)


# --- write_file ---


@tool
def write_file(path: str, content: str) -> dict[str, Any]:
    """Write content to a file when its parent directory exists.

    Args:
        path: Path to the file. Absolute paths start with '/', relative
            paths are resolved from the current working directory.
        content: The content to write to the file.

    Returns:
        A dict with keys: success, path, chars_written, error.
    """
    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return {
            "success": False,
            "path": path,
            "rel_path": path,
            "chars_written": 0,
            "error": str(exc),
        }

    if not resolved.parent.exists():
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "chars_written": 0,
            "new_file_size": 0,
            "diff_preview": None,
            "error": f"Parent directory does not exist: {resolved.parent}",
        }

    try:
        chars_written = resolved.write_text(content, encoding="utf-8")
        result: dict[str, Any] = {
            "success": True,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "chars_written": chars_written,
            "new_file_size": len(content.encode("utf-8")),
            "diff_preview": content[:500],
            "error": None,
        }
        return result
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "chars_written": 0,
            "new_file_size": 0,
            "diff_preview": None,
            "error": f"Permission denied: {path}",
        }
    except Exception as exc:
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "chars_written": 0,
            "new_file_size": 0,
            "diff_preview": None,
            "error": str(exc),
        }


# --- str_replace (content-based edit with fuzzy matching) ---


def _find_all(haystack: str, needle: str) -> list[tuple[int, int]]:
    """Return all (start, end) positions of needle in haystack."""
    matches: list[tuple[int, int]] = []
    start = 0
    while True:
        pos = haystack.find(needle, start)
        if pos == -1:
            break
        matches.append((pos, pos + len(needle)))
        start = pos + 1
    return matches


def _strategy_exact(content: str, old: str) -> list[tuple[int, int]]:
    """Strategy 1: exact substring match."""
    return _find_all(content, old)


def _strategy_line_trimmed(content: str, old: str) -> list[tuple[int, int]]:
    """Strategy 2: match after stripping each line of both sides."""
    old_lines = [line.strip() for line in old.split("\n")]
    old_norm = "\n".join(old_lines)
    content_lines = content.split("\n")
    content_norm_lines = [line.strip() for line in content_lines]
    content_norm = "\n".join(content_norm_lines)
    norm_matches = _find_all(content_norm, old_norm)
    if not norm_matches:
        return []
    # Map normalized positions back to original — approximate by line counting.
    return _map_line_matches(
        content_lines, content_norm_lines, old_lines, norm_matches, content
    )


def _strategy_whitespace_normalized(content: str, old: str) -> list[tuple[int, int]]:
    """Strategy 3: collapse runs of spaces/tabs to single space."""

    def normalize(s: str) -> str:
        return re.sub(r"[ \t]+", " ", s)

    old_norm = normalize(old)
    content_norm = normalize(content)
    norm_matches = _find_all(content_norm, old_norm)
    if not norm_matches:
        return []
    return _map_normalized_positions(content, content_norm, norm_matches)


def _strategy_indentation_flexible(content: str, old: str) -> list[tuple[int, int]]:
    """Strategy 4: strip all leading whitespace from each line before matching."""
    old_lines = [line.lstrip() for line in old.split("\n")]
    old_norm = "\n".join(old_lines)
    content_lines = content.split("\n")
    content_norm_lines = [line.lstrip() for line in content_lines]
    content_norm = "\n".join(content_norm_lines)
    norm_matches = _find_all(content_norm, old_norm)
    if not norm_matches:
        return []
    return _map_line_matches(
        content_lines, content_norm_lines, old_lines, norm_matches, content
    )


def _strategy_escape_normalized(content: str, old: str) -> list[tuple[int, int]]:
    """Strategy 5: unescape common escape sequences in old_string."""
    old_unescaped = (
        old.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace('\\"', '"')
        .replace("\\'", "'")
    )
    if old_unescaped == old:
        return []  # no escapes to normalize — skip
    return _find_all(content, old_unescaped)


def _strategy_trimmed_boundary(content: str, old: str) -> list[tuple[int, int]]:
    """Strategy 6: trim whitespace from first and last lines only."""
    old_lines = old.split("\n")
    if len(old_lines) <= 1:
        return []  # single line — trimming boundary = line_trimmed
    old_lines[0] = old_lines[0].strip()
    old_lines[-1] = old_lines[-1].strip()
    old_mod = "\n".join(old_lines)
    if old_mod == old:
        return []  # no change — skip
    content_lines = content.split("\n")
    pattern_count = len(old_lines)
    matches: list[tuple[int, int]] = []
    for i in range(len(content_lines) - pattern_count + 1):
        block = content_lines[i : i + pattern_count].copy()
        block[0] = block[0].strip()
        block[-1] = block[-1].strip()
        if "\n".join(block) == old_mod:
            start_pos = sum(len(content_lines[j]) + 1 for j in range(i))
            end_pos = start_pos + len(content_lines[i])
            for j in range(i + 1, i + pattern_count):
                end_pos += 1 + len(content_lines[j])
            matches.append((start_pos, end_pos))
    return matches


def _strategy_unicode_normalized(content: str, old: str) -> list[tuple[int, int]]:
    """Strategy 7: normalize unicode (NFC) before matching."""
    old_norm = unicodedata.normalize("NFC", old)
    content_norm = unicodedata.normalize("NFC", content)
    if old_norm == old and content_norm == content:
        return []  # no unicode differences — skip
    norm_matches = _find_all(content_norm, old_norm)
    if not norm_matches:
        return []
    return _map_normalized_positions(content, content_norm, norm_matches)


def _map_normalized_positions(
    original: str, normalized: str, norm_matches: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """Map positions from normalized content back to original content.

    Approximate mapping by character offset — works when normalization
    only changes character values (not lengths), which is true for
    whitespace-collapse and unicode-normalize strategies.
    """
    if len(original) == len(normalized):
        return norm_matches  # 1:1 position mapping
    # Build an offset map from normalized → original positions.
    orig_to_norm: list[int] = _build_orig_to_norm_map(original, normalized)
    results: list[tuple[int, int]] = []
    for norm_start, norm_end in norm_matches:
        # Find the original positions that map to these normalized positions.
        orig_start = _map_position(orig_to_norm, norm_start)
        orig_end = _map_position(orig_to_norm, norm_end)
        if orig_start is not None and orig_end is not None:
            results.append((orig_start, orig_end))
    return results


def _build_orig_to_norm_map(original: str, normalized: str) -> list[int]:
    """Build a mapping from original char index → normalized char index.

    Assumes normalization is character-by-character (whitespace collapse,
    unicode). When original and normalized have different lengths, we
    align them by walking both strings.
    """
    mapping: list[int] = []
    oi, ni = 0, 0
    while oi < len(original) and ni < len(normalized):
        if original[oi] == normalized[ni]:
            mapping.append(ni)
            oi += 1
            ni += 1
        else:
            # Original char was collapsed/skipped — map to next norm position.
            mapping.append(ni)
            oi += 1
    while oi < len(original):
        mapping.append(ni - 1 if ni > 0 else 0)
        oi += 1
    return mapping


def _map_position(orig_to_norm: list[int], norm_pos: int) -> int | None:
    """Map a normalized position back to an original position."""
    for orig_idx, norm_idx in enumerate(orig_to_norm):
        if norm_idx >= norm_pos:
            return orig_idx
    return None


def _map_line_matches(
    content_lines: list[str],
    content_norm_lines: list[str],
    old_lines: list[str],
    norm_matches: list[tuple[int, int]],
    original_content: str,
) -> list[tuple[int, int]]:
    """Map line-based normalized matches back to original char positions."""
    old_line_count = len(old_lines)
    results: list[tuple[int, int]] = []
    for norm_start, norm_end in norm_matches:
        # Find which line in normalized content the match starts at.
        norm_content = "\n".join(content_norm_lines)
        before = norm_content[:norm_start]
        start_line = before.count("\n")
        # Calculate original char positions from line indices.
        orig_start = sum(len(content_lines[j]) + 1 for j in range(start_line))
        end_line = start_line + old_line_count
        orig_end = sum(len(content_lines[j]) + 1 for j in range(start_line, end_line))
        # For single-line matches, adjust the end within the line.
        if old_line_count == 1:
            # Find the position within the line.
            line_content = content_lines[start_line]
            line_norm = content_norm_lines[start_line]
            # Simpler: just find old[0] in the stripped line.
            stripped_old = old_lines[0]
            pos_in_stripped = line_norm.find(stripped_old)
            if pos_in_stripped >= 0:
                # Find the corresponding position in the original line.
                orig_line_pos = _find_in_original_line(
                    line_content, stripped_old, pos_in_stripped
                )
                if orig_line_pos >= 0:
                    orig_start = (
                        sum(len(content_lines[j]) + 1 for j in range(start_line))
                        + orig_line_pos
                    )
                    orig_end = orig_start + len(old_lines[0])
        results.append((orig_start, orig_end))
    return results


def _find_in_original_line(
    line: str, stripped_pattern: str, pos_in_stripped: int
) -> int:
    """Find the position of stripped_pattern in the original (unstripped) line."""
    # For line-trimmed and indentation-flexible, the pattern's content
    # matches a contiguous region in the original line. Find it by
    # searching for the stripped pattern within the line.
    idx = line.find(stripped_pattern)
    if idx >= 0:
        return idx
    # If exact find fails, try finding by content (ignoring leading ws).
    for i in range(len(line)):
        if line[i:].startswith(stripped_pattern) or line[i:].lstrip().startswith(
            stripped_pattern
        ):
            return i
    return -1


# Ordered list of matching strategies (exact first, progressively fuzzier).
_MATCH_STRATEGIES = [
    ("exact", _strategy_exact),
    ("line_trimmed", _strategy_line_trimmed),
    ("whitespace_normalized", _strategy_whitespace_normalized),
    ("indentation_flexible", _strategy_indentation_flexible),
    ("escape_normalized", _strategy_escape_normalized),
    ("trimmed_boundary", _strategy_trimmed_boundary),
    ("unicode_normalized", _strategy_unicode_normalized),
]


def _fuzzy_find_and_replace(
    content: str,
    old_string: str,
    new_string: str,
    replace_all: bool,
) -> tuple[str, int, str | None]:
    """Find old_string in content using fuzzy matching and replace it.

    Tries each matching strategy in order. Returns (new_content, match_count, error).
    FR-052: distinguishes zero-match from multi-match errors so the model can
    tell whether to provide more context (multi-match) or fix the string
    (zero-match).
    """
    max_multi_match = 0  # FR-052: track the highest match count across strategies
    for strategy_name, strategy_fn in _MATCH_STRATEGIES:
        matches = strategy_fn(content, old_string)
        if not matches:
            continue
        if len(matches) > 1 and not replace_all:
            # FR-052: record the multi-match count for a distinct error, then
            # try the next strategy (a fuzzier one may narrow to 1 match).
            if len(matches) > max_multi_match:
                max_multi_match = len(matches)
            continue  # ambiguous — try next strategy
        # Safety guard: refuse if matched region is disproportionately large.
        old_line_count = old_string.count("\n") + 1
        for start, end in matches:
            matched_text = content[start:end]
            matched_lines = matched_text.count("\n") + 1
            if matched_lines >= 2 * old_line_count + 3:
                return (
                    content,
                    0,
                    (
                        f"Matched region ({matched_lines} lines) is disproportionately "
                        f"larger than old_string ({old_line_count} lines). Provide more "
                        f"context in old_string to narrow the match."
                    ),
                )
        # Apply replacements (work backwards to preserve positions).
        result = content
        for start, end in reversed(matches):
            result = result[:start] + new_string + result[end:]
        return result, len(matches), None
    # FR-052: if any strategy found >1 matches, return a distinct actionable error.
    if max_multi_match > 1:
        return (
            content,
            0,
            (
                f"Found {max_multi_match} matches for old_string. Provide more "
                f"context in old_string to disambiguate, or set replace_all=True "
                f"to replace all {max_multi_match}."
            ),
        )
    # All strategies found zero matches.
    return (
        content,
        0,
        f"Could not find old_string in the file. Check for exact whitespace and indentation. Tried {len(_MATCH_STRATEGIES)} matching strategies.",
    )


@tool
def str_replace(
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> dict[str, Any]:
    """Replace text in a file using content-based fuzzy matching.

    Finds ``old_string`` in the file and replaces it with ``new_string``.
    Matching is fuzzy — minor whitespace, indentation, escape-sequence, and
    unicode differences are tolerated across 7 matching strategies.

    If ``old_string`` is empty and the file doesn't exist, creates the file
    with ``new_string`` (like ``write_file``). If ``old_string`` appears
    multiple times and ``replace_all`` is False, returns an error asking
    for more context.

    Args:
        path: Path to the file. Absolute paths start with '/', relative
            paths are resolved from the current working directory.
        old_string: The text to find. Empty string = create new file.
        new_string: The replacement text. Must differ from old_string.
        replace_all: If True, replace all occurrences. Default False.

    Returns:
        A dict with keys: success, path, replacements_made, bytes_written,
        diff_preview, error.
    """
    if old_string == new_string:
        return {
            "success": False,
            "path": path,
            "rel_path": path,
            "replacements_made": 0,
            "bytes_written": 0,
            "diff_preview": None,
            "error": "old_string and new_string are identical.",
        }
    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return {
            "success": False,
            "path": path,
            "rel_path": path,
            "replacements_made": 0,
            "bytes_written": 0,
            "diff_preview": None,
            "error": str(exc),
        }
    # Empty old_string = create new file.
    if not old_string:
        if resolved.exists():
            return {
                "success": False,
                "path": str(resolved),
                "rel_path": to_workspace_relative(resolved),
                "replacements_made": 0,
                "bytes_written": 0,
                "diff_preview": None,
                "error": "old_string is empty but file exists. Use write_file to overwrite.",
            }
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(new_string, encoding="utf-8")
            return {
                "success": True,
                "path": str(resolved),
                "rel_path": to_workspace_relative(resolved),
                "replacements_made": 1,
                "bytes_written": len(new_string.encode("utf-8")),
                "diff_preview": new_string[:200],
                "error": None,
            }
        except Exception as exc:
            return {
                "success": False,
                "path": str(resolved),
                "rel_path": to_workspace_relative(resolved),
                "replacements_made": 0,
                "bytes_written": 0,
                "diff_preview": None,
                "error": str(exc),
            }
    # Read the file.
    if not resolved.exists():
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "replacements_made": 0,
            "bytes_written": 0,
            "diff_preview": None,
            "error": f"File not found: {path}",
        }
    try:
        content = resolved.read_text(encoding="utf-8")
        content = content.replace("\r\n", "\n")
    except Exception as exc:
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "replacements_made": 0,
            "bytes_written": 0,
            "diff_preview": None,
            "error": str(exc),
        }
    # Fuzzy find and replace.
    new_content, match_count, error = _fuzzy_find_and_replace(
        content, old_string, new_string, replace_all
    )
    if error:
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "replacements_made": match_count,
            "bytes_written": 0,
            "diff_preview": None,
            "error": error,
        }
    # Write the result.
    try:
        resolved.write_text(new_content, encoding="utf-8")
    except Exception as exc:
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "replacements_made": 0,
            "bytes_written": 0,
            "diff_preview": None,
            "error": str(exc),
        }
    # FR-058: build a real unified-diff snippet (first ~500 chars) so the
    # model can see what actually changed, not just new_string[:200].
    import difflib

    diff_lines = list(
        difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=to_workspace_relative(resolved),
            tofile=to_workspace_relative(resolved),
            n=1,
        )
    )
    diff_preview = "".join(diff_lines)[:500]
    result: dict[str, Any] = {
        "success": True,
        "path": str(resolved),
        "rel_path": to_workspace_relative(resolved),
        "replacements_made": match_count,
        "bytes_written": len(new_content.encode("utf-8")),
        "diff_preview": diff_preview,
        "error": None,
    }
    return result


# --- append_file ---


@tool
def append_file(path: str, content: str) -> dict[str, Any]:
    """Append content to the end of a file, creating it if needed.

    If the file exists and doesn't end with a newline, one is added
    before the appended content. Parent directories are created.

    Args:
        path: Path to the file. Absolute paths start with '/', relative
            paths are resolved from the current working directory.
        content: The content to append.

    Returns:
        A dict with keys: success, path, bytes_appended, error.
    """
    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return {
            "success": False,
            "path": path,
            "rel_path": path,
            "bytes_appended": 0,
            "error": str(exc),
        }
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "bytes_appended": 0,
            "error": f"Permission denied creating directory: {resolved.parent}",
        }
    try:
        if resolved.exists():
            existing = resolved.read_text(encoding="utf-8")
            # Ensure newline separator between existing and appended content.
            if existing and not existing.endswith("\n"):
                existing += "\n"
            combined = existing + content
        else:
            combined = content
        resolved.write_text(combined, encoding="utf-8")
        bytes_appended = len(content.encode("utf-8"))
        result: dict[str, Any] = {
            "success": True,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "bytes_appended": bytes_appended,
            "new_file_size": len(combined.encode("utf-8")),
            "diff_preview": f"--- appended ---\n{content[:500]}",
            "error": None,
        }
        return result
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "bytes_appended": 0,
            "new_file_size": 0,
            "diff_preview": None,
            "error": f"Permission denied: {path}",
        }
    except Exception as exc:
        return {
            "success": False,
            "path": str(resolved),
            "rel_path": to_workspace_relative(resolved),
            "bytes_appended": 0,
            "new_file_size": 0,
            "diff_preview": None,
            "error": str(exc),
        }


# --- list_files ---


@tool
def list_files(
    path: str = ".", pattern: str = "*", recursive: bool = False
) -> list[str] | dict[str, Any]:
    """List files and directories in a workspace path, including hidden entries.

    Accepts any directory path inside the workspace (not just the root) so an
    agent can inspect nested structure. Both files and directories are
    returned; directories are marked with a trailing ``/`` so the LLM can tell
    them apart from files. Hidden entries (``.venv``, ``.hidden.txt``) are
    included so reviewers/agents can see created workspace artifacts.

    Args:
        path: Directory path to list. Relative paths resolve from the session
            workspace root; absolute paths must stay inside the workspace.
        pattern: Glob filter applied to leaf names (default ``*`` = everything).
            Directories matching the pattern are included too.
        recursive: When True, walk the whole subtree and return relative paths
            from ``path`` for every entry below it (files and directories).

    Returns:
        A list of workspace-relative paths on success (directories suffixed
        with ``/``), or an error dict on failure.
    """
    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return {"error": str(exc)}

    if not resolved.exists():
        return {"error": f"Directory not found: {path}"}
    if not resolved.is_dir():
        return {"error": f"Not a directory: {path}"}

    try:
        if recursive:
            entries = sorted(resolved.rglob(pattern))
        else:
            entries = sorted(resolved.glob(pattern))
        # ponytail: include dirs (suffixed with /) so a reviewer can see created
        # artifacts like .venv. If throughput ever matters, add a files-only flag.
        # FR-035: return workspace-relative paths so the model has a short,
        # clean path to echo back, reducing the chance of path doubling.
        result = []
        for entry in entries:
            rel = to_workspace_relative(entry)
            if entry.is_dir():
                result.append(f"{rel}/")
            else:
                result.append(str(rel))
        return result
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as exc:
        return {"error": str(exc)}


# --- search_files ---


_MAX_SEARCH_FILE_SIZE = 1_048_576  # 1 MB — skip larger files to avoid OOM.

# Module-level loop detection state. tinycua executes one node at a time
# (no concurrency), so module-level state naturally resets between nodes
# because different nodes search for different things. If a node repeats
# the same search 4+ times, that's a genuine loop.
_last_search_key: tuple | None = None
_search_repeat_count: int = 0


def _check_search_loop(
    pattern: str,
    target: str,
    path: str,
    file_glob: str | None,
) -> str | None:
    """Return a block message if the same search is repeated 4+ times."""
    global _last_search_key, _search_repeat_count
    key = (pattern, target, path, file_glob or "")
    if key == _last_search_key:
        _search_repeat_count += 1
    else:
        _last_search_key = key
        _search_repeat_count = 1
    if _search_repeat_count >= 4:
        return (
            f"BLOCKED: You have run this exact search {_search_repeat_count} "
            "times. The results have not changed. Stop re-searching and "
            "proceed with your task."
        )
    return None


def _iter_searchable_files(
    root: Path,
    file_glob: str | None,
) -> list[Path]:
    """Yield files under root, optionally filtered by glob pattern."""
    if root.is_file():
        return [root]
    results: list[Path] = []
    for entry in sorted(root.rglob("*")):
        if not entry.is_file():
            continue
        if file_glob:
            import fnmatch

            if not fnmatch.fnmatch(entry.name, file_glob):
                continue
        results.append(entry)
    return results


def _search_collect_matches(
    files: list[Path],
    regex: re.Pattern,
    context: int,
) -> list[tuple[Path, int, str, list[str]]]:
    """Collect (filepath, line_num, line, ctx_lines) matches for content mode."""
    all_matches: list[tuple[Path, int, str, list[str]]] = []
    for filepath in files:
        try:
            if filepath.stat().st_size > _MAX_SEARCH_FILE_SIZE:
                continue
        except OSError:
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        content = content.replace("\r\n", "\n")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if regex.search(line):
                ctx_start = max(0, i - context)
                ctx_end = min(len(lines), i + context + 1)
                ctx_lines = lines[ctx_start:ctx_end]
                all_matches.append((filepath, i + 1, line, ctx_lines))
    return all_matches


def _search_counts(
    files: list[Path],
    regex: re.Pattern,
    limit: int,
    offset: int,
) -> list[str]:
    """Count matches per file."""
    file_counts: dict[str, int] = {}
    for filepath in files:
        try:
            if filepath.stat().st_size > _MAX_SEARCH_FILE_SIZE:
                continue
        except OSError:
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        content = content.replace("\r\n", "\n")
        lines = content.split("\n")
        for line in lines:
            if regex.search(line):
                file_counts[str(filepath)] = file_counts.get(str(filepath), 0) + 1
    result = [
        f"{fp}: {cnt} match{'es' if cnt != 1 else ''}"
        for fp, cnt in file_counts.items()
    ]
    return result[offset : offset + limit]


def _search_files_only(
    files: list[Path],
    regex: re.Pattern,
    limit: int,
    offset: int,
) -> list[str]:
    """Return file paths that contain at least one match."""
    file_paths: list[str] = []
    for filepath in files:
        try:
            if filepath.stat().st_size > _MAX_SEARCH_FILE_SIZE:
                continue
        except OSError:
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        content = content.replace("\r\n", "\n")
        lines = content.split("\n")
        if any(regex.search(line) for line in lines):
            file_paths.append(to_workspace_relative(filepath))
    return file_paths[offset : offset + limit]


def _render_content_matches(
    all_matches: list[tuple[Path, int, str, list[str]]],
    context: int,
    limit: int,
    offset: int,
) -> list[str]:
    """Render content-mode matches with optional context lines + pagination footer."""
    result: list[str] = []
    for filepath, line_num, line, ctx_lines in all_matches:
        rel = to_workspace_relative(filepath)
        if context > 0:
            for ci, ctx_line in enumerate(ctx_lines):
                ctx_line_num = line_num - context + ci
                if ctx_line_num < 1:
                    continue
                prefix = ">" if ctx_line == line else " "
                result.append(f"{rel}:{ctx_line_num}:{prefix} {ctx_line}")
            result.append("")  # blank line between matches
        else:
            result.append(f"{rel}:{line_num}: {line}")

    total = len(result)
    paged = result[offset : offset + limit]
    if total > limit:
        paged.append(
            f"[Showing {offset + 1}-{min(offset + limit, total)} of {total} total matches. "
            f"Use offset={offset + limit} to see more.]"
        )
    return paged


def _search_content(
    files: list[Path],
    pattern: str,
    context: int,
    output_mode: str,
    limit: int,
    offset: int,
) -> list[str]:
    """Search file contents for regex pattern. Returns formatted result lines."""
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return [f"[Invalid regex: {exc}]"]

    if output_mode == "files_only":
        return _search_files_only(files, regex, limit, offset)
    if output_mode == "count":
        return _search_counts(files, regex, limit, offset)
    # content mode
    all_matches = _search_collect_matches(files, regex, context)
    return _render_content_matches(all_matches, context, limit, offset)


def _search_files_by_name(
    root: Path,
    pattern: str,
    limit: int,
    offset: int,
) -> list[str]:
    """Find files by glob pattern under root."""
    import fnmatch

    results: list[str] = []
    if root.is_file():
        if fnmatch.fnmatch(root.name, pattern):
            results.append(to_workspace_relative(root))
    else:
        for entry in sorted(root.rglob("*")):
            if entry.is_file() and fnmatch.fnmatch(entry.name, pattern):
                results.append(to_workspace_relative(entry))

    total = len(results)
    paged = results[offset : offset + limit]
    if total > limit:
        paged.append(
            f"[Showing {offset + 1}-{min(offset + limit, total)} of {total} total files. "
            f"Use offset={offset + limit} to see more.]"
        )
    return paged


@tool
def search_files(
    pattern: str,
    target: str = "content",
    path: str = ".",
    file_glob: str | None = None,
    limit: int = 50,
    offset: int = 0,
    output_mode: str = "content",
    context: int = 0,
) -> list[str] | dict[str, Any]:
    """Search file contents (grep) or find files by name (glob).

    Uses regex for content search and glob patterns for file search.
    Prefer this over run_shell grep — it gives structured output with
    line numbers, context lines, and pagination.

    Args:
        pattern: Regex pattern (for target='content') or glob pattern
            (e.g. '*.py' for target='files').
        target: 'content' to search inside files, 'files' to find by name.
        path: Directory or file to search. Relative to workspace root.
        file_glob: Filter files by pattern (e.g. '*.py'). Content mode only.
        limit: Max results to return (default 50).
        offset: Skip first N results for pagination (default 0).
        output_mode: 'content' (matches with line numbers), 'files_only'
            (paths only), 'count' (match counts per file). Default 'content'.
        context: Lines of context before/after each match (default 0).

    Returns:
        List of formatted result strings, or an error dict on failure.
    """
    # Defensive int coercion (local models emit "7").
    try:
        limit = int(limit) if limit is not None else 50
        offset = int(offset) if offset is not None else 0
        context = int(context) if context is not None else 0
    except (TypeError, ValueError) as exc:
        return {"error": f"Invalid integer argument: {exc}"}

    # Loop detection.
    loop_msg = _check_search_loop(pattern, target, path, file_glob)
    if loop_msg:
        return {"error": loop_msg, "pattern": pattern, "blocked": True}

    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return {"error": str(exc)}

    if not resolved.exists():
        return {"error": f"Path not found: {path}"}

    try:
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        context = max(0, min(context, 10))

        if target == "files":
            results = _search_files_by_name(resolved, pattern, limit, offset)
        else:
            files = _iter_searchable_files(resolved, file_glob)
            results = _search_content(
                files, pattern, context, output_mode, limit, offset
            )

        if not results:
            return ["No matches found."]
        return results
    except Exception as exc:
        return {"error": str(exc)}


for _native_file_tool in (
    read_file,
    write_file,
    str_replace,
    append_file,
    list_files,
    search_files,
):
    bind_workspace_to_tool(_native_file_tool)
