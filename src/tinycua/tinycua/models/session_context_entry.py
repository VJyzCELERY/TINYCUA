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
    content: str | dict | list[dict] = ""
    origin_record_id: str | None = None
    source_node_id: str | None = None
    source_session_id: str | None = None
    created_seq: int = 0

    def __getitem__(self, key: str) -> Any:
        """Support dict-style access for backward compatibility.

        Args:
            key: The field name to access.

        Returns:
            The field value.

        Raises:
            KeyError: If the field doesn't exist.
        """
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for backward compatibility.

        Args:
            key: The field name to check.

        Returns:
            True if the field exists.
        """
        return hasattr(self, key)