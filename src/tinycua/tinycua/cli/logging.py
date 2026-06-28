"""Structured agent log writing for tinycua run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def write_log_entry(
    path: Path,
    event: str,
    level: str,
    data: dict,
) -> None:
    """Append a structured JSON log entry to the agent log file.

    Each entry is a single JSON line with timestamp, event type, level,
    and event-specific payload data. The file is opened in append mode
    so multiple entries accumulate across the run lifecycle.

    Args:
        path: File path for the agent log.
        event: Event type string (e.g., "start", "config", "agent_run",
            "complete", "error", "timeout").
        level: Log level (e.g., "info", "warning", "error").
        data: Event-specific payload dict.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "level": level,
        "data": data,
    }

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
