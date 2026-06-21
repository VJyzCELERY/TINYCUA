"""Node-level contracts: single declarative source of truth for per-node tool/state requirements.

Consolidates the 13+ scattered required-tool maps into one registry. Each
``NodeContract`` declares what a node must call, which tools are deterministic
(no-arg, runtime-synthesizable), and (for Milestone 3) the structured-output
schema. Consulted by validators, retry prompt builders, tool-narrowing logic,
the recovery loop, and tool_choice forcing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class NodeState(StrEnum):
    """Lifecycle state of a node during execution.

    Tracked on :class:`NodeProgress` so node state is observable in the
    execution trace, not implicit.
    """

    PENDING = "pending"
    EXECUTING = "executing"
    AWAITING_TOOL = "awaiting_tool"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class NodeProgress:
    """Per-node runtime tracking. Lives on the ``Node`` instance.

    Makes node state observable: ``phase``, ``attempt_count``, which tools
    have been called, which required tools are satisfied, and a history of
    state transitions.
    """

    phase: NodeState = NodeState.PENDING
    attempt_count: int = 0
    visited_tools: set[str] = None  # type: ignore[assignment]
    satisfied_requirements: set[str] = None  # type: ignore[assignment]
    history: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        """Initialize mutable default fields (dataclass mutable-default safe)."""
        if self.visited_tools is None:
            self.visited_tools = set()
        if self.satisfied_requirements is None:
            self.satisfied_requirements = set()
        if self.history is None:
            self.history = []

    def transition(self, to: NodeState, reason: str = "") -> None:
        """Transition to a new phase, recording the transition in history.

        Args:
            to: The new phase.
            reason: Why the transition happened (for observability).
        """
        self.history.append(
            {
                "from": self.phase,
                "to": to,
                "reason": reason,
                "attempt": self.attempt_count,
            }
        )
        self.phase = to

    def mark_tool_called(self, tool_name: str, success: bool = True) -> None:
        """Record that a tool was called on this node.

        Args:
            tool_name: The tool that was called.
            success: Whether the tool call succeeded.
        """
        self.visited_tools.add(tool_name)
        if success:
            self.satisfied_requirements.add(tool_name)

    def reset(self) -> None:
        """Reset progress for a fresh node lifecycle (e.g. re-enqueued)."""
        self.phase = NodeState.PENDING
        self.attempt_count = 0
        self.visited_tools.clear()
        self.satisfied_requirements.clear()
        self.history.clear()


@dataclass(frozen=True)
class NodeContract:
    """Single declarative source of truth for a node's tool/state contract.

    One per ``node_id``. Replaces the 13+ scattered required-tool maps
    (``required_by_node``, ``any_of_by_node``, ``_RECOVERY_CHAINS``,
    ``_worker_lifecycle_ready_to_terminate``, ``_can_stop_after_tool_batch``,
    ``_retry_required_tool_name``, ``_required_single_tool_choice_name``,
    ``recovery_tool_map``, ``retry_required_by_node``, plus prompt strings and
    ``NodeRetryPolicy.required_tool_calls``).

    Attributes:
        node_id: The node this contract applies to.
        required_tools: ALL of these must be called successfully before the
            node can terminate.
        any_of_tools: At least one set in this collection must be fully
            satisfied (e.g. task_analyzer must call task_decompose OR
            task_update).
        deterministic_tools: No-arg tools the runtime may synthesize without
            an LLM round-trip (e.g. terminate). Tools whose arguments carry
            LLM-provided content MUST NOT be in this set.
        requires_terminate: Whether the node must call terminate after its
            required work is done (i.e. it's in the terminated-lifecycle set).
        early_stop_tool: A single tool whose successful result lets the
            inner tool-continuation loop exit early (e.g. task_result_update
            for task_executor).
        structured_output_schema: The json_schema for response_format, or
            None for free-text nodes. (Milestone 3 — populated later.)
        retry_max_attempts: Max retry attempts, or None for unbounded.
    """

    node_id: str
    required_tools: frozenset[str] = frozenset()
    any_of_tools: frozenset[frozenset[str]] = frozenset()
    deterministic_tools: frozenset[str] = frozenset({"terminate"})
    requires_terminate: bool = False
    early_stop_tool: str | None = None
    structured_output_schema: dict[str, Any] | None = None
    retry_max_attempts: int | None = None

    def is_satisfied(self, successful_tools: set[str]) -> bool:
        """Return whether the given successful-tool set satisfies this contract.

        Args:
            successful_tools: Tool names that completed successfully.

        Returns:
            True if all required_tools are present and at least one any_of
            set is satisfied (if any_of is non-empty).
        """
        if not self.required_tools.issubset(successful_tools):
            return False
        if self.any_of_tools:
            if not any(
                group.issubset(successful_tools) for group in self.any_of_tools
            ):
                return False
        return True


# ---------------------------------------------------------------------------
# Registry: the single source of truth.
#
# Data consolidated from:
#   validation_retry_mixin.py:862-880  — required_by_node, any_of_by_node
#   validation_retry_mixin.py:29-35    — _TERMINATED_NODE_IDS
#   validation_retry_mixin.py:632-654  — _worker_lifecycle_ready_to_terminate
#   validation_retry_mixin.py:786-797  — _can_stop_after_tool_batch
#   validation_retry_mixin.py:174      — retry_required_by_node
#   validation_retry_mixin.py:1125-1131 — recovery_tool_map
#   orchestration_mixin.py:899-905     — _RECOVERY_CHAINS
#   prompt_protocol_mixin.py:456-463   — _required_single_tool_choice_name
#   node_config.py:237-248            — required_tool_calls overrides
# ---------------------------------------------------------------------------

_NODE_CONTRACTS: dict[str, NodeContract] = {
    "task_create": NodeContract(
        node_id="task_create",
        required_tools=frozenset({"task_init"}),
        requires_terminate=True,
        early_stop_tool="task_init",
    ),
    "task_analyzer": NodeContract(
        node_id="task_analyzer",
        any_of_tools=frozenset({frozenset({"task_decompose"}), frozenset({"task_update"})}),
        requires_terminate=True,
        early_stop_tool="task_decompose",
    ),
    "task_assessor": NodeContract(
        node_id="task_assessor",
        required_tools=frozenset({"node_handoff"}),
        requires_terminate=True,
        early_stop_tool="node_handoff",
    ),
    "task_executor": NodeContract(
        node_id="task_executor",
        required_tools=frozenset({"task_result_update"}),
        requires_terminate=True,
        early_stop_tool="task_result_update",
        retry_max_attempts=25,
    ),
    "result_reviewer": NodeContract(
        node_id="result_reviewer",
        required_tools=frozenset({"task_review_decision"}),
        requires_terminate=True,
        # Reviewer also needs task_inspect before approving, but it's
        # not a hard requirement (it's guidance, not a gate). The
        # _worker_lifecycle_ready_to_terminate check requires both
        # task_review_decision AND task_inspect. We model this as an
        # any_of: {task_review_decision} is the strict requirement, but
        # readiness-to-terminate needs both. Keep it simple: the required
        # set is task_review_decision; the lifecycle check is separate.
        retry_max_attempts=25,
    ),
    # Free-text nodes (no required state-mutation tools):
    "query_analyst": NodeContract(
        node_id="query_analyst",
        required_tools=frozenset({"select_query_route"}),
    ),
    "worker": NodeContract(
        node_id="worker",
        required_tools=frozenset({"select_worker_route"}),
    ),
    "digester": NodeContract(
        node_id="digester",
        early_stop_tool="digest_information",
    ),
    "response": NodeContract(
        node_id="response",
    ),
    "result_aggregation": NodeContract(
        node_id="result_aggregation",
    ),
    "analysis_effort": NodeContract(
        node_id="analysis_effort",
    ),
    "information_digester": NodeContract(
        node_id="information_digester",
    ),
}


def get_node_contract(node_id: str) -> NodeContract:
    """Return the contract for a node_id, or a default empty contract.

    Args:
        node_id: The node identifier.

    Returns:
        The ``NodeContract`` for this node. Unknown node_ids get a contract
        with no required tools and no terminate requirement.
    """
    return _NODE_CONTRACTS.get(
        node_id,
        NodeContract(
            node_id=node_id,
            deterministic_tools=frozenset(),
            requires_terminate=False,
        ),
    )


def terminated_node_ids() -> frozenset[str]:
    """Return the set of node_ids that require terminate after their work."""
    return frozenset(
        nc.node_id for nc in _NODE_CONTRACTS.values() if nc.requires_terminate
    )
