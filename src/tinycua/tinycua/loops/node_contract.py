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


class LifecyclePhase(StrEnum):
    """Focused tool exposure phases for lifecycle nodes."""

    PLAN = "plan"
    ACTION = "action"
    SUMMARY = "summary"
    COMMIT = "commit"
    TERMINATE = "terminate"


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
    # Recovery state is session-backed so re-dispatch cannot restart an
    # unchanged corrective strategy.
    recovery_attempts: dict[str, int] = None  # type: ignore[assignment]
    recovery_fingerprint: str = ""
    recovery_escalations: list[dict[str, Any]] = None  # type: ignore[assignment]
    recovery_last_error: str = ""
    lifecycle_phase: LifecyclePhase = LifecyclePhase.ACTION
    action_summary: str = ""
    lifecycle_history: list[dict[str, str]] = None  # type: ignore[assignment]
    correlated_outcomes: list[dict[str, Any]] = None  # type: ignore[assignment]

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
        if self.recovery_attempts is None:
            self.recovery_attempts = {}
        if self.recovery_escalations is None:
            self.recovery_escalations = []
        if self.lifecycle_history is None:
            self.lifecycle_history = []
        if self.correlated_outcomes is None:
            self.correlated_outcomes = []

    def advance_lifecycle(self, phase: LifecyclePhase, summary: str = "") -> None:
        """Record a phase transition and retain the bounded action summary."""
        if summary:
            self.action_summary = summary[:8_000]
        self.lifecycle_phase = phase
        self.lifecycle_history.append(
            {"phase": phase.value, "summary": summary[:8_000]}
        )

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
        self.recovery_attempts.clear()
        self.recovery_fingerprint = ""
        self.recovery_escalations.clear()
        self.recovery_last_error = ""
        self.lifecycle_phase = LifecyclePhase.ACTION
        self.action_summary = ""
        self.lifecycle_history.clear()
        self.correlated_outcomes.clear()


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
        requires_terminate: Legacy name for nodes using the focused ACTION →
            COMMIT lifecycle. A successful commit ends the node automatically.
        early_stop_tool: A single tool whose successful result lets the
            inner tool-continuation loop exit early (e.g. task_result_update
            for task_executor).
        structured_output_schema: The json_schema for response_format, or
            None for free-text nodes. (Milestone 3 — populated later.)
        retry_max_attempts: Max retry attempts, or None for unbounded.
        role_boundary: The work this node may perform and its explicit limits.
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
    role_boundary: str = ""
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
            if not any(group.issubset(successful_tools) for group in self.any_of_tools):
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
        role_boundary="Only initialize one root roadmap. Do not research, write files, execute work, or decompose tasks.",
        success_criteria="task_init called with a concise title and description.",
        tool_rationale={
            "task_init": "Creates the root task that the entire roadmap descends from. Without it, there's nothing to decompose or execute.",
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
        early_stop_tool=None,
        goal=(
            "Produce or refine a roadmap of coherent, actionable, and verifiable "
            "outcomes with sufficient context and specific observable evidence."
        ),
        role_boundary="Plan task structure only. Do not execute requested work or prescribe unsupported implementation details.",
        success_criteria="Every selected planning target is resolved and the roadmap is coherent, actionable, verifiable, and nonredundant.",
        tool_rationale={
            "task_decompose": "Creates coherent, actionable, and verifiable child outcomes with specific observable evidence.",
            "task_update": "Confirms the existing roadmap is sufficient. Use when no useful decomposition remains.",
            "task_create": "Adds a missing child or sibling without recreating completed roadmap history.",
            "task_shrink": "Cancels, supersedes, deletes, or merges invalid local work safely.",
        },
    ),
    "task_assessor": NodeContract(
        node_id="task_assessor",
        required_tools=frozenset({"task_assessment_decision"}),
        requires_terminate=True,
        early_stop_tool="task_assessment_decision",
        goal=(
            "Review whether every roadmap task is coherent, actionable, and verifiable "
            "from specific observable evidence."
        ),
        role_boundary="Planning judgment only; never execute work or impose unsupported implementation choices.",
        success_criteria="task_assessment_decision called with ready or task-bound blocking findings on unfinished tasks.",
        tool_rationale={
            "task_assessment_decision": "Validates readiness and passes canonical targets to the paired analyzer.",
        },
    ),
    "task_executor": NodeContract(
        node_id="task_executor",
        required_tools=frozenset({"task_result_update"}),
        requires_terminate=True,
        early_stop_tool="task_result_update",
        retry_max_attempts=25,
        goal="Execute the active task: explore, act, verify, then report the outcome.",
        role_boundary="Only execute and complete the active task. Report verified incidental effects on pending outcomes without marking those tasks complete.",
        success_criteria="task_result_update called with a concise outcome report and success=true/false.",
        tool_rationale={
            "task_result_update": "Records what was done and whether it succeeded. The reviewer judges this report — without it, the runtime cannot infer task state from prose.",
        },
    ),
    "result_reviewer": NodeContract(
        node_id="result_reviewer",
        required_tools=frozenset({"task_review_decision"}),
        requires_terminate=True,
        retry_max_attempts=25,
        goal=(
            "Review and try to falsify the active task outcome, update its journal, and "
            "explicitly curate relevant future-task context."
        ),
        role_boundary=(
            "Review only the active task. The decision may include context handoffs "
            "for unfinished tasks; never review or execute those tasks, modify their "
            "artifacts, or fix executor work."
        ),
        success_criteria=(
            "task_review_decision called for the active task with review_summary, "
            "findings, rationale, root criterion assessments when planned, and any "
            "explicit future-task context_updates."
        ),
        tool_rationale={
            "task_review_plan": (
                "Precommits root falsification checks before Executor conclusions are "
                "revealed. It records a plan, not evidence."
            ),
            "task_review_decision": "Records approved, needs_revision, replan, monotonic postponement, or terminal compromise. Approved completes; needs_revision reworks; compromise remains unsuccessful.",
            "task_inspect": "Reads task state for active-task review and future-task context curation.",
        },
        additional_recovery_tools=("task_inspect",),
    ),
    "query_analyst": NodeContract(
        node_id="query_analyst",
        required_tools=frozenset({"summarize_query_context", "select_query_route"}),
        goal="Classify the user request and route it to the correct handler.",
        role_boundary="Only classify and route the request. Do not plan tasks, execute work, or write deliverables.",
        success_criteria="summarize_query_context and exactly one select_query_route call succeed.",
        tool_rationale={
            "summarize_query_context": "Commits the preliminary summary used to build the downstream request handoff.",
            "select_query_route": "Expresses the routing decision. Text-only answers are not actionable — the runtime reads the function call.",
        },
    ),
    "worker": NodeContract(
        node_id="worker",
        required_tools=frozenset({"select_worker_route"}),
        goal="Determine the next orchestration step based on current task state.",
        role_boundary="Only choose the next orchestration route. Do not initialize, plan, execute, or review tasks.",
        success_criteria="select_worker_route called with exactly one route (task_creation, task_recreation, task_reanalysis, passthrough, proceed_execution).",
        tool_rationale={
            "select_worker_route": "Expresses the orchestration decision. The runtime advances based on this, not on prose.",
        },
    ),
    "digester": NodeContract(
        node_id="digester",
        required_tools=frozenset({"digest_information"}),
        requires_terminate=True,
        early_stop_tool="digest_information",
        goal="Gather comprehensive context to ground downstream task planning.",
        role_boundary="Only gather and digest context. Do not create tasks, execute work, or write deliverables.",
        success_criteria="digest_information called with a concise structured summary of findings.",
        tool_rationale={
            "digest_information": "Records the gathered context. Downstream nodes (analyzer, executor) rely on this — without it, planning is ungrounded.",
            "enhanced_context_retrieval": "Inspects prior conversation history after explicitly referenced workspace files have been read.",
            "web_search": "Resolves material external uncertainty with sources appropriate to the requested timeframe.",
        },
    ),
    "response": NodeContract(
        node_id="response",
        goal="Synthesize the final user-facing answer from completed task evidence.",
        role_boundary="Only provide the final user-facing answer. Do not execute work or mutate task state.",
        success_criteria="A concise, non-empty natural language response mentioning concrete artifacts and key findings.",
    ),
    "result_aggregation": NodeContract(
        node_id="result_aggregation",
        goal="Compact completed task results into concise response-ready context.",
        role_boundary="Only summarize completed evidence. Do not execute work, review tasks, or mutate task state.",
        success_criteria="Aggregated summary of completed task results with artifacts and verification evidence.",
    ),
    "analysis_effort": NodeContract(
        node_id="analysis_effort",
        role_boundary="Only schedule the next analysis effort. Do not execute work or mutate task state.",
    ),
    "information_digester": NodeContract(
        node_id="information_digester",
        role_boundary="Only gather and digest context. Do not create tasks, execute work, or write deliverables.",
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


def phase_tool_names(
    node_id: str,
    tool_names: set[str],
    phase: LifecyclePhase,
) -> set[str]:
    """Return tools exposed exclusively in one lifecycle phase."""
    contract = get_node_contract(node_id)
    plan_tools = {"task_review_plan"} if node_id == "result_reviewer" else set()
    commit_tools = set(contract.required_tools)
    for group in contract.any_of_tools:
        commit_tools.update(group)
    all_commit_tools: set[str] = set()
    for registered in _NODE_CONTRACTS.values():
        all_commit_tools.update(registered.required_tools)
        for group in registered.any_of_tools:
            all_commit_tools.update(group)
    action_tools = tool_names - all_commit_tools - plan_tools - {"terminate"}
    if phase == LifecyclePhase.PLAN:
        return plan_tools & tool_names
    if phase == LifecyclePhase.ACTION:
        if node_id == "result_reviewer" and action_tools:
            return action_tools
        return action_tools | (commit_tools & tool_names)
    if phase == LifecyclePhase.COMMIT:
        return commit_tools & tool_names
    if phase == LifecyclePhase.TERMINATE:
        return tool_names
    return set()


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
    for nc in _NODE_CONTRACTS.values()
    if nc.required_tools
}

#: Any-of tool groups per node (replaces any_of_by_node dict).
ANY_OF_TOOLS_BY_NODE: dict[str, frozenset[frozenset[str]]] = {
    nc.node_id: nc.any_of_tools for nc in _NODE_CONTRACTS.values() if nc.any_of_tools
}


def _build_recovery_chains() -> dict[str, tuple[str, ...]]:
    """Derive recovery prerequisite chains from contracts (replaces _RECOVERY_CHAINS).

    For each lifecycle node, the chain is: required_tools (sorted) + the
    early_stop_tool (preferred representative of any-of). We only include ONE
    tool per any-of group (the
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
        chains[nc.node_id] = tuple(tools)
    return chains


#: Recovery prerequisite chains (replaces _RECOVERY_CHAINS class attr).
RECOVERY_CHAINS: dict[str, tuple[str, ...]] = _build_recovery_chains()


def _build_recovery_tool_map() -> dict[str, tuple[str, ...]]:
    """Derive the recovery tool candidate map from contracts.

    For each node, list all tools that could satisfy the contract (required +
    any-of flattened + additional_recovery_tools). Used by
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
        if tools:
            tool_map[nc.node_id] = tuple(tools)
    return tool_map


#: Recovery tool candidates per node (replaces recovery_tool_map dict).
RECOVERY_TOOL_MAP: dict[str, tuple[str, ...]] = _build_recovery_tool_map()
