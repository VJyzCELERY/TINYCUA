"""AcceptedResult and WorkerResult state objects."""

from __future__ import annotations

import dataclasses

from tinycua.state.base import StateObject


@dataclasses.dataclass
class AcceptedResult(StateObject):
    """A single accepted task output for Primary Agent consumption.

    Attributes:
        task_id: ID of the accepted task.
        name: Name of the accepted task.
        result: Task output text.
    """

    task_id: str
    name: str
    result: str


@dataclasses.dataclass
class WorkerResult(StateObject):
    """Aggregated accepted task results for Primary Agent.

    Attributes:
        accepted_results: List of accepted task results.
    """

    accepted_results: list[AcceptedResult]
