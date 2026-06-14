"""Unit tests for transcript conversion helpers."""

from __future__ import annotations

import json
from pathlib import Path

from tinycua.cli.transcript import (
    _build_content_blocks,
    _usage_int,
    convert_working_messages_to_openclaw,
    write_openclaw_jsonl,
    write_usage_summary,
)


# --- _usage_int tests ---


class TestUsageInt:
    """Tests for _usage_int helper."""

    def test_none_returns_zero(self) -> None:
        """None input returns 0."""
        assert _usage_int(None) == 0

    def test_valid_int_preserved(self) -> None:
        """Valid integer is returned unchanged."""
        assert _usage_int(42) == 42

    def test_zero_preserved(self) -> None:
        """Zero is returned as 0."""
        assert _usage_int(0) == 0

    def test_negative_returns_zero(self) -> None:
        """Negative integers are clamped to 0."""
        assert _usage_int(-5) == 0

    def test_bool_returns_zero(self) -> None:
        """Booleans are coerced to 0, not 1."""
        assert _usage_int(True) == 0
        assert _usage_int(False) == 0

    def test_string_returns_zero(self) -> None:
        """Non-numeric strings return 0."""
        assert _usage_int("abc") == 0

    def test_float_returns_zero(self) -> None:
        """Floats return 0 (not truncated)."""
        assert _usage_int(3.14) == 0

    def test_numeric_string_returns_zero(self) -> None:
        """String numbers return 0 (strict int check)."""
        assert _usage_int("42") == 0


# --- _build_content_blocks tests ---


class TestBuildContentBlocks:
    """Tests for _build_content_blocks helper."""

    def test_no_tool_calls_returns_string(self) -> None:
        """No tool calls returns plain string content."""
        entry = {"role": "assistant", "content": "Hello"}
        result = _build_content_blocks(entry, [])
        assert isinstance(result, str)
        assert result == "Hello"

    def test_with_tool_calls_returns_list(self) -> None:
        """With tool calls returns list of content blocks."""
        entry = {
            "role": "assistant",
            "content": "I'll write that file.",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "/tmp/test.txt"}',
                    },
                }
            ],
        }
        result = _build_content_blocks(entry, entry["tool_calls"])
        assert isinstance(result, list)
        assert len(result) == 2
        # First block is text
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "I'll write that file."
        # Second block is tool_use
        assert result[1]["type"] == "tool_use"
        assert result[1]["id"] == "call_123"
        assert result[1]["name"] == "write_file"
        assert result[1]["input"] == {"path": "/tmp/test.txt"}

    def test_tool_calls_arguments_decoded(self) -> None:
        """Tool call arguments JSON string is decoded to dict."""
        entry = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_456",
                    "type": "function",
                    "function": {
                        "name": "search",
                        "arguments": '{"query": "test", "limit": 5}',
                    },
                }
            ],
        }
        result = _build_content_blocks(entry, entry["tool_calls"])
        assert result[1]["input"] == {"query": "test", "limit": 5}

    def test_empty_content_with_tool_calls(self) -> None:
        """Empty content with tool calls still produces text block."""
        entry = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_789",
                    "type": "function",
                    "function": {
                        "name": "do_something",
                        "arguments": "{}",
                    },
                }
            ],
        }
        result = _build_content_blocks(entry, entry["tool_calls"])
        assert isinstance(result, list)
        assert result[0]["type"] == "text"
        assert result[0]["text"] == ""


# --- convert_working_messages_to_openclaw tests ---


class TestConvertWorkingMessages:
    """Tests for convert_working_messages_to_openclaw."""

    def test_system_messages_skipped(self) -> None:
        """System messages are excluded from output."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]
        records = convert_working_messages_to_openclaw(messages)
        assert len(records) == 1
        assert records[0]["type"] == "message"
        assert records[0]["message"]["role"] == "user"

    def test_user_message_converted(self) -> None:
        """User messages are mapped to OpenClaw message records."""
        messages = [{"role": "user", "content": "Hello"}]
        records = convert_working_messages_to_openclaw(messages)
        assert len(records) == 1
        assert records[0]["type"] == "message"
        assert records[0]["message"]["role"] == "user"
        assert records[0]["message"]["content"] == "Hello"

    def test_assistant_message_without_tools(self) -> None:
        """Assistant message without tool calls is a simple message record."""
        messages = [{"role": "assistant", "content": "Sure!"}]
        records = convert_working_messages_to_openclaw(messages)
        assert len(records) == 1
        assert records[0]["type"] == "message"
        assert records[0]["message"]["role"] == "assistant"
        assert records[0]["message"]["content"] == "Sure!"

    def test_assistant_message_with_tool_calls(self) -> None:
        """Assistant message with tool calls has content blocks."""
        messages = [
            {
                "role": "assistant",
                "content": "Calling tool",
                "tool_calls": [
                    {
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "my_tool",
                            "arguments": '{"key": "val"}',
                        },
                    }
                ],
            }
        ]
        records = convert_working_messages_to_openclaw(messages)
        assert len(records) == 1
        assert records[0]["type"] == "message"
        content = records[0]["message"]["content"]
        assert isinstance(content, list)
        tool_blocks = [b for b in content if b["type"] == "tool_use"]
        assert len(tool_blocks) == 1
        assert tool_blocks[0]["id"] == "call_abc"

    def test_tool_result_message(self) -> None:
        """Tool result messages are mapped to toolResult records."""
        messages = [
            {"role": "tool_result", "call_id": "call_abc", "content": "Done"}
        ]
        records = convert_working_messages_to_openclaw(messages)
        assert len(records) == 1
        assert records[0]["type"] == "toolResult"
        assert records[0]["toolResult"]["callId"] == "call_abc"
        assert records[0]["toolResult"]["tool_call_id"] == "call_abc"
        assert records[0]["toolResult"]["content"] == "Done"

    def test_per_message_usage_attached(self) -> None:
        """Per-message usage is attached to assistant message records."""
        messages = [{"role": "assistant", "content": "Hello"}]
        usage = [{"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}]
        records = convert_working_messages_to_openclaw(
            messages, per_message_usage=usage
        )
        assert records[0]["usage"] == usage[0]

    def test_empty_messages_returns_empty_list(self) -> None:
        """Empty message list returns empty records."""
        records = convert_working_messages_to_openclaw([])
        assert records == []


# --- write_openclaw_jsonl tests ---


class TestWriteOpenClawJsonl:
    """Tests for write_openclaw_jsonl."""

    def test_writes_jsonl(self, tmp_path: Path) -> None:
        """Records are written as JSONL."""
        records = [
            {"type": "message", "message": {"role": "user", "content": "Hi"}}
        ]
        path = tmp_path / "transcript.jsonl"
        write_openclaw_jsonl(records, path)
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["type"] == "message"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Parent directories are created if needed."""
        records = [{"type": "message", "message": {"role": "user", "content": "Hi"}}]
        path = tmp_path / "subdir" / "deep" / "transcript.jsonl"
        write_openclaw_jsonl(records, path)
        assert path.exists()

    def test_empty_records_writes_empty_file(self, tmp_path: Path) -> None:
        """Empty records list writes an empty file."""
        path = tmp_path / "transcript.jsonl"
        write_openclaw_jsonl([], path)
        assert path.read_text() == ""


# --- write_usage_summary tests ---


class TestWriteUsageSummary:
    """Tests for write_usage_summary."""

    def test_aggregates_usage_events(self, tmp_path: Path) -> None:
        """Usage events are aggregated correctly."""
        events = [
            {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            {"input_tokens": 200, "output_tokens": 80, "total_tokens": 280},
        ]
        path = tmp_path / "usage.json"
        write_usage_summary(path, events, elapsed_time=10.0)
        data = json.loads(path.read_text())
        assert data["input_tokens"] == 300
        assert data["output_tokens"] == 130
        assert data["total_tokens"] == 430
        assert data["request_count"] == 2
        assert data["elapsed_time"] == 10.0

    def test_zero_filled_when_no_events(self, tmp_path: Path) -> None:
        """No events produce zero-filled usage.json."""
        path = tmp_path / "usage.json"
        write_usage_summary(path, [], elapsed_time=0.0)
        data = json.loads(path.read_text())
        assert data["input_tokens"] == 0
        assert data["output_tokens"] == 0
        assert data["total_tokens"] == 0
        assert data["cache_read_tokens"] == 0
        assert data["cache_write_tokens"] == 0
        assert data["cost_usd"] == 0.0
        assert data["request_count"] == 0
        assert data["elapsed_time"] == 0.0

    def test_handles_none_token_values(self, tmp_path: Path) -> None:
        """None token values are treated as 0."""
        events = [
            {"input_tokens": None, "output_tokens": None, "total_tokens": None}
        ]
        path = tmp_path / "usage.json"
        write_usage_summary(path, events, elapsed_time=1.0)
        data = json.loads(path.read_text())
        assert data["input_tokens"] == 0
        assert data["output_tokens"] == 0
        assert data["total_tokens"] == 0

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Parent directories are created if needed."""
        path = tmp_path / "subdir" / "usage.json"
        write_usage_summary(path, [], elapsed_time=0.0)
        assert path.exists()
