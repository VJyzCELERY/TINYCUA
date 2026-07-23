"""Node-level contracts: single declarative source of truth for per-node tool/state requirements.

Consolidates the 13+ scattered required-tool maps into one registry. Each
``NodeContract`` declares what a node must call, which tools are deterministic
(no-arg, runtime-synthesizable), and (for Milestone 3) the structured-output
schema. Consulted by validators, retry prompt builders, tool-narrowing logic,
the recovery loop, and tool_choice forcing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    """Per-node runtime tracking. Lives on ``session.node_progress[node_id]``.

    Makes node state observable: ``phase``, ``attempt_count``, which tools
    have been called, which required tools are satisfied, and a history of
    state transitions. Also carries ``accumulated_tool_results`` across
    recovery re-entries and ``stage_tool_history`` for the no-progress guard.
    """

    phase: NodeState = NodeState.PENDING
    attempt_count: int = 0
    visited_tools: set[str] = None  # type: ignore[assignment]
    satisfied_requirements: set[str] = None  # type: ignore[assignment]
    history: list[dict[str, Any]] = None  # type: ignore[assignment]
    # FR-063: successful tool results accumulated across recovery stages.
    # Survives re-entry (lives on session). Fresh dispatch resets.
    accumulated_tool_results: dict[str, dict] = None  # type: ignore[assignment]
    # FR-063: per-stage log of what each recovery attempt produced, so the
    # no-progress guard has evidence and recovery messages can show the
    # model what it already did.
    stage_tool_history: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        """Initialize mutable default fields (dataclass mutable-default safe)."""
        if self.visited_tools is None:
            self.visited_tools = set()
        if self.satisfied_requirements is None:
            self.satisfied_requirements = set()
        if self.history is None:
            self.history = []
        if self.accumulated_tool_results is None:
            self.accumulated_tool_results = {}
        if self.stage_tool_history is None:
            self.stage_tool_history = []

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
        self.accumulated_tool_results.clear()
        self.stage_tool_history.clear()


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
    # FR-064: goal-oriented instruction fields. Injected into the system
    # message so the model knows its fulfillment criteria and WHY each
    # tool is required — not just "call X" but "call X because Y."
    goal: str = ""
    success_criteria: str = ""
    tool_rationale: dict[str, str] = field(default_factory=dict)
    # Tools that are not strictly required but should be in the recovery chain
    # (e.g. task_inspect for the reviewer — it's guidance, not a gate, but
    # the recovery loop should still prompt for it before terminate).
    additional_recovery_tools: tuple[str, ...] = ()

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
        goal="Initialize the root task from the user request and digested context.",
        success_criteria="task_init called with a concise title and description, then terminate.",
        tool_rationale={
            "task_init": "Creates the root task that the entire roadmap descends from. Without it, there's nothing to decompose or execute.",
            "terminate": "Ends this node so the analyzer can decompose the root task. Without terminate, the loop is stuck here.",
        },
    ),
    "task_analyzer": NodeContract(
        node_id="task_analyzer",
        any_of_tools=frozenset(
            {
                frozenset({"task_create"}),
                frozenset({"task_decompose"}),
                frozenset({"task_shrink"}),
                frozenset({"task_update"}),
            }
        ),
        requires_terminate=True,
        early_stop_tool="task_decompose",
        goal="Break down the active task into concrete, executable subtasks grounded in current reality.",
        success_criteria="A supported task mutation succeeds, then terminate. The roadmap is actionable or safely repaired.",
        tool_rationale={
            "task_decompose": "Creates child tasks the executor can pick up. Without this, the roadmap has no executable next steps.",
            "task_update": "Confirms the existing roadmap is sufficient. Use when no useful decomposition remains.",
            "task_create": "Adds a missing child or sibling without recreating completed roadmap history.",
            "task_shrink": "Cancels, supersedes, deletes, or merges invalid local work safely.",
            "terminate": "Ends this node so the runtime advances to the executor. Without terminate, the loop is stuck here.",
        },
    ),
    "task_assessor": NodeContract(
        node_id="task_assessor",
        required_tools=frozenset({"node_handoff"}),
        requires_terminate=True,
        early_stop_tool="node_handoff",
        goal="Assess decomposition readiness and instruct the analyzer which tasks to refine.",
        success_criteria="node_handoff called with the assessment (selected tasks, reasons, or 'no further decomposition useful'), then terminate.",
        tool_rationale={
            "node_handoff": "Passes your assessment to the analyzer. Without it, the analyzer doesn't know what to focus on.",
            "terminate": "Ends this node so the analyzer can act on your handoff.",
        },
    ),
    "task_executor": NodeContract(
        node_id="task_executor",
        required_tools=frozenset({"task_result_update"}),
        requires_terminate=True,
        early_stop_tool="task_result_update",
        retry_max_attempts=25,
        goal="Execute the active task: explore, act, verify, then report the outcome.",
        success_criteria="task_result_update called with the outcome (success=true/false and evidence), then terminate.",
        tool_rationale={
            "task_result_update": "Records what was done and whether it succeeded. The reviewer judges this report — without it, the runtime cannot infer task state from prose.",
            "terminate": "Ends this node so the reviewer can evaluate the outcome.",
        },
    ),
    "result_reviewer": NodeContract(
        node_id="result_reviewer",
        required_tools=frozenset({"task_review_decision"}),
        requires_terminate=True,
        retry_max_attempts=25,
        goal="Verify the executor's outcome against the task requirements using concrete evidence, then decide approve/revise/replan.",
        success_criteria="task_review_decision called with rationale citing validation evidence, then task_inspect, then terminate.",
        tool_rationale={
            "task_review_decision": "Records your verdict (approved/needs_revision/rejected/replan) with evidence. This drives the task lifecycle — approved→completed, needs_revision→rework.",
            "task_inspect": "Reads the task list after your decision so you can curate unfinished tasks.",
            "terminate": "Ends this node so the runtime advances to the next task or response.",
        },
        additional_recovery_tools=("task_inspect",),
    ),
    "query_analyst": NodeContract(
        node_id="query_analyst",
        required_tools=frozenset({"select_query_route"}),
        goal="Classify the user request and route it to the correct handler.",
        success_criteria="select_query_route called with exactly one route (worker, uncertain, passthrough).",
        tool_rationale={
            "select_query_route": "Expresses the routing decision. Text-only answers are not actionable — the runtime reads the function call.",
        },
    ),
    "worker": NodeContract(
        node_id="worker",
        required_tools=frozenset({"select_worker_route"}),
        goal="Determine the next orchestration step based on current task state.",
        success_criteria="select_worker_route called with exactly one route (task_creation, task_recreation, task_reanalysis, passthrough, proceed_execution).",
        tool_rationale={
            "select_worker_route": "Expresses the orchestration decision. The runtime advances based on this, not on prose.",
        },
    ),
    "digester": NodeContract(
        node_id="digester",
        early_stop_tool="digest_information",
        goal="Gather comprehensive context to ground downstream task planning.",
        success_criteria="digest_information called with a concise summary of findings (context first, then original query).",
        tool_rationale={
            "digest_information": "Records the gathered context. Downstream nodes (analyzer, executor) rely on this — without it, planning is ungrounded.",
            "enhanced_context_retrieval": "Inspects prior conversation history. Use this before external research to avoid redundant work.",
            "web_search": "Finds current information for fast-moving domains. Use 2-4 searches to ground planning.",
        },
    ),
    "response": NodeContract(
        node_id="response",
        goal="Synthesize the final user-facing answer from completed task evidence.",
        success_criteria="A concise, non-empty natural language response mentioning concrete artifacts and key findings.",
    ),
    "result_aggregation": NodeContract(
        node_id="result_aggregation",
        goal="Compact completed task results into concise response-ready context.",
        success_criteria="Aggregated summary of completed task results with artifacts and verification evidence.",
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


# ---------------------------------------------------------------------------
# FR-061: Derived runtime maps — single source of truth from _NODE_CONTRACTS.
# These replace the ad-hoc maps scattered across validation_retry_mixin.py
# and orchestration_mixin.py. Drift between contract and runtime is now
# impossible — change the contract, and all derived maps update automatically.
# ---------------------------------------------------------------------------

#: Node IDs that require terminate after their work (replaces _TERMINATED_NODE_IDS).
TERMINATED_NODE_IDS: frozenset[str] = terminated_node_ids()

#: Required tools per node (replaces required_by_node dict).
REQUIRED_TOOLS_BY_NODE: dict[str, frozenset[str]] = {
    nc.node_id: nc.required_tools
    for nc in _NODE_CONTRACTS.values() if nc.required_tools
}

#: Any-of tool groups per node (replaces any_of_by_node dict).
ANY_OF_TOOLS_BY_NODE: dict[str, frozenset[frozenset[str]]] = {
    nc.node_id: nc.any_of_tools
    for nc in _NODE_CONTRACTS.values() if nc.any_of_tools
}


def _build_recovery_chains() -> dict[str, tuple[str, ...]]:
    """Derive recovery prerequisite chains from contracts (replaces _RECOVERY_CHAINS).

    For each terminated node, the chain is: required_tools (sorted) + the
    early_stop_tool (preferred representative of any-of) + additional_recovery_tools
    + 'terminate'. We only include ONE tool per any-of group (the
    ``early_stop_tool``) — the recovery loop should prompt for the preferred
    tool, not all alternatives. Order matters: the recovery loop injects
    ``missing[0]`` first.
    """
    chains: dict[str, tuple[str, ...]] = {}
    for nc in _NODE_CONTRACTS.values():
        if not nc.requires_terminate:
            continue
        tools: list[str] = []
        # Required tools first (sorted for stable order).
        tools.extend(sorted(nc.required_tools))
        # For any-of, include only the early_stop_tool (the preferred
        # representative). The recovery loop prompts for the preferred tool;
        # if the model calls the other any-of tool, the validator still
        # accepts it (via _validate_tool_owned_task_state's intersection check).
        if nc.early_stop_tool and nc.early_stop_tool not in tools:
            tools.append(nc.early_stop_tool)
        # Additional recovery tools (guidance, not gates — e.g. task_inspect).
        for t in nc.additional_recovery_tools:
            if t not in tools:
                tools.append(t)
        # Terminate always last.
        tools.append("terminate")
        chains[nc.node_id] = tuple(tools)
    return chains


#: Recovery prerequisite chains (replaces _RECOVERY_CHAINS class attr).
RECOVERY_CHAINS: dict[str, tuple[str, ...]] = _build_recovery_chains()


def _build_recovery_tool_map() -> dict[str, tuple[str, ...]]:
    """Derive the recovery tool candidate map from contracts.

    For each node, list all tools that could satisfy the contract (required +
    any-of flattened + additional_recovery_tools + terminate). Used by
    _required_tool_for_recovery to find which tool to inject during recovery.
    """
    tool_map: dict[str, tuple[str, ...]] = {}
    for nc in _NODE_CONTRACTS.values():
        tools: list[str] = []
        tools.extend(sorted(nc.required_tools))
        for group in nc.any_of_tools:
            for t in sorted(group):
                if t not in tools:
                    tools.append(t)
        for t in nc.additional_recovery_tools:
            if t not in tools:
                tools.append(t)
        if nc.requires_terminate and "terminate" not in tools:
            tools.append("terminate")
        if tools:
            tool_map[nc.node_id] = tuple(tools)
    return tool_map


#: Recovery tool candidates per node (replaces recovery_tool_map dict).
RECOVERY_TOOL_MAP: dict[str, tuple[str, ...]] = _build_recovery_tool_map()
