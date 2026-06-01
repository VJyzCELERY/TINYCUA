"""AgentState state object."""

from __future__ import annotations

__all__ = ["AgentState", "AgentStatus"]

import dataclasses
from typing import Literal

from tinycua.state.base import StateObject

AgentStatus = Literal["idle", "running", "blocked", "terminated"]


@dataclasses.dataclass
class AgentState(StateObject):
    """Tracks internal agent lifecycle state.

    Attributes:
        active_agent: Name of the active agent.
        active_task_id: ID of the currently active task (optional).
        status: Operational status - idle, running, blocked, or terminated.
        resume_target: Resume target description (optional).
        consecutive_failures: Number of consecutive failures (non-negative).
    """

    active_agent: str
    active_task_id: str | None = None
    status: AgentStatus = "idle"
    resume_target: str | None = None
    consecutive_failures: int = 0

    def __post_init__(self) -> None:
        """Validate status enum and non-negative consecutive_failures."""
        self._validate_enum(
            self.status,
            {"idle", "running", "blocked", "terminated"},
            "status",
        )
        if self.consecutive_failures < 0:
            raise ValueError(
                "consecutive_failures must be non-negative"
            )
