"""Transcript capture and JSONL writing for tinycua run."""

from __future__ import annotations

import json
from pathlib import Path


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
