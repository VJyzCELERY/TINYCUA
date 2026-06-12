"""ChatRecord model for append-only durable audit transcript."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from tinycua.models.state_object import StateObject


@dataclass
class ChatRecord(StateObject):
    """Append-only durable audit transcript recording node I/O provenance.

    Attributes:
        record_id: Unique identifier for this record.
        role: Role of the message (user, assistant, system, tool).
        record_type: Type of record (node_output, propagation, tool_result, etc.).
        content: The message content.
        visibility: Visibility level (user_visible, internal, tool_only).
        source_node_id: ID of the node that produced this record.
        source_session_id: ID of the session that produced this record.
        receiver_node_id: ID of the node that received this record.
        receiver_session_id: ID of the session that received this record.
        origin_record_id: ID of the original record for deduplication.
        created_seq: Sequence number for ordering.
        metadata: Additional metadata.
    """

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    role: Literal["user", "assistant", "system", "tool"] = "assistant"
    record_type: str = "node_output"
    content: str | dict | list[dict] = ""
    visibility: Literal["user_visible", "internal", "tool_only"] = "user_visible"
    source_node_id: str | None = None
    source_session_id: str | None = None
    receiver_node_id: str | None = None
    receiver_session_id: str | None = None
    origin_record_id: str | None = None
    created_seq: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
