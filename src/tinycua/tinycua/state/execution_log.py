"""ExecutionLog and ExecutionLogEntry state objects."""

from __future__ import annotations

import dataclasses

from tinycua.state.base import StateObject


@dataclasses.dataclass
class ExecutionLogEntry(StateObject):
    """A single entry in the execution log.

    Attributes:
        action: Action that was taken.
        outcome: Outcome of the action.
        decision: Optional decision trace or reasoning.
    """

    action: str
    outcome: str
    decision: str | None = None


@dataclasses.dataclass
class ExecutionLog(StateObject):
    """Record of actions, outcomes, and decisions during sub-session execution.

    Attributes:
        entries: List of execution log entries.
    """

    entries: list[ExecutionLogEntry]
