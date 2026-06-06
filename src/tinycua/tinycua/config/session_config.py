"""Session configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionConfig:
    """Configuration for a session.

    Attributes:
        compaction_strategy: Strategy for compacting context (reserved for
            future use).
        max_context_messages: Maximum number of messages to keep in context.
        max_context_tokens: Maximum token count for context window.
        metadata: Arbitrary metadata attached to the session.
    """

    compaction_strategy: Any | None = None
    max_context_messages: int | None = 100
    max_context_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
