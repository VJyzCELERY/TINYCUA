"""Shared transcript parsing for all WildClawBench agent harnesses."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_transcript(transcript_path: Path) -> dict[str, Any]:
    """Parse a transcript JSONL file and extract usage statistics.

    Args:
        transcript_path: Path to transcript.jsonl.

    Returns:
        Dict with keys: requests, total_tokens.
    """
    if not transcript_path.exists():
        return {"requests": 0, "total_tokens": None}

    requests = 0
    total_tokens = 0

    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                event_type = event.get("type", "")

                if "llm" in event_type or "response" in event_type:
                    requests += 1

                usage = event.get("usage", {})
                tokens = usage.get("total_tokens")
                if isinstance(tokens, (int, float)):
                    total_tokens += int(tokens)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to parse transcript %s: %s", transcript_path, exc)
        return {"requests": 0, "total_tokens": None}

    return {
        "requests": requests,
        "total_tokens": total_tokens if total_tokens > 0 else None,
    }
