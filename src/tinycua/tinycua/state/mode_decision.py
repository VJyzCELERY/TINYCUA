"""ContextEnhancedQuery and ModeDecision state objects."""

from __future__ import annotations

__all__ = ["ContextEnhancedQuery", "ModeDecision", "ModeType", "UncertainNextAction"]

import dataclasses
from typing import Literal

from tinycua.state.base import StateObject

ModeType = Literal["primary_agent", "worker", "uncertain"]
UncertainNextAction = Literal["ask_user", "explore"]


@dataclasses.dataclass
class ContextEnhancedQuery(StateObject):
    """User query enriched with high-level session context.

    Attributes:
        enhanced_query: The enhanced query text with context.
    """

    enhanced_query: str


@dataclasses.dataclass
class ModeDecision(StateObject):
    """Query analyst's routing decision.

    Attributes:
        mode: Chosen mode - primary_agent, worker, or uncertain.
        score: Confidence score for the mode choice.
        confidence: Overall confidence in the decision.
        reasons: List of reasons for the chosen mode.
        uncertain_next_action: Required when mode is 'uncertain'.
    """

    mode: ModeType
    score: float
    confidence: float
    reasons: list[str]
    uncertain_next_action: UncertainNextAction | None = None

    def __post_init__(self) -> None:
        """Validate enum fields and cross-field constraints."""
        self._validate_enum(
            self.mode,
            {"primary_agent", "worker", "uncertain"},
            "mode",
        )
        if self.uncertain_next_action is not None:
            self._validate_enum(
                self.uncertain_next_action,
                {"ask_user", "explore"},
                "uncertain_next_action",
            )
        if self.mode == "uncertain" and self.uncertain_next_action is None:
            raise ValueError(
                "uncertain_next_action is required when mode is 'uncertain'"
            )
