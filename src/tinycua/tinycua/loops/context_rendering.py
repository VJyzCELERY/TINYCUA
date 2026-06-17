"""LLM-bound context rendering helpers for TinyCUA loops."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


_MAX_CONTEXT_CHARS = 4_000
_INTERNAL_REPR_MARKERS = (
    "DigestedInformation(",
    "AggregatedResult(",
    "TaskResult(",
    "WorkerResult(",
)
_INTERNAL_CONTROL_LINES = {"task_init()"}
_PLANNER_PROSE_MARKERS = (
    "i cannot create files in a physical workspace",
    "copy into your local environment",
    "complete project structure and code",
)
_INTERNAL_PROMPT_ECHO_MARKERS = (
    "based on the external user request above, classify the route",
    "based on the context-enhanced query above, produce focused",
    "based on the digested information and current task state above",
    "based on the digested information above, initialize the root task",
    "based on the current digested information or focused task context above",
    "based on the task tree above, choose concise analysis effort",
    "based on the active task and shallow roadmap above",
    "based on the active task above, perform the required workspace",
    "based on the latest task result and execution evidence above",
    "do not answer the user from this node",
)


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
        return _bound(sanitize_internal_reprs(value), max_chars)
    rendered = json.dumps(
        _context_payload(value),
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return _bound(rendered, max_chars)


def sanitize_internal_reprs(content: str) -> str:
    """Remove echoed Python reprs for internal TinyCUA model objects."""
    clean_lines = []
    for raw_line in content.splitlines():
        if any(marker in raw_line for marker in _INTERNAL_REPR_MARKERS):
            continue
        if raw_line.strip() in _INTERNAL_CONTROL_LINES:
            continue
        if raw_line.strip() in {"</think>", "<think>"}:
            continue
        clean_lines.append(raw_line)
    return "\n".join(clean_lines)


def looks_like_planner_prose(content: str) -> bool:
    """Return whether content is planner/code-dump prose instead of state evidence."""
    lowered = content.lower()
    if looks_like_tool_protocol_payload(content):
        return True
    if looks_like_internal_prompt_echo(content):
        return True
    if any(marker in lowered for marker in _PLANNER_PROSE_MARKERS):
        return True
    return len(content) > 1_500 and "```" in content and "project structure" in lowered


def looks_like_tool_protocol_payload(content: str) -> bool:
    """Return whether content is an internal tool-call protocol payload."""
    stripped = content.strip()
    if '"tool_calls"' in stripped:
        return True
    return "</tool_call>" in stripped or stripped.startswith("<tool_call>")


def looks_like_internal_prompt_echo(content: str) -> bool:
    """Return whether content is an echoed TinyCUA internal prompt."""
    lowered = content.lower()
    return any(marker in lowered for marker in _INTERNAL_PROMPT_ECHO_MARKERS)


def clean_context_enhanced_query(content: str) -> str:
    """Extract the user-facing query from a context-enhanced query echo."""
    text = sanitize_internal_reprs(content).strip()
    marker = "Context Enhanced Query:"
    if marker in text:
        text = text.split(marker, 1)[1].strip()
    for split_marker in (
        "\n\nBased on the context-enhanced query above",
        "\nBased on the context-enhanced query above",
        "Based on the context-enhanced query above",
    ):
        if split_marker in text:
            text = text.split(split_marker, 1)[0].strip()
    return " ".join(text.split())


def _context_payload(value: Any) -> Any:
    type_name = _known_context_type(value)
    if type_name is not None:
        # Render known types as markdown for LLM readability
        md = _render_known_type_markdown(type_name, value)
        if md is not None:
            return md
        return {"type": type_name, "data": _json_safe(_object_data(value))}
    return _json_safe(_object_data(value))


def _render_known_type_markdown(type_name: str, value: Any) -> str | None:
    """Render known model types as readable markdown. Returns None to fall back to JSON."""
    if type_name == "DigestedInformation":
        return _render_digested_information(value)
    if type_name == "AggregatedResult":
        return _render_aggregated_result(value)
    return None


def _render_digested_information(value: Any) -> str:
    """Render DigestedInformation as concise markdown."""
    data = _json_safe(_object_data(value))
    lines = ["## Digested Information"]
    if data.get("context_summary"):
        lines.append(f"**Summary:** {data['context_summary']}")
    if data.get("key_points"):
        lines.append("**Key points:**")
        for point in data["key_points"]:
            lines.append(f"- {point}")
    if data.get("original_query"):
        lines.append(f"**Original query:** {data['original_query']}")
    if data.get("constraints"):
        lines.append("**Constraints:**")
        for c in data["constraints"]:
            lines.append(f"- {c}")
    if data.get("known_gaps"):
        lines.append("**Known gaps:**")
        for g in data["known_gaps"]:
            lines.append(f"- {g}")
    if data.get("advisory_instructions"):
        lines.append("**Advisory:**")
        for a in data["advisory_instructions"]:
            lines.append(f"- {a}")
    return "\n".join(lines)


def _render_aggregated_result(value: Any) -> str:
    """Render AggregatedResult as concise markdown."""
    data = _json_safe(_object_data(value))
    lines = ["## Aggregated Result"]
    if data.get("final_context"):
        lines.append(f"**Context:** {data['final_context']}")
    results = data.get("accepted_results", [])
    if results:
        lines.append("**Accepted results:**")
        for r in results:
            if isinstance(r, dict):
                lines.append(f"- {r.get('task_id', '?')}: {r.get('content', r.get('summary', ''))[:100]}")
    return "\n".join(lines)


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
