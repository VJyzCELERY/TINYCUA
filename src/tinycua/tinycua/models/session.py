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

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: str | None = None
    session_config: SessionConfig | None = None
    chat_history: list[dict[str, Any]] = field(default_factory=list)
    session_context: list[dict[str, Any]] = field(default_factory=list)
    task: str | None = None
    todo: list[dict[str, Any]] = field(default_factory=list)

    def compact_context(
        self, window: list[dict[str, Any]] | None = None
    ) -> dict[str, Any] | None:
        """Compact context entries using the configured strategy.

        If no ``compaction_strategy`` is set on ``session_config``, returns
        ``None`` immediately. Otherwise delegates to the strategy's
        ``compact()`` method and replaces the compacted window in
        ``session_context`` with the resulting summary.

        Args:
            window: Optional explicit subset of messages to compact. When
                ``None``, uses the full ``session_context``.

        Returns:
            The assistant-role summary dict produced by the strategy, or
            ``None`` if no strategy is configured.
        """
        if self.session_config is None or self.session_config.compaction_strategy is None:
            return None

        strategy = self.session_config.compaction_strategy
        messages = window if window is not None else self.session_context
        summary = strategy.compact(messages)

        if window is None:
            self.session_context = [summary]
        else:
            # Remove the compacted window entries and append the summary.
            # Build a set of ids for efficient removal.
            window_ids = {id(m) for m in window}
            self.session_context = [
                m for m in self.session_context if id(m) not in window_ids
            ]
            self.session_context.append(summary)

        return summary
