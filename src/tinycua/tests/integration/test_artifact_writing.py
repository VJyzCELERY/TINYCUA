"""Integration tests for transcript, usage, and log artifact writing."""

from __future__ import annotations

import json
from pathlib import Path

from tinycua.cli.transcript import (
    _usage_int,
    convert_working_messages_to_openclaw,
    write_openclaw_jsonl,
    write_usage_summary,
)


def test_end_to_end_transcript_writing(tmp_path: Path) -> None:
    """Agent working messages produce a parseable OpenClaw-compatible transcript.jsonl."""
    # Arrange
    working_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a file."},
        {
            "role": "assistant",
            "content": "I'll write that file.",
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "/tmp/test.txt", "content": "hello"}',
                    },
                }
            ],
        },
        {"role": "tool_result", "call_id": "call_abc123", "content": "File written."},
        {"role": "assistant", "content": "Done."},
    ]
    transcript_path = tmp_path / "transcript.jsonl"

    # Act
    records = convert_working_messages_to_openclaw(working_messages)
    write_openclaw_jsonl(records, transcript_path)

    # Assert
    lines = transcript_path.read_text().strip().split("\n")
    parsed = [json.loads(line) for line in lines]
    # System messages excluded
    assert all(r["type"] in ("message", "toolResult") for r in parsed)
    # tool_use blocks preserved
    assistant_with_tools = [
        r
        for r in parsed
        if r["type"] == "message"
        and r["message"]["role"] == "assistant"
        and isinstance(r["message"]["content"], list)
    ]
    assert len(assistant_with_tools) == 1
    tool_blocks = [
        b
        for b in assistant_with_tools[0]["message"]["content"]
        if b["type"] == "tool_use"
    ]
    assert len(tool_blocks) == 1
    assert tool_blocks[0]["id"] == "call_abc123"
    assert tool_blocks[0]["input"]["path"] == "/tmp/test.txt"
    # toolResult record present
    tool_results = [r for r in parsed if r["type"] == "toolResult"]
    assert len(tool_results) == 1
    assert tool_results[0]["toolResult"]["callId"] == "call_abc123"
    assert tool_results[0]["toolResult"]["tool_call_id"] == "call_abc123"


def test_end_to_end_usage_writing(tmp_path: Path) -> None:
    """Usage summary is written to usage.json with correct fields."""
    # Arrange
    usage_events = [
        {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        {"input_tokens": 200, "output_tokens": 80, "total_tokens": 280},
    ]
    usage_path = tmp_path / "usage.json"

    # Act
    write_usage_summary(usage_path, usage_events, elapsed_time=12.5)

    # Assert
    data = json.loads(usage_path.read_text())
    assert data["input_tokens"] == 300
    assert data["output_tokens"] == 130
    assert data["total_tokens"] == 430
    assert data["cache_read_tokens"] == 0
    assert data["cache_write_tokens"] == 0
    assert data["cost_usd"] == 0.0
    assert data["request_count"] == 2
    assert data["elapsed_time"] == 12.5


def test_usage_summary_zero_filled_fallback(tmp_path: Path) -> None:
    """Empty usage events produce zero-filled usage.json, never {}."""
    # Arrange
    usage_path = tmp_path / "usage.json"

    # Act
    write_usage_summary(usage_path, [], elapsed_time=0.0)

    # Assert
    data = json.loads(usage_path.read_text())
    assert data["input_tokens"] == 0
    assert data["output_tokens"] == 0
    assert data["total_tokens"] == 0
    assert data["request_count"] == 0
    assert data["elapsed_time"] == 0.0


def test_usage_int_bool_returns_zero() -> None:
    """_usage_int() coerces booleans to 0, not 1."""
    assert _usage_int(True) == 0
    assert _usage_int(False) == 0
