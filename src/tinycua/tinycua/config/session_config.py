"""Session configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from tinycua.compaction.strategy import CompactionStrategy


@dataclass
class SessionConfig:
    """Configuration for a session.

    Attributes:
        compaction_strategy: Strategy for compacting context. When set,
            ``Session.compact_context()`` delegates to this strategy.
        max_context_messages: Maximum number of messages to keep in context.
        max_context_tokens: Maximum token count for context window.
        metadata: Arbitrary metadata attached to the session.
        llm_client: LLM client callable for node LLM invocations. When set,
            spawned nodes (e.g., TaskExecutor, ResultReviewer) use this client
            instead of the agent's default ``_call_llm()``, enabling their
            custom logic (ReAct loops, decision parsing) to execute correctly.
    """

    compaction_strategy: CompactionStrategy | None = None
    max_context_messages: int | None = 100
    max_context_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    llm_client: Callable | None = None
