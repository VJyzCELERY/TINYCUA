"""Architecture path definitions and registry for the verification gate.

Defines all 12 TinyCUA architecture paths with node sequences, expected
outcomes, and validation criteria. Uses declarative data definitions for
clarity and maintainability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class ArchitecturePath:
    """Definition of a single architecture verification path.

    Attributes:
        name: Unique path identifier (e.g., "passthrough_simple").
        description: Human-readable description.
        node_sequence: Ordered node IDs to execute.
        expected_nodes: Nodes that must execute for the path to pass.
        expected_outcome: "success", "hitl", or "failure".
        timeout_seconds: Per-path timeout override (None = use gate default).
        setup_fn: Optional setup callback invoked before execution.
            Receives (queue, session, config) and can modify queue or
            inject context into session.
        validation_fn: Optional custom validation callback. Receives
            (path_result) and can modify status or add error details.
        worker_classification: Optional Worker classification to inject
            via session context (for paths 3 vs 11 distinction).
    """

    name: str
    description: str
    node_sequence: list[str]
    expected_nodes: list[str]
    expected_outcome: str = "success"
    timeout_seconds: int | None = None
    setup_fn: Callable[..., None] | None = None
    validation_fn: Callable[..., None] | None = None
    worker_classification: str | None = None


# ─── Path Definitions ────────────────────────────────────────────────────

PATH_PASSTHROUGH_SIMPLE = ArchitecturePath(
    name="passthrough_simple",
    description="Simple passthrough — QueryAnalyst → PrimaryAgent → Response",
    node_sequence=["query_analyst", "primary_agent", "response"],
    expected_nodes=["query_analyst", "primary_agent", "response"],
    expected_outcome="success",
)

PATH_PASSTHROUGH_DIGESTION = ArchitecturePath(
    name="passthrough_digestion",
    description=(
        "Passthrough with digestion — PrimaryAgent determines it needs "
        "consolidated context, invokes InformationDigester"
    ),
    node_sequence=[
        "query_analyst",
        "primary_agent",
        "information_digester",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "primary_agent",
        "information_digester",
        "response",
    ],
    expected_outcome="success",
)

PATH_WORKER_SIMPLE = ArchitecturePath(
    name="worker_simple",
    description=(
        "Simple worker — single task created, executed, accepted. "
        "Path 3 and Path 11 share the same node sequence; they differ "
        "in Worker classification (task_creation vs proceed_execution)."
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_outcome="success",
    worker_classification="task_creation",
)

PATH_WORKER_TASK_CREATION = ArchitecturePath(
    name="worker_task_creation",
    description=(
        "Worker with upfront task decomposition — TaskCreation builds "
        "task tree, TaskAssessor evaluates, TaskAnalyzer decomposes"
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_outcome="success",
    worker_classification="task_creation",
)

PATH_WORKER_RETRY = ArchitecturePath(
    name="worker_retry",
    description=(
        "Worker with retry — task fails, ResultReviewer decides to retry, "
        "second attempt succeeds"
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_outcome="success",
    worker_classification="task_creation",
)

PATH_WORKER_REPLAN = ArchitecturePath(
    name="worker_replan",
    description=(
        "Worker with replan — task fails, ResultReviewer triggers "
        "TaskAnalyzer for decomposition, sub-tasks executed"
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "task_analyzer",
        "primary_agent",
        "response",
    ],
    expected_outcome="success",
    worker_classification="task_creation",
)

PATH_WORKER_FAILURE = ArchitecturePath(
    name="worker_failure",
    description=(
        "Worker with failure — repeated failures reach threshold, "
        "agent stays active for human-in-the-loop"
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
    ],
    expected_outcome="hitl",
    worker_classification="task_creation",
)

PATH_WORKER_DECOMPOSITION = ArchitecturePath(
    name="worker_decomposition",
    description=(
        "Worker with task decomposition — TaskAssessor identifies tasks "
        "needing decomposition, TaskAnalyzer breaks them down"
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_outcome="success",
    worker_classification="task_creation",
)

PATH_WORKER_RECREATION = ArchitecturePath(
    name="worker_recreation",
    description=(
        "Worker re-entry with task_recreation — Worker classifies as "
        "task_recreation, TaskCreation builds new task tree"
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_assessor",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_outcome="success",
    worker_classification="task_recreation",
)

PATH_WORKER_REANALYSIS = ArchitecturePath(
    name="worker_reanalysis",
    description=(
        "Worker re-entry with task_reanalysis — Worker classifies as "
        "task_reanalysis, TaskAnalyzer reanalyzes scope"
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_outcome="success",
    worker_classification="task_reanalysis",
)

PATH_WORKER_PROCEED = ArchitecturePath(
    name="worker_proceed",
    description=(
        "Worker re-entry with proceed_execution — Worker classifies as "
        "proceed_execution, next task executed directly"
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_outcome="success",
    worker_classification="proceed_execution",
)

PATH_WORKER_AGGREGATION = ArchitecturePath(
    name="worker_aggregation",
    description=(
        "Worker result aggregation — PrimaryAgent synthesizes from "
        "aggregated context (ResultAggregationNode not yet implemented)"
    ),
    node_sequence=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_nodes=[
        "query_analyst",
        "information_digester",
        "worker",
        "task_creation",
        "task_executor",
        "result_reviewer",
        "primary_agent",
        "response",
    ],
    expected_outcome="success",
    worker_classification="task_creation",
)


# ─── Path Registry ───────────────────────────────────────────────────────

ALL_PATHS: list[ArchitecturePath] = [
    PATH_PASSTHROUGH_SIMPLE,
    PATH_PASSTHROUGH_DIGESTION,
    PATH_WORKER_SIMPLE,
    PATH_WORKER_TASK_CREATION,
    PATH_WORKER_RETRY,
    PATH_WORKER_REPLAN,
    PATH_WORKER_FAILURE,
    PATH_WORKER_DECOMPOSITION,
    PATH_WORKER_RECREATION,
    PATH_WORKER_REANALYSIS,
    PATH_WORKER_PROCEED,
    PATH_WORKER_AGGREGATION,
]

_PATH_REGISTRY: dict[str, ArchitecturePath] = {p.name: p for p in ALL_PATHS}


def get_path(name: str) -> ArchitecturePath:
    """Look up a path by name.

    Args:
        name: The path name to look up.

    Returns:
        The matching ArchitecturePath.

    Raises:
        KeyError: If no path with the given name exists.
    """
    if name not in _PATH_REGISTRY:
        available = ", ".join(sorted(_PATH_REGISTRY.keys()))
        raise KeyError(f"Unknown path '{name}'. Available: {available}")
    return _PATH_REGISTRY[name]


def list_paths() -> list[str]:
    """Return all registered path names.

    Returns:
        Sorted list of path names.
    """
    return sorted(_PATH_REGISTRY.keys())
