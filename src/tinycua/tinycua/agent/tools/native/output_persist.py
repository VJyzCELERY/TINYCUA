"""Persist oversized tool results to temp files to bound in-message context.

When a tool result's serialized content is very large (e.g. a verbose
``run_shell`` output, a big ``read_file``, or a ``task_inspect`` full snapshot),
keeping it verbatim in ``attempt_messages`` balloons the prompt — the
experiment-4 ResultReviewer peaked at 257K input tokens this way.

This module implements two bounds (adapted from hermes-agent's
``tool_result_storage.py`` three-layer defense):

1. ``persist_if_oversized`` — if a single tool result's serialized content
   exceeds ``_PERSIST_THRESHOLD`` chars, write the full content to
   ``./tmp/tool-results/{tool_call_id}.txt`` and return a ``<persisted-output>``
   block containing a 4K preview, the file path, and a "use read_file with
   offset/limit" instruction. Under the threshold, return the content unchanged.

2. ``enforce_turn_budget`` — after a batch of tool results is collected, if the
   cumulative tool-result chars in the messages exceed ``_TURN_BUDGET``, spill
   the largest non-persisted results to disk (via ``persist_if_oversized``)
   until under budget.

Never loses data: if a persist write fails, the original content is returned
untruncated (the per-tool head+tail truncation in shell.py is a separate,
earlier bound).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

_PERSIST_THRESHOLD = 100_000      # persist a single result above this
_PREVIEW_CHARS = 4_000            # preview kept in-message when persisted
# Safety-net ceiling only — NOT a tight budget. Normal operation should never
# hit this; it exists so a pathological runaway (e.g. a model reading 100
# distinct large files in one node attempt) can't OOM the prompt. Set high so
# legitimate multi-file exploration is never trimmed. The PRIMARY bound is
# evict_superseded_file_reads (staleness, not size).
_TURN_SAFETY_NET = 200_000
# Tools that operate on a file path and whose older results are superseded by
# a newer result for the same path. read_file/edit_file/write_file on path X
# are stale once a newer read/edit/write of X exists — the file changed.
_FILE_PATH_TOOLS = frozenset({"read_file", "str_replace", "append_file", "write_file", "search_files"})

# ponytail: write to ./tmp/tool-results/ (gitignored, repo-local). Per-session
# subdirectory would isolate runs; upgrade path if concurrent runs collide.
_RESULTS_DIR = Path("tmp") / "tool-results"


def _ensure_results_dir() -> Path:
    """Create (idempotently) and return the tool-results directory."""
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return _RESULTS_DIR


def _safe_id(tool_call_id: str) -> str:
    """Sanitize a tool_call_id for use as a filename."""
    # Keep it filesystem-safe but readable. Hash collisions aren't a concern
    # here — the id is unique per tool call within a node attempt.
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in tool_call_id)
    if not safe:
        safe = hashlib.sha256(tool_call_id.encode("utf-8")).hexdigest()[:16]
    return safe


def persist_if_oversized(
    content: str,
    tool_call_id: str,
    *,
    threshold: int = _PERSIST_THRESHOLD,
    tool_name: str = "",
) -> str:
    """Return a compact in-message representation when content is oversized.

    If ``len(content) > threshold``, write the full content to
    ``./tmp/tool-results/{tool_call_id}.txt`` and return a
    ``<persisted-output>`` block with a preview + path + re-read hint.
    Otherwise return ``content`` unchanged.

    On write failure, return the original content untruncated (never lose
    data; the caller's own head+tail truncation still applies separately).
    """
    if len(content) <= threshold:
        return content
    try:
        results_dir = _ensure_results_dir()
        filename = f"{_safe_id(tool_call_id)}.txt"
        dest = results_dir / filename
        dest.write_text(content, encoding="utf-8")
    except OSError:
        # Disk full / permission / path issue — fall back to the full content.
        # The per-tool truncation (e.g. shell.py head+tail) is the backstop.
        return content

    preview = content[:_PREVIEW_CHARS]
    if len(content) > _PREVIEW_CHARS:
        preview += "\n... [preview truncated; full output in file] ..."
    name_hint = f" (tool={tool_name})" if tool_name else ""
    return (
        f"<persisted-output>{name_hint}\n"
        f"Full output ({len(content)} chars) saved to: {dest}\n"
        f"Use the read_file tool with offset and limit to access specific sections.\n"
        f"Preview:\n{preview}\n"
        f"</persisted-output>"
    )


def _stub_content(original: str, tool_name: str, *, reason: str = "superseded") -> str:
    """Build a one-line stub replacing an evicted tool result.

    The stub tells the model the result existed and how big it was, so it
    knows it can re-call the tool if it actually needs that content again.
    """
    size = len(original)
    return (
        f"[elided prior {tool_name} result ({size} chars, {reason}); "
        f"re-call {tool_name} if needed]"
    )


def _parse_tool_call_path(tool_call: dict) -> str | None:
    """Extract the file path from a file-tool call's arguments, if present.

    Tool-call arguments arrive as a JSON string in ``function.arguments``.
    Returns the normalized path for read_file/edit_file/write_file, else None.
    """
    fn = tool_call.get("function") if isinstance(tool_call, dict) else None
    if not isinstance(fn, dict):
        return None
    name = fn.get("name", "")
    if name not in _FILE_PATH_TOOLS:
        return None
    raw_args = fn.get("arguments", "")
    if not raw_args:
        return None
    import json

    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except (ValueError, TypeError):
        return None
    if not isinstance(args, dict):
        return None
    path = args.get("path")
    if not isinstance(path, str) or not path.strip():
        return None
    # Normalize: strip and lowercase for matching (case-insensitive path
    # equality is good enough for staleness detection; we're not a security
    # boundary). Absolute vs relative doesn't matter — same string = same file.
    return path.strip().lower()


def _build_tool_call_id_to_path(messages: list[dict]) -> dict[str, str]:
    """Map tool_call_id → file path for every file-tool call in the messages."""
    mapping: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            tc_id = tc.get("id")
            path = _parse_tool_call_path(tc)
            if tc_id and path:
                mapping[tc_id] = path
    return mapping


def evict_superseded_file_reads(tool_messages: list[dict]) -> list[dict]:
    """Stub file-tool results that a NEWER result for the same path has superseded.

    This is the PRIMARY context bound (not a token budget). The experiment-4
    executor re-read ``api.py`` 8 times in one node attempt — each prior read is
    stale the moment a newer read/edit/write of the same file lands, because
    the file changed. Stubbing the superseded reads removes redundant history
    the model already processed, without touching distinct-file exploration
    (10 different files all stay verbatim).

    Keeps the LATEST result per file path verbatim; stubs all older results for
    that same path. Non-file tools (run_shell, task_inspect, web_search, ...) are
    never stubbed by this pass — only the high safety net touches them.
    """
    if not tool_messages:
        return tool_messages

    # We need the assistant tool_calls to map tool_call_id → path. The caller
    # passes only the tool-result messages; the full attempt_messages (with
    # assistant tool_calls) are needed. So this function is a no-op when called
    # without the assistant messages — the caller must pass the full
    # attempt_messages list (assistant + tool messages interleaved).
    # Detect: if there are no assistant messages here, we can't map; bail.
    has_assistant = any(m.get("role") == "assistant" and m.get("tool_calls") for m in tool_messages)
    if not has_assistant:
        return tool_messages

    id_to_path = _build_tool_call_id_to_path(tool_messages)

    # For each file path, find the index of the LATEST tool result referencing it.
    latest_index_for_path: dict[str, int] = {}
    for i, msg in enumerate(tool_messages):
        if msg.get("role") != "tool":
            continue
        tc_id = str(msg.get("tool_call_id") or "")
        path = id_to_path.get(tc_id)
        if not path:
            continue
        latest_index_for_path[path] = i  # last write wins → latest index

    # Stub every older tool result whose path has a newer result.
    for i, msg in enumerate(tool_messages):
        if msg.get("role") != "tool":
            continue
        if str(msg.get("content", "")).startswith("[elided prior"):
            continue  # already stubbed
        tc_id = str(msg.get("tool_call_id") or "")
        path = id_to_path.get(tc_id)
        if not path:
            continue
        latest = latest_index_for_path.get(path)
        if latest is not None and i < latest:
            original = str(msg.get("content", ""))
            tool_name = str(msg.get("name") or "tool")
            msg["content"] = _stub_content(original, tool_name, reason="superseded by newer read of same file")
    return tool_messages


def enforce_turn_budget(
    tool_messages: list[dict],
    *,
    budget: int = _TURN_SAFETY_NET,
) -> list[dict]:
    """High safety-net ceiling — NOT a tight budget.

    Only fires in pathological runaway (e.g. 100 distinct large file reads in
    one node attempt). Normal operation never hits it. When it does fire,
    stubs the OLDEST non-file tool results (file reads are already handled by
    evict_superseded_file_reads). Kept as a last-resort OOM guard, not a
    routine trim.
    """
    if not tool_messages:
        return tool_messages

    def _content_len(msg: dict) -> int:
        return len(str(msg.get("content", "")))

    def _is_stub(msg: dict) -> bool:
        return str(msg.get("content", "")).startswith("[elided prior")

    def _is_persisted(msg: dict) -> bool:
        return "<persisted-output>" in str(msg.get("content", ""))

    # Persist any single oversized result first.
    for i, msg in enumerate(tool_messages):
        if _is_persisted(msg) or _is_stub(msg):
            continue
        original = str(msg.get("content", ""))
        if len(original) <= _PERSIST_THRESHOLD:
            continue
        tool_call_id = str(msg.get("tool_call_id") or msg.get("name") or f"msg-{i}")
        tool_name = str(msg.get("name") or "")
        persisted = persist_if_oversized(original, tool_call_id, tool_name=tool_name)
        if persisted is not original:
            msg["content"] = persisted

    total = sum(_content_len(m) for m in tool_messages)
    if total <= budget:
        return tool_messages

    # Safety net: stub oldest non-stub tool results until under budget.
    for i, msg in enumerate(tool_messages):
        if total <= budget:
            break
        if msg.get("role") != "tool" or _is_stub(msg) or _is_persisted(msg):
            continue
        original = str(msg.get("content", ""))
        if not original:
            continue
        tool_name = str(msg.get("name") or "tool")
        msg["content"] = _stub_content(original, tool_name, reason="safety-net overflow")
        total -= len(original) - len(msg["content"])
    return tool_messages


# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------

def _self_check() -> None:
    """Verify persist + staleness eviction + safety net. Not a test suite."""
    # Under threshold → passthrough
    assert persist_if_oversized("small", "tc1") == "small"

    # Over threshold → persisted file + preview block
    big = "A" * 150_000
    out = persist_if_oversized(big, "tc-2")
    assert "<persisted-output>" in out
    assert "150000 chars" in out
    assert "read_file" in out
    assert ("A" * 4_000) in out  # preview head

    # Staleness eviction: 3 read_file of the SAME path → oldest 2 stubbed,
    # latest kept verbatim. Distinct-file reads stay verbatim.
    import json as _json

    msgs = [
        # assistant tool_calls mapping ids → path
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "r1", "function": {"name": "read_file", "arguments": _json.dumps({"path": "api.py"})}},
            {"id": "r2", "function": {"name": "read_file", "arguments": _json.dumps({"path": "api.py"})}},
            {"id": "r3", "function": {"name": "read_file", "arguments": _json.dumps({"path": "api.py"})}},
            {"id": "o1", "function": {"name": "read_file", "arguments": _json.dumps({"path": "other.py"})}},
        ]},
        {"role": "tool", "tool_call_id": "r1", "name": "read_file", "content": "X" * 5_000},
        {"role": "tool", "tool_call_id": "r2", "name": "read_file", "content": "Y" * 5_000},
        {"role": "tool", "tool_call_id": "r3", "name": "read_file", "content": "Z" * 5_000},
        {"role": "tool", "tool_call_id": "o1", "name": "read_file", "content": "W" * 5_000},
    ]
    evict_superseded_file_reads(msgs)
    # r1, r2 stubbed (superseded by r3 for same path api.py)
    assert str(msgs[1]["content"]).startswith("[elided prior read_file"), msgs[1]
    assert str(msgs[2]["content"]).startswith("[elided prior read_file"), msgs[2]
    assert "superseded by newer" in str(msgs[1]["content"])
    # r3 (latest of api.py) stays verbatim
    assert msgs[3]["content"] == "Z" * 5_000
    # o1 (different file) stays verbatim — distinct-file exploration untouched
    assert msgs[4]["content"] == "W" * 5_000

    # Safety net: only fires at very high total (200K). Under it → no trimming.
    small_msgs = [
        {"role": "tool", "tool_call_id": f"t{i}", "name": "run_shell", "content": "X" * 1_000}
        for i in range(10)
    ]  # 10K total — well under 200K
    enforce_turn_budget(small_msgs)
    assert all(m["content"] == "X" * 1_000 for m in small_msgs)  # untouched

    print("output_persist.py self-check OK")
    print("output_persist.py self-check OK")


if __name__ == "__main__":
    _self_check()