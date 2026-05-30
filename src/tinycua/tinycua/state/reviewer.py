"""ContextUpdate and ReviewerDecision state objects."""

from __future__ import annotations

__all__ = ["ContextUpdate", "ReviewerDecision", "ReviewStatus"]

import dataclasses
from typing import Literal

from tinycua.state.base import StateObject

ReviewStatus = Literal["accepted", "retry", "replan", "escalate_user"]


@dataclasses.dataclass
class ContextUpdate(StateObject):
    """A targeted context modification produced by the Result Reviewer.

    Attributes:
        target_task_id: ID of the task to update.
        update: Context update string.
    """

    target_task_id: str
    update: str


@dataclasses.dataclass
class ReviewerDecision(StateObject):
    """Result Reviewer's judgment on a task result.

    Attributes:
        task_id: ID of the reviewed task.
        status: Review status - accepted, retry, replan, or escalate_user.
        reason: Reason for the decision.
        confidence: Confidence in the decision.
        context_updates: Optional list of context updates.
        retry_instructions: Optional retry instructions.
    """

    task_id: str
    status: ReviewStatus
    reason: str
    confidence: float
    context_updates: list[ContextUpdate] | None = None
    retry_instructions: str | None = None

    def __post_init__(self) -> None:
        """Validate status enum value."""
        self._validate_enum(
            self.status,
            {"accepted", "retry", "replan", "escalate_user"},
            "status",
        )
