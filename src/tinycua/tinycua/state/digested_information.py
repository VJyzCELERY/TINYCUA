"""DigestedInformation state object."""

from __future__ import annotations

__all__ = ["DigestedInformation"]

import dataclasses

from tinycua.state.base import StateObject


@dataclasses.dataclass
class DigestedInformation(StateObject):
    """Precision-oriented context summary produced by the Information Digester.

    Attributes:
        context_summary: Compressed relevant context in markdown (required).
        key_points: List of key takeaway points (required).
        advisory_instructions: Action-oriented guidance (optional).
        constraints: List of guardrails (optional).
        known_gaps: List of missing information (optional).
    """

    context_summary: str
    key_points: list[str]
    advisory_instructions: str | None = None
    constraints: list[str] | None = None
    known_gaps: list[str] | None = None
