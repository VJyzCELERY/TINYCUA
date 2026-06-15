"""Session configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
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
        workspace_dir: Directory where file tools operate for this session.
        artifact_dir: Directory where run artifacts should be written.
        session_dir: Directory for session-scoped persisted state.
        metadata: Arbitrary metadata attached to the session.
    """

    compaction_strategy: CompactionStrategy | None = None
    max_context_messages: int | None = 100
    max_context_tokens: int | None = None
    interaction_policy: InteractionPolicy = field(default_factory=InteractionPolicy)
    workspace_dir: Path | None = None
    artifact_dir: Path | None = None
    session_dir: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize filesystem paths supplied through the public API."""
        if self.workspace_dir is not None:
            self.workspace_dir = Path(self.workspace_dir).expanduser().resolve()
        if self.artifact_dir is not None:
            self.artifact_dir = Path(self.artifact_dir).expanduser().resolve()
        if self.session_dir is not None:
            self.session_dir = Path(self.session_dir).expanduser().resolve()
