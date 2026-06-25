"""SessionContextEntry model for mutable LLM-reusable context with segment metadata."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from tinycua.models.state_object import StateObject


@dataclass
class SessionContextEntry(StateObject):
    """Session context record with segment metadata.

    Attributes:
        record_id: Unique identifier for this entry.
        segment: Segment type (prior, input, output).
        content: The context content.
        origin_record_id: ID of the original record for deduplication.
        source_node_id: ID of the node that produced this entry.
        source_session_id: ID of the session that produced this entry.
        created_seq: Sequence number for ordering.
    """

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    segment: Literal["prior", "input", "output"] = "prior"
    content: Any = ""
    origin_record_id: str | None = None
    source_node_id: str | None = None
    source_session_id: str | None = None
    created_seq: int = 0
    forwarded_to_node_ids: set[str] = field(default_factory=set)

    @property
    def role(self) -> str:
        """Role property.

        Returns 'user' for prior/input segments, 'assistant' for output segments.
        """
        if self.segment == "output":
            return "assistant"
        return "user"


def entry_content(entry: Any) -> Any:
    """Return the content of a SessionContextEntry or dict-shaped entry.

    The codebase handles both ``SessionContextEntry`` dataclass instances and
    legacy ``dict`` entries (e.g. from snapshots / serialised state). This
    helper centralises the dict-or-attr coercion so callers don't repeat the
    ``entry.get("content") if isinstance(entry, dict) else entry.content``
    pattern at every read site.
    """
    if isinstance(entry, dict):
        return entry.get("content")
    return entry.content


def append_output_entry(
    session: Any,
    content: Any,
    source_node_id: str,
    *,
    idempotent_by_identity: bool = False,
) -> None:
    """Append a ``segment="output"`` SessionContextEntry to ``session.session_context``.

    Centralises the repeated "record this node's output into the session
    context" pattern. When ``idempotent_by_identity`` is True, skips the
    append if an existing output entry holds the exact same content object
    (identity check) — used by digester/worker to avoid double-recording the
    same digest across propagation passes.
    """
    if idempotent_by_identity:
        for entry in session.session_context:
            if getattr(entry, "segment", None) == "output" and entry.content is content:
                return
    session.session_context.append(
        SessionContextEntry(
            content=content,
            segment="output",
            source_node_id=source_node_id,
            source_session_id=session.session_id,
        )
    )
