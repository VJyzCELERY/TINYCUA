"""Session configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from tinycua.compaction.strategy import CompactionStrategy


@dataclass
class InteractionPolicy:
    """Controls human-in-the-loop behavior for unattended runs.

    Defaults are non-interactive so benchmark and CI runs complete
    deterministically unless HITL behavior is explicitly enabled.
    """

    hitl_enabled: bool = False
    uncertain_strategy: Literal["fallback_response", "route_worker", "ask", "fail"] = (
        "fallback_response"
    )
    allow_clarifying_questions: bool = False


@dataclass
class SessionConfig:
    """Configuration for a session.

    Attributes:
        compaction_strategy: Strategy for compacting context. When set,
            ``Session.compact_context()`` delegates to this strategy.
        max_context_messages: Maximum number of messages to keep in context.
        max_context_tokens: Maximum token count for context window.
        metadata: Arbitrary metadata attached to the session.
    """

    compaction_strategy: CompactionStrategy | None = None
    max_context_messages: int | None = 100
    max_context_tokens: int | None = None
    interaction_policy: InteractionPolicy = field(default_factory=InteractionPolicy)
    metadata: dict[str, Any] = field(default_factory=dict)
