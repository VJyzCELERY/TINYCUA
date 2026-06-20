"""File I/O tools.

Provides ``read_file``, ``write_file``, ``str_replace``, ``append_file``,
and ``list_files`` for file system interaction with path resolution,
fuzzy matching, and error handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tinycua_sdk.tools.decorators import tool

from tinycua.agent.tools.native.context import (
    bind_workspace_to_tool,
    resolve_workspace_path,
)

# Internal truncation limit for full-file reads (100 KB)
_FULL_FILE_TRUNCATION_BYTES = 100 * 1024


def _normalize_newlines(text: str) -> str:
    """Unescape literal backslash-n/t/r to real control characters.

    Local models (qwen3.5-9b on llama.cpp/LM Studio) sometimes send ``\\n``
    (backslash + n as two literal characters) in JSON tool-call arguments
    instead of an actual newline byte. Cloud APIs (GPT-4, Claude) handle
    this correctly, but local inference servers don't always deserialize
    the escape properly. Writing the literal two-character sequence to a
    file produces one giant line instead of properly formatted content.

    This function unescapes ``\\n``, ``\\t``, and ``\\r`` to their real
    control-character equivalents, but ONLY when:
    - The text contains the literal two-character sequence (``\\n`` etc.)
    - The text does NOT already contain the corresponding real character

    This avoids mangling source code that legitimately contains ``\\n`` as
    a string literal (e.g. Python ``sep = "\\n"``) — in those cases, the
    content already has real newlines elsewhere, so the heuristic leaves
    the literal ``\\n`` alone.
    """
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")
    if "\\t" in text and "\t" not in text:
        text = text.replace("\\t", "\t")
    if "\\r" in text and "\r" not in text:
        text = text.replace("\\r", "\r")
    return text


def _resolve_path(path: str) -> Path:
    """Resolve a path to an absolute Path.

    When the tool is bound to a session workspace, paths must remain inside
    that workspace. Otherwise legacy cwd-relative resolution is used.
    """
    return resolve_workspace_path(path)


# --- Helper functions for read_file ---


def _detect_literal_newline_warning(content: str) -> str:
    """Detect literal backslash-n on long lines and return a warning string.

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
                "malformed — use str_replace to fix the literal \\n to "
                "real newlines.]"
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
        return {"error": f"Invalid line argument (start/offset must be integers): {exc}"}
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
        result_str += _detect_literal_newline_warning(result_str)
        result_bytes = result_str.encode("utf-8")
        if len(result_bytes) <= _FULL_FILE_TRUNCATION_BYTES:
            return result_str
        return _truncate_content(result_bytes, _FULL_FILE_TRUNCATION_BYTES, start)

    # --- Full-file mode: no start, no offset ---
    content += _detect_literal_newline_warning(content)
    if len(content.encode("utf-8")) <= _FULL_FILE_TRUNCATION_BYTES:
        return content
    return _truncate_content(content.encode("utf-8"), _FULL_FILE_TRUNCATION_BYTES)


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
    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return {
            "success": False,
            "path": path,
            "chars_written": 0,
            "error": str(exc),
        }

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
        content = _normalize_newlines(content)
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


# --- str_replace (content-based edit with fuzzy matching) ---


import re
import unicodedata


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
    return _map_line_matches(content_lines, content_norm_lines, old_lines, norm_matches, content)


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
    return _map_line_matches(content_lines, content_norm_lines, old_lines, norm_matches, content)


def _strategy_escape_normalized(content: str, old: str) -> list[tuple[int, int]]:
    """Strategy 5: unescape common escape sequences in old_string."""
    old_unescaped = old.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "\r").replace('\\"', '"').replace("\\'", "'")
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
            rel_start = norm_start - (len(norm_content[:norm_start]) - len(before)) if before else norm_start
            # Simpler: just find old[0] in the stripped line.
            stripped_old = old_lines[0]
            pos_in_stripped = line_norm.find(stripped_old)
            if pos_in_stripped >= 0:
                # Find the corresponding position in the original line.
                orig_line_pos = _find_in_original_line(line_content, stripped_old, pos_in_stripped)
                if orig_line_pos >= 0:
                    orig_start = sum(len(content_lines[j]) + 1 for j in range(start_line)) + orig_line_pos
                    orig_end = orig_start + len(old_lines[0])
        results.append((orig_start, orig_end))
    return results


def _find_in_original_line(line: str, stripped_pattern: str, pos_in_stripped: int) -> int:
    """Find the position of stripped_pattern in the original (unstripped) line."""
    # For line-trimmed and indentation-flexible, the pattern's content
    # matches a contiguous region in the original line. Find it by
    # searching for the stripped pattern within the line.
    idx = line.find(stripped_pattern)
    if idx >= 0:
        return idx
    # If exact find fails, try finding by content (ignoring leading ws).
    for i in range(len(line)):
        if line[i:].startswith(stripped_pattern) or line[i:].lstrip().startswith(stripped_pattern):
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
    """
    for strategy_name, strategy_fn in _MATCH_STRATEGIES:
        matches = strategy_fn(content, old_string)
        if not matches:
            continue
        if len(matches) > 1 and not replace_all:
            continue  # ambiguous — try next strategy
        # Safety guard: refuse if matched region is disproportionately large.
        old_line_count = old_string.count("\n") + 1
        for start, end in matches:
            matched_text = content[start:end]
            matched_lines = matched_text.count("\n") + 1
            if matched_lines >= 2 * old_line_count + 3:
                return content, 0, (
                    f"Matched region ({matched_lines} lines) is disproportionately "
                    f"larger than old_string ({old_line_count} lines). Provide more "
                    f"context in old_string to narrow the match."
                )
        # Apply replacements (work backwards to preserve positions).
        result = content
        for start, end in reversed(matches):
            result = result[:start] + new_string + result[end:]
        return result, len(matches), None
    # All strategies failed to find a unique match.
    return content, 0, f"Could not find old_string in the file. Check for exact whitespace and indentation. Tried {len(_MATCH_STRATEGIES)} matching strategies."


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
            "replacements_made": 0,
            "bytes_written": 0,
            "diff_preview": None,
            "error": "old_string and new_string are identical.",
        }
    # Unescape literal \n, \t, \r that local models send as two-character
    # sequences in JSON tool-call arguments. This prevents malformed files
    # where the entire content is on one line with literal backslash-n.
    new_string = _normalize_newlines(new_string)
    old_string = _normalize_newlines(old_string)
    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return {
            "success": False,
            "path": path,
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
                "replacements_made": 1,
                "bytes_written": len(new_string.encode("utf-8")),
                "diff_preview": new_string[:200],
                "error": None,
            }
        except Exception as exc:
            return {
                "success": False,
                "path": str(resolved),
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
            "replacements_made": 0,
            "bytes_written": 0,
            "diff_preview": None,
            "error": str(exc),
        }
    # Build a minimal diff preview (first 200 chars of the changed region).
    diff_preview = new_string[:200]
    return {
        "success": True,
        "path": str(resolved),
        "replacements_made": match_count,
        "bytes_written": len(new_content.encode("utf-8")),
        "diff_preview": diff_preview,
        "error": None,
    }


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
            "bytes_appended": 0,
            "error": str(exc),
        }
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "bytes_appended": 0,
            "error": f"Permission denied creating directory: {resolved.parent}",
        }
    try:
        content = _normalize_newlines(content)
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
        return {
            "success": True,
            "path": str(resolved),
            "bytes_appended": bytes_appended,
            "error": None,
        }
    except PermissionError:
        return {
            "success": False,
            "path": str(resolved),
            "bytes_appended": 0,
            "error": f"Permission denied: {path}",
        }
    except Exception as exc:
        return {
            "success": False,
            "path": str(resolved),
            "bytes_appended": 0,
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
        A list of absolute paths on success (directories suffixed with ``/``),
        or an error dict on failure.
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
        result = []
        for entry in entries:
            if entry.is_dir():
                result.append(f"{entry}/")
            else:
                result.append(str(entry))
        return result
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as exc:
        return {"error": str(exc)}


for _native_file_tool in (read_file, write_file, str_replace, append_file, list_files):
    bind_workspace_to_tool(_native_file_tool)
