"""Session configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

if TYPE_CHECKING:
    from tinycua.compaction.strategy import CompactionStrategy


@dataclass
class InteractionPolicy:
    """Controls human-in-the-loop behavior for unattended runs.

    Defaults are non-interactive so benchmark and CI runs complete
    deterministically unless HITL behavior is explicitly enabled.
    """

    hitl_enabled: bool = False
    uncertain_strategy: Literal["passthrough", "route_worker", "ask", "fail"] = (
        "passthrough"
    )
    allow_clarifying_questions: bool = False


@dataclass(frozen=True)
class NativeToolPolicy:
    """Controls which optional native tools the public factory exposes."""

    allowed_tool_names: frozenset[str] | None = None

    def permits(self, tool_name: str) -> bool:
        """Return whether a native tool name is allowed by this policy."""
        return self.allowed_tool_names is None or tool_name in self.allowed_tool_names


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
        worker_effort: Worker decomposition effort. ``medium`` defaults to two
            task-analysis passes before execution.
    """

    compaction_strategy: CompactionStrategy | None = None
    max_context_messages: int | None = 100
    max_context_tokens: int | None = None
    interaction_policy: InteractionPolicy = field(default_factory=InteractionPolicy)
    workspace_dir: Path | None = None
    artifact_dir: Path | None = None
    session_dir: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    worker_effort: Literal["none", "low", "medium", "high"] = "medium"
    # When True, suppress per-tool-call audit JSON files (the tool-calls/
    # subdirectory under artifact_dir). Trace/transcript/logs are still
    # written. Set via CLI --no-tool-audit.
    disable_tool_audit: bool = False
    # When True, allow the ResultReviewer to emit ``OPEN_QUESTION`` decisions
    # and bail to ResponseNode for unresolved upstream questions. Defaults to
    # False — one-shot worker mode must not bail while tasks remain
    # unfinished. Enable for interactive/exploratory sessions.
    enable_open_question_review: bool = False
    # Consecutive reviewer rejections (needs_revision/rejected) before the
    # runtime deterministically routes to TaskAnalyzer for replan instead of
    # retrying the executor. Resets on reviewer approval. Default 5.
    replan_threshold: int = 5
    # Maximum replans per task before the runtime force-approves the task
    # with a "replan budget exhausted" rationale (FR-050). When None, derived
    # from ``worker_effort``: none=0, low=1, medium=3, high=6. An explicit
    # value overrides the effort-derived default.
    max_replans: int | None = None
    # Milestone 8 Stream B: compaction thresholds (ratio of model.max_context).
    # When session._last_input_tokens exceeds compaction_threshold * max_context,
    # dynamic context is compacted (keep last N turns, summarize the rest).
    # Static context (mission, instruction, continuation) is never compacted.
    compaction_threshold: float = 0.7
    # Task result summaries are compacted more aggressively (lower threshold)
    # because they're secondary context, not primary content.
    task_result_compaction_threshold: float = 0.3
    # Number of recent dynamic turns to keep during compaction.
    compaction_keep_recent: int = 5
    # FR-087: opt-in markdown-synthesis retry ("lazy retry"). When "standard"
    # (default), retry/recovery behavior is bit-for-bit unchanged. When
    # "markdown_synthesis", missing-state-tool validation failures get one
    # no-tools markdown continuation before standard recovery (FR-088..093).
    recovery_strategy: Literal["standard", "markdown_synthesis"] = "standard"

    # Effort → max_replans mapping (FR-050). Used when max_replans is None.
    _EFFORT_MAX_REPLANS: ClassVar[dict[str, int]] = {
        "none": 0,
        "low": 1,
        "medium": 3,
        "high": 6,
    }

    def __post_init__(self) -> None:
        """Normalize filesystem paths and derive effort-profiled settings."""
        if self.workspace_dir is not None:
            self.workspace_dir = Path(self.workspace_dir).expanduser().resolve()
        if self.artifact_dir is not None:
            self.artifact_dir = Path(self.artifact_dir).expanduser().resolve()
        if self.session_dir is not None:
            self.session_dir = Path(self.session_dir).expanduser().resolve()
        # FR-050: derive max_replans from worker_effort when not explicit.
        if self.max_replans is None:
            self.max_replans = self._EFFORT_MAX_REPLANS.get(
                str(self.worker_effort), 3
            )
