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
