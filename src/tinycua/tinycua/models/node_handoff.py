"""Generic explicit handoff between TinyCUA nodes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

_MAX_PAYLOAD_CHARS = 4_000


@dataclass
class NodeHandoff:
    """Generic inter-node handoff envelope.

    Node-specific meaning belongs in ``payload``; the base envelope stays
    neutral so every node can use it.
    """

    source_node: str
    target_node: str | None
    instruction: str
    payload: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> dict[str, str]:
        """Render the handoff as one assistant-role LLM message."""
        return {"role": "assistant", "content": render_handoff_markdown(self)}

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary representation."""
        return {
            "source_node": self.source_node,
            "target_node": self.target_node,
            "instruction": self.instruction,
            "payload": _json_safe(self.payload),
            "constraints": list(self.constraints),
            "metadata": _json_safe(self.metadata),
        }


def render_handoff_markdown(handoff: NodeHandoff) -> str:
    """Render a generic handoff as natural working context."""
    payload = _render_payload(handoff.payload)
    lines = [
        "## Relevant context",
        handoff.instruction,
    ]
    if payload:
        lines.extend(["", payload])
    if handoff.constraints:
        lines.extend(["", "Constraints:"])
        lines.extend(f"- {item}" for item in handoff.constraints)
    return "\n".join(lines)


def _render_payload(payload: dict[str, Any]) -> str:
    digest = payload.get("digested_information")
    if digest is not None:
        return _render_digest(digest)
    if not payload:
        return ""
    rendered = json.dumps(
        _json_safe(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return rendered if len(rendered) <= _MAX_PAYLOAD_CHARS else f"{rendered[:_MAX_PAYLOAD_CHARS]}…[truncated]"


def _render_digest(digest: Any) -> str:
    original = str(getattr(digest, "original_query", "") or "").strip()
    summary = str(getattr(digest, "context_summary", "") or "").strip()
    lines = ["Request brief:"]
    if original:
        lines.append(f"- User request: {original}")
    if summary and summary != original:
        lines.append(f"- Summary: {summary}")
    for label, attr in (
        ("Important details", "key_points"),
        ("Guidance", "advisory_instructions"),
        ("Constraints", "constraints"),
        ("Open questions", "known_gaps"),
    ):
        values = getattr(digest, attr, None) or []
        if values:
            lines.append(f"- {label}:")
            lines.extend(f"  - {item}" for item in values)
    return "\n".join(lines) if len(lines) > 1 else ""


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
