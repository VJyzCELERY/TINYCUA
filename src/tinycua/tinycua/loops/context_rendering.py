"""LLM-bound context rendering helpers for TinyCUA loops."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


_MAX_CONTEXT_CHARS = 4_000


def should_include_chat_record(record: Any) -> bool:
    """Return whether a durable chat record is safe to resend to the LLM."""
    if getattr(record, "record_type", None) == "retry":
        return False
    if getattr(record, "visibility", "user_visible") in {"internal", "tool_only"}:
        return False
    return True


def render_llm_content(value: Any, *, max_chars: int = _MAX_CONTEXT_CHARS) -> str:
    """Render internal values as compact, bounded LLM-safe text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return _bound(value, max_chars)
    rendered = json.dumps(
        _context_payload(value),
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _bound(rendered, max_chars)


def _context_payload(value: Any) -> Any:
    type_name = _known_context_type(value)
    if type_name is not None:
        return {"type": type_name, "data": _json_safe(_object_data(value))}
    return _json_safe(_object_data(value))


def _known_context_type(value: Any) -> str | None:
    module_name = type(value).__module__
    type_name = type(value).__name__
    if module_name.startswith("tinycua.models") and type_name in {
        "AggregatedResult",
        "DigestedInformation",
        "Task",
        "TaskResult",
        "WorkerResult",
    }:
        return type_name
    return None


def _object_data(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if hasattr(value, "snapshot") and callable(value.snapshot):
        return value.snapshot()
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _bound(content: str, max_chars: int) -> str:
    if len(content) <= max_chars:
        return content
    return f"{content[:max_chars]}…[truncated]"
