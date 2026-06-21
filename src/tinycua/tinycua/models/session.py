"""Session model for tracking agent execution state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from tinycua.models.task import Task, TaskStateStore

if TYPE_CHECKING:
    from tinycua.config.session_config import SessionConfig
    from tinycua.models.chat_record import ChatRecord
    from tinycua.models.session_context_entry import SessionContextEntry


@dataclass
class Session:
    """Represents an agent execution session.

    A session tracks the conversation history, context entries,
    and associated task/todo state for a single agent execution.

    Attributes:
        session_id: Unique identifier for this session.
        parent_id: Optional parent session ID for child sessions.
        session_config: Configuration applied to this session.
        input_context: Merged SDK messages from the agent loop.
        chat_history: Append-only durable audit transcript.
        session_context: Mutable LLM-reusable context with segment metadata.
        diagnostics: Internal runtime diagnostics that must not be sent as
            reusable LLM context.
        task: Optional root task object.
        task_store: Session-owned task tree state.
        todo: Optional todo list.
    """

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: str | None = None
    session_config: SessionConfig | None = None
    input_context: list[dict[str, Any]] = field(default_factory=list)
    chat_history: list[ChatRecord] = field(default_factory=list)
    session_context: list[SessionContextEntry] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    task: Task | None = None
    task_store: TaskStateStore = field(default_factory=TaskStateStore)
    todo: list[dict[str, Any]] = field(default_factory=list)
    # Milestone 8 Stream B: per-session token tracking from provider usage.
    # Updated after each LLM call from response.usage.input_tokens.
    # Used to trigger compaction before the next call when over threshold.
    _last_input_tokens: int = 0
    # Session-scoped date snapshot for the system prompt (FR-015). Slow-moving
    # time info (date + weekday) injected into the stable system prefix so the
    # model sees the authoritative current date without a per-call timestamp
    # breaking prompt-cache stability. Set once at construction; child sessions
    # inherit the root's snapshot via ensure_session() so all nodes in one run
    # share one date. Never mutated during the session.
    date_snapshot: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d (%A)")
    )

    async def compact_context(
        self, window: list[SessionContextEntry] | list[dict[str, Any]] | None = None
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
        if (
            self.session_config is None
            or self.session_config.compaction_strategy is None
        ):
            return None

        # Early return for empty window — nothing to compact.
        if window is not None and len(window) == 0:
            return None

        strategy = self.session_config.compaction_strategy

        # Convert SessionContextEntry objects to dicts for compaction strategy
        def _to_dict(entry: SessionContextEntry | dict[str, Any]) -> dict[str, Any]:
            if isinstance(entry, dict):
                return entry
            return entry.to_dict()

        if window is not None:
            messages = [_to_dict(entry) for entry in window]
        else:
            messages = [_to_dict(entry) for entry in self.session_context]

        summary = await strategy.compact(messages)

        if window is None:
            # Convert summary dict back to SessionContextEntry if needed
            from tinycua.models.session_context_entry import SessionContextEntry

            if isinstance(summary, dict):
                # Check if the summary dict has SessionContextEntry fields
                if "record_id" in summary or "segment" in summary:
                    self.session_context = [SessionContextEntry.from_dict(summary)]
                else:
                    # Legacy format: wrap in SessionContextEntry
                    self.session_context = [
                        SessionContextEntry(
                            content=summary.get("content", ""),
                            segment="prior",
                            created_seq=0,
                        )
                    ]
            else:
                self.session_context = [summary]
        elif len(window) > 0:
            # Remove the compacted window entries and append the summary.
            # Find the window by comparing expected sequence within session_context.
            # Assumes window is a contiguous subset of session_context.
            from tinycua.models.session_context_entry import SessionContextEntry

            window_len = len(window)
            for i in range(len(self.session_context) - window_len + 1):
                # Compare by converting both to dicts for comparison
                current_slice = self.session_context[i : i + window_len]
                current_dicts = [_to_dict(entry) for entry in current_slice]
                window_dicts = [_to_dict(entry) for entry in window]
                if current_dicts == window_dicts:
                    if isinstance(summary, dict):
                        # Check if the summary dict has SessionContextEntry fields
                        if "record_id" in summary or "segment" in summary:
                            summary_entry = SessionContextEntry.from_dict(summary)
                        else:
                            # Legacy format: wrap in SessionContextEntry
                            summary_entry = SessionContextEntry(
                                content=summary.get("content", ""),
                                segment="prior",
                                created_seq=0,
                            )
                    else:
                        summary_entry = summary
                    self.session_context = (
                        self.session_context[:i]
                        + [summary_entry]
                        + self.session_context[i + window_len :]
                    )
                    break
            else:
                msg = "Supplied window is not a contiguous subset of session_context"
                raise ValueError(msg)

        return summary
