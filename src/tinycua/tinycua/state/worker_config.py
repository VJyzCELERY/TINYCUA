"""WorkerConfig state object."""

from __future__ import annotations

__all__ = ["WorkerConfig", "EffortLevel"]

import dataclasses
from typing import Literal

from tinycua.state.base import StateObject

EffortLevel = Literal["none", "high"]


@dataclasses.dataclass
class WorkerConfig(StateObject):
    """Worker configuration controlling behavior and effort.

    Attributes:
        effort: Effort level for planning - 'none' or 'high'.
    """

    effort: EffortLevel

    def __post_init__(self) -> None:
        """Validate effort enum value."""
        self._validate_enum(
            self.effort,
            {"none", "high"},
            "effort",
        )
