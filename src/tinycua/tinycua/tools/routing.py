"""Routing decision tools for TinyCUA decision nodes."""

from __future__ import annotations

from tinycua.config.types import Tool


def _route_parameters(labels: list[str]) -> dict:
    """Build a strict route-selection JSON schema."""
    return {
        "type": "object",
        "properties": {
            "route": {
                "type": "string",
                "enum": labels,
                "description": "The exact route label selected for the decision node.",
            },
            "reason": {
                "type": "string",
                "description": "Brief internal reason for selecting the route.",
            },
        },
        "required": ["route"],
        "additionalProperties": False,
    }


class QueryRouteSelectionTool(Tool):
    """Tool schema for selecting the top-level query route."""

    def __init__(self) -> None:
        super().__init__(
            name="select_query_route",
            description=(
                "Select exactly one route for the user request: worker for "
                "task planning/execution, uncertain for unsafe ambiguity, or "
                "passthrough for direct conversational/factual responses."
            ),
            parameters=_route_parameters(["worker", "uncertain", "passthrough"]),
        )


class WorkerRouteSelectionTool(Tool):
    """Tool schema for selecting the worker orchestration route."""

    def __init__(self, labels: list[str] | None = None) -> None:
        """Initialize worker route selector with state-valid labels."""
        route_labels = labels or [
            "task_creation",
            "task_recreation",
            "task_reanalysis",
            "passthrough",
            "proceed_execution",
        ]
        super().__init__(
            name="select_worker_route",
            description=(
                "Select exactly one worker orchestration route based on the "
                "digested request and task state."
            ),
            parameters=_route_parameters(route_labels),
        )
