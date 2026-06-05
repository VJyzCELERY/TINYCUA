"""Session model for tracking agent execution state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tinycua.config.session_config import SessionConfig


@dataclass
class Session:
    """Represents an agent execution session.

    A session tracks the conversation history, context entries,
    and associated task/todo state for a single agent execution.

    Attributes:
        session_id: Unique identifier for this session.
        parent_id: Optional parent session ID for child sessions.
        session_config: Configuration applied to this session.
        chat_history: List of chat message dicts (role, content, etc.).
        session_context: List of context entries populated by nodes.
        task: Optional task description string.
        todo: Optional todo list.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: str | None = None
    session_config: SessionConfig | None = None
    chat_history: list[dict[str, Any]] = field(default_factory=list)
    session_context: list[dict[str, Any]] = field(default_factory=list)
    task: str | None = None
    todo: list[dict[str, Any]] = field(default_factory=list)

    def compact_context(self) -> None:
        """Compact context entries (placeholder for Milestone 1.1).

        In future milestones this will apply the compaction strategy
        defined in session_config to reduce context size.
        """
