"""Transcript capture and JSONL writing for tinycua run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _usage_int(value: Any) -> int:
    """Coerce a nullable token count to a non-negative integer.

    Prevents ``null`` in JSON output. Booleans are coerced to 0 (not 1)
    since they are not valid token counts.

    Args:
        value: The value to coerce (int, None, bool, or other).

    Returns:
        Non-negative integer token count.
    """
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _build_content_blocks(
    entry: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> str | list[dict[str, Any]]:
    """Build the content field for an assistant message record.

    When tool calls are present, returns a list of content blocks
    (text + tool_use). Otherwise returns the plain string content.

    Args:
        entry: The original assistant message dict.
        tool_calls: List of tool call dicts from the message.

    Returns:
        Plain string content or list of content block dicts.
    """
    if not tool_calls:
        return entry.get("content", "")

    blocks: list[dict[str, Any]] = []
    # Text block
    blocks.append({
        "type": "text",
        "text": entry.get("content", ""),
    })
    # Tool use blocks
    for tc in tool_calls:
        func = tc.get("function", {})
        # Decode arguments from JSON string to dict
        raw_args = func.get("arguments", "{}")
        try:
            input_data = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except (json.JSONDecodeError, TypeError):
            input_data = {}
        blocks.append({
            "type": "tool_use",
            "id": tc.get("id", ""),
            "name": func.get("name", ""),
            "input": input_data,
        })
    return blocks


def convert_working_messages_to_openclaw(
    working_messages: list[dict[str, Any]],
    per_message_usage: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Convert BaseLoop working messages to OpenClaw-compatible JSONL records.

    Skips system messages. Maps user/assistant messages to ``{"type": "message"}``
    records and tool_result messages to ``{"type": "toolResult"}`` records.

    Args:
        working_messages: List of message dicts from BaseLoop._working_messages.
        per_message_usage: Optional list of per-response usage dicts. When
            provided, usage is attached to assistant message records in order.

    Returns:
        List of OpenClaw-compatible record dicts.
    """
    records: list[dict[str, Any]] = []
    usage_idx = 0
    usage_list = per_message_usage or []

    for msg in working_messages:
        role = msg.get("role", "")

        # Skip system messages
        if role == "system":
            continue

        # Tool result messages -> toolResult records
        if role == "tool_result":
            call_id = msg.get("call_id", "")
            records.append({
                "type": "toolResult",
                "toolResult": {
                    "callId": call_id,
                    "tool_call_id": call_id,
                    "content": msg.get("content", ""),
                },
            })
            continue

        # Assistant messages with tool calls -> content blocks
        if role == "assistant" and "tool_calls" in msg:
            tool_calls = msg.get("tool_calls", [])
            content = _build_content_blocks(msg, tool_calls)
            record: dict[str, Any] = {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": content,
                },
            }
            # Attach per-message usage if available
            if usage_idx < len(usage_list):
                record["message"]["usage"] = usage_list[usage_idx]
                usage_idx += 1
            records.append(record)
            continue

        # Standard messages (user, assistant without tool calls)
        record = {
            "type": "message",
            "message": {
                "role": role,
                "content": msg.get("content", ""),
            },
        }
        # Attach per-message usage for assistant messages
        if role == "assistant" and usage_idx < len(usage_list):
            record["message"]["usage"] = usage_list[usage_idx]
            usage_idx += 1
        records.append(record)

    return records


def write_openclaw_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    """Write OpenClaw-compatible records to a JSONL file.

    Creates parent directories if needed.

    Args:
        records: List of OpenClaw record dicts.
        path: File path for the JSONL output.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_usage_summary(
    path: Path,
    usage_events: list[dict[str, Any]],
    elapsed_time: float,
) -> None:
    """Aggregate per-response usage events and write usage.json.

    Produces a zero-filled summary when no events are provided (never ``{}``).

    Args:
        path: File path for the usage JSON output.
        usage_events: List of per-response usage dicts with token counts.
        elapsed_time: Total elapsed time in seconds.
    """
    total_input = 0
    total_output = 0
    total_tokens = 0
    cache_read = 0
    cache_write = 0

    for event in usage_events:
        total_input += _usage_int(event.get("input_tokens"))
        total_output += _usage_int(event.get("output_tokens"))
        total_tokens += _usage_int(event.get("total_tokens"))
        cache_read += _usage_int(event.get("cache_read_tokens"))
        cache_write += _usage_int(event.get("cache_write_tokens"))

    summary = {
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "total_tokens": total_tokens,
        "cost_usd": 0.0,
        "request_count": len(usage_events),
        "elapsed_time": elapsed_time,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")


def write_transcript(messages: list[dict], path: Path) -> None:
    """Write conversation messages to an OpenClaw-compatible JSONL file.

    Each line is a JSON object containing the message fields (role, content, etc.).
    The output directory is created if it doesn't exist.

    Args:
        messages: List of message dicts with at least "role" and "content" keys.
        path: File path for the JSONL transcript output.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for msg in messages:
            record = {"type": "message", "message": msg}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
