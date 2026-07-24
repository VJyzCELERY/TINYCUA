"""Concrete worker-mode task nodes."""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.node import ProcessNode
from tinycua.loops.node_guidance import (
    _RESULT_REVIEWER_CONTINUATION,
    _RESULT_REVIEWER_INSTRUCTION,
    build_reviewer_tool_guidance,
)
from tinycua.loops.session_context_query import find_latest_entry
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session_context_entry import entry_content
from tinycua.models.task import (
    AggregatedResult,
    TaskResult,
    TaskStatus,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike
    from tinycua.models.session import Session
    from tinycua.models.task import Task, TaskStateStore


# Effort-profiled shrink thresholds (Milestone 4): higher effort → lower
# threshold (more aggressive shrink trigger). The LLM still decides what to
# merge/delete — this just triggers the shrink-prompt.
_SHRINK_THRESHOLDS: dict[str, int] = {
    "none": 99,  # never trigger at none effort
    "low": 15,   # rarely trigger
    "medium": 12,
    "high": 8,   # proactively trigger
}


def shrink_threshold_for_effort(effort: str) -> int:
    """Return the shrink threshold for the given worker effort level.

    Higher effort → lower threshold (more aggressive shrink trigger).
    The LLM still decides what to merge/delete — no hard pruning.

    Args:
        effort: Worker effort level (none/low/medium/high).

    Returns:
        The pending-children threshold above which the shrink-prompt fires.
    """
    return _SHRINK_THRESHOLDS.get(effort, 12)


_TASK_ANALYZER_INSTRUCTION = (
    "You are the TaskAnalyzer. You decompose or refine the roadmap. Before "
    "decomposing, you may explore (web_search, fetch_url, read_file, "
    "list_files, search_files, run_shell) to ground your plan in current "
    "reality — especially for research tasks, verify what entities are "
    "current today instead of assuming from prior knowledge. You do not "
    "execute the task or produce the deliverable — that is the "
    "TaskExecutor's job. Inspect the roadmap. If the active task needs "
    "subtasks, identify the needed structural change. Return a concise action "
    "summary after exploring; the next lifecycle phase will expose the state "
    "mutation. Do not execute the task itself."
)
_TASK_ANALYZER_CONTINUATION = (
    "Based on the roadmap and mission context above, explore first "
    "(web_search/fetch_url/read_file/run_shell) when the task involves a "
    "fast-moving domain (research, current state of tech, models, "
    "frameworks) so your decomposition targets what is current today. "
    "Then summarize the needed structural change. If previous tasks already write to "
    "the report file, do not create a final 'write report' task — "
    "decompose it as 'review and reorganize the existing deliverable file' instead."
)
_TASK_ANALYZER_LOCAL_REPLAN_CONTINUATION = (
    "Refine only the active local region. Explore the local region "
    "(read_file/run_shell/search_files) if it helps you understand the "
    "current task before refining. If the existing plan is correct and "
    "the task failed due to execution (not planning), summarize that the plan "
    "is unchanged so the runtime can skip re-execution. If the plan is wrong, "
    "summarize the local structural change needed. Do "
    "not decompose the root roadmap from a local replan."
)

_TASK_ASSESSOR_UPFRONT_INSTRUCTION = (
    "You are the TaskAssessor for the upfront analysis-effort decomposition loop. "
    "You assess decomposition readiness. You may explore (web_search, "
    "fetch_url, read_file, run_shell) to verify whether the roadmap covers "
    "current reality — especially for research tasks, check that the tasks "
    "target current entities, not stale assumptions. You do not execute "
    "tasks or mutate task state. Inspect the whole roadmap and select "
    "unfinished tasks that are complex enough to warrant further "
    "decomposition. Identify duplicate, overlapping, obsolete, or invalid unfinished "
    "work and hand off the specific task IDs to prune, merge, cancel, or supersede "
    "before any new decomposition. "
    "Use read-only assessment and summarize which tasks need analysis and why. "
    "Be concise and do not repeat upstream context."
)
_TASK_ASSESSOR_UPFRONT_CONTINUATION = (
    "Based on the whole roadmap above, assess decomposition readiness across "
    "the roadmap. Explore (web_search/fetch_url/read_file/run_shell) to "
    "verify the roadmap targets current reality for research tasks. Summarize "
    "selected task IDs and a payload.recommendations list of {task_ids, action, "
    "rationale} for any structural follow-up; action is decompose, shrink, update, "
    "retain, or add. Include constraints, or state that no further upfront "
    "decomposition is useful."
)
_TASK_ASSESSOR_LOCAL_REPLAN_INSTRUCTION = (
    "You are the TaskAssessor for a ResultReviewer-requested local replan. "
    "Inspect the active task and nearby roadmap context to decide whether "
    "that local region needs refinement before execution continues. You may "
    "explore the local region (read_file, run_shell, search_files) to "
    "understand it. Do not reassess the whole roadmap, do not execute "
    "tasks, and do not discuss execution tools. Use read-only assessment and "
    "summarize the local recommendation. Do not mutate task state."
)
_TASK_ASSESSOR_LOCAL_REPLAN_CONTINUATION = (
    "Based on the active task and local roadmap region above, assess whether "
    "the reviewed task needs local decomposition or planning metadata updates. "
    "Explore the local region if it helps your assessment. Summarize the local "
    "assessment, selected decomposition target, blocked planning gap, or that "
    "no local replan is useful."
)

_TASK_EXECUTOR_INSTRUCTION = (
    "You are the TaskExecutor. You execute the active task; you do not "
    "review, decompose, or curate other tasks. Explore the workspace and "
    "task state first (read_file, list_files, search_files, web_search, "
    "fetch_url) before making changes — plan and analyze before you act. "
    "You MUST use tools for workspace changes, inspection, commands, "
    "Python, research, or verification. Preserve explicit user constraints "
    "from the work order. Do not write a plan. Do not describe what you will "
    "do — "
    "use the tools and "
    "return a concise action summary. Report only the active task's outcome."
)
_TASK_EXECUTOR_CONTINUATION = (
    "Based on the active task above, explore the current state (read_file/"
    "list_files/search_files/web_search) before making changes. Then use "
    "tools to complete it. Summarize what changed, was found, or blocked; do "
    "not keep repeating read/list inspection. Report only the active task's "
    "outcome."
)

_RESULT_REVIEWER_INSTRUCTION = _RESULT_REVIEWER_INSTRUCTION  # re-exported from node_guidance
_RESULT_REVIEWER_CONTINUATION = _RESULT_REVIEWER_CONTINUATION  # re-exported from node_guidance

_RESULT_AGGREGATION_INSTRUCTION = (
    "You are the ResultAggregation node. You act as a compaction layer: "
    "summarize completed task results, artifacts, and verification evidence "
    "concisely. You may explore task results (read_file, list_files, "
    "run_shell, task_inspect) to verify or enrich claims in the task "
    "results before aggregating — but do not re-research or re-execute the "
    "work. Do not include Python reprs or duplicate upstream context."
)
_RESULT_AGGREGATION_CONTINUATION = (
    "Based on accepted task results above, explore the task results "
    "(read_file/list_files/run_shell/task_inspect) to verify claims if "
    "needed, then aggregate the Worker result into concise response-ready "
    "context with artifacts and verification evidence."
)

_ANALYSIS_EFFORT_INSTRUCTION = "Deterministic effort controller. No LLM call required."
_ANALYSIS_EFFORT_CONTINUATION = ""


class TinyCUATaskAnalyzerNode(ProcessNode):
    """Analyze or refine task structure."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _TASK_ANALYZER_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the task analyzer node."""
        mode = str(config.metadata.get("task_analyzer_mode", "task_creation"))
        continuation = (
            _TASK_ANALYZER_LOCAL_REPLAN_CONTINUATION
            if mode == "local_replan"
            else _TASK_ANALYZER_CONTINUATION
        )
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=continuation,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build analyzer continuation with current task snapshot."""
        base = super().build_continuation(session)
        if session is None:
            return base
        mode = str(self.config.metadata.get("task_analyzer_mode", "task_creation"))
        if mode == "local_replan":
            region = _local_task_region(session)
            replan_reason = str(self.config.metadata.get("replan_reason", ""))
            reason_prefix = f"{replan_reason}\n\n" if replan_reason else ""
            return f"{reason_prefix}Local task region for replan:\n{_render_local_region_markdown(region)}\n\n{base}"
        mission = _render_mission_block(session)
        prefix = f"{mission}\n\n" if mission else ""
        return f"{prefix}Roadmap:\n{session.task_store.render_markdown()}\n\n{base}"

    def build_tool_system_prompt(self, resolved_tools: list[Any] | None = None) -> str:
        """Behavioral guidance keyed on present analyzer tools (FR-005)."""
        names = {getattr(tool, "name", "") for tool in (resolved_tools or [])}
        if "terminate" in names:
            return "Tool guidance: Call terminate now."
        commit_tools = names.intersection(
            {"task_create", "task_decompose", "task_shrink", "task_update"}
        )
        if commit_tools:
            guidance = "Tool guidance: Commit the planned structural change with " + ", ".join(sorted(commit_tools)) + "."
            if "task_shrink" in commit_tools:
                guidance += (
                    " Review every TaskAssessor recommendation and decide whether "
                    "task_shrink, another available structural tool, or retaining the "
                    "current plan addresses it. Do not change tasks merely because "
                    "they are recommended."
                )
            if (
                "task_update" in commit_tools
                and self.config.metadata.get("task_analyzer_mode") == "local_replan"
            ):
                guidance += " Use metadata plan_unchanged=true when the plan needs no change."
            return guidance
        if "terminate" in names:
            return "Tool guidance: Call terminate now."
        if not names.intersection({"task_inspect", "web_search", "fetch_url", "read_file", "list_files", "search_files", "run_shell"}):
            return ""
        return (
            "Tool guidance: use task_inspect to read state when available. Explore first "
            "(web_search/fetch_url/read_file/list_files/search_files/"
            "run_shell) to ground your decomposition in current reality, especially "
            "for research tasks. Do not execute the task itself."
        )

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Skip re-execution when the analyzer confirmed the plan is unchanged.

        FR-051: in a local replan, when the analyzer sets
        ``metadata.plan_unchanged`` on the active task (via ``task_update``),
        the queued executor is removed — the plan did not change, so
        re-execution would only duplicate work. The reviewer is kept so it
        can re-judge the existing result. Only fires in ``local_replan``
        mode; the upfront analysis loop is unaffected.
        """
        super().on_complete(queue, response)
        mode = str(self.config.metadata.get("task_analyzer_mode", "task_creation"))
        if mode != "local_replan":
            return
        if self.session is None:
            return
        active = self.session.task_store.get_active_task()
        if active is None or not active.metadata.get("plan_unchanged"):
            return
        # Remove the next queued task_executor (if any) — keep the reviewer.
        # ponytail: linear scan is fine, the queue is short (≤4 after replan).
        removed = False
        new_items = []
        for node in queue.items:
            if not removed and node.node_id == "task_executor":
                removed = True
                continue
            new_items.append(node)
        queue.items = new_items
        logger.info(
            "plan_unchanged task_id=%s — skipping executor re-run, "
            "reviewer will re-judge the existing result",
            active.task_id,
        )


def _local_task_region(session: Session) -> dict:
    """Return a compact active-task region for local replan prompts."""
    store = session.task_store
    active = store.get_active_task()
    if active is None:
        return {"active_task": None, "children": [], "siblings": []}
    children = [store.tasks[child_id] for child_id in active.children]
    siblings = []
    if active.parent_id and active.parent_id in store.tasks:
        parent = store.tasks[active.parent_id]
        siblings = [
            store.tasks[child_id]
            for child_id in parent.children
            if child_id != active.task_id and child_id in store.tasks
        ]
    return {
        "active_task": {
            "task_id": active.task_id,
            "title": active.title,
            "status": active.status.value,
            "description": active.description,
            "metadata": active.metadata,
            "result": active.result.summary if active.result else None,
            "reviewer_decisions": active.reviewer_decisions,
        },
        "children": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status.value,
                "result": task.result.summary if task.result else None,
            }
            for task in children
        ],
        "siblings": [
            {
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status.value,
                "result": task.result.summary if task.result else None,
            }
            for task in siblings
        ],
    }


def _task_context_snapshot(session: Session) -> dict:
    """Return unified task context without stale unfinished parent aggregates."""
    return _task_context_snapshot_from_store(session.task_store)


def _task_context_snapshot_from_store(store) -> dict:
    """Store-based variant of ``_task_context_snapshot`` (no Session needed).

    Returns a snapshot with unfinished-parent aggregates nulled out so the
    renderer doesn't show stale "Completed from child task results" summaries
    on parents whose children aren't all done yet.
    """
    snapshot = store.snapshot()
    tasks = snapshot.get("tasks", {})
    if not isinstance(tasks, dict):
        return snapshot
    for task_data in tasks.values():
        if not isinstance(task_data, dict):
            continue
        if task_data.get("children") and task_data.get("status") != "completed":
            task_data["result"] = None
    return snapshot


def _render_task_tree_markdown(snapshot: dict) -> str:
    """Render task tree snapshot as a numbered post-order list for the LLM.

    Execution starts at the DFS left-most leaf and works up/right
    (``next_unfinished_leaf``), so the roadmap is printed in execution order:
    line 1 is the first task worked on, the root (the final goal) is printed
    last in the header. The list is numbered 1..N (root excluded) and the
    numbers match ``TaskStateStore.task_number_map`` so the agent can refer to
    a task by its number instead of a hallucination-prone UUID. Distinct from
    the user-facing ``render_task_tree`` (which uses ``Task [status] title``).
    """
    tasks = snapshot.get("tasks", {})
    root_id = snapshot.get("root_task_id", "")
    active_id = snapshot.get("active_task_id", "")

    lines: list[str] = []
    if root_id:
        root = tasks.get(root_id, {})
        # Root is the goal, not a work item — no status marker on it.
        lines.append(f"Root (goal): {root.get('title', root_id)} (id={root_id})")
    if active_id and active_id != root_id:
        active = tasks.get(active_id, {})
        lines.append(f"Active: {active.get('title', active_id)} (id={active_id})")
    lines.append("Task list (in execution order, numbered):")
    lines.append("")

    counter = 0

    def _render_task(task_id: str) -> None:
        nonlocal counter
        task = tasks.get(task_id, {})
        if not task:
            return
        # Post-order: children first (left-most leaf becomes line 1).
        for child_id in task.get("children", []):
            _render_task(child_id)
        if task_id == root_id:
            return  # root is the goal header, not a numbered work item
        counter += 1
        status = task.get("status", "pending")
        title = task.get("title", task_id)
        marker = " ✓" if status == "completed" else ""
        lines.append(f"{counter}. [{status}] {title} (id={task_id}){marker}")
        result = task.get("result")
        if isinstance(result, dict) and result.get("summary"):
            summary = str(result["summary"])
            lines.append(f"   Result: {summary}")

    # Post-order traversal from root; root itself is not emitted as a list row.
    if root_id:
        _render_task(root_id)

    return "\n".join(lines)


def _render_local_region_markdown(region: dict) -> str:
    """Render local task region as concise markdown with full result summaries.

    The local replan region is scoped to the active task + its children +
    siblings, so the token budget is small. Full result summaries (no
    truncation) are shown for completed tasks so the assessor/analyzer can
    see exactly what was found and decide whether the region needs
    refinement — a 200-char truncation could hide the very detail that
    determines "does this region need replanning?"
    """
    lines: list[str] = []
    active = region.get("active_task")
    if active:
        lines.append(f"Active: {active.get('title', 'unknown')} [{active.get('status', '?')}]")
        active_result = active.get("result")
        if active_result:
            lines.append(f"  Result: {active_result}")
    children = region.get("children", [])
    if children:
        lines.append("Subtasks:")
        for child in children:
            line = f"  - [{child.get('status', '?')}] {child.get('title', '?')}"
            child_result = child.get("result")
            if child_result:
                line += f" — {child_result}"
            lines.append(line)
    siblings = region.get("siblings", [])
    if siblings:
        lines.append("Sibling tasks:")
        for sib in siblings:
            line = f"  - [{sib.get('status', '?')}] {sib.get('title', '?')}"
            sib_result = sib.get("result")
            if sib_result:
                line += f" — {sib_result}"
            lines.append(line)
    return "\n".join(lines) if lines else str(region)


def _render_completed_sibling_results(store: TaskStateStore, active: Task) -> list[str]:
    """Render completed sibling result summaries for the executor context.

    Returns the lines for the 'Completed Sibling Results' section, or an
    empty list if the active task has no completed siblings.
    """
    if not active.parent_id or active.parent_id not in store.tasks:
        return []
    parent = store.tasks[active.parent_id]
    completed_siblings = []
    for child_id in parent.children:
        if child_id == active.task_id:
            continue
        child = store.tasks.get(child_id)
        if child and child.status == TaskStatus.COMPLETED and child.result:
            completed_siblings.append(child)
    if not completed_siblings:
        return []
    lines = ["", "## Completed Sibling Results"]
    lines.append(
        "Previous tasks under the same parent completed with these "
        "findings. Use this context — do not re-research what was "
        "already found."
    )
    for sib in completed_siblings:
        summary = sib.result.summary or sib.result.content
        lines.append(f"### {sib.title}")
        lines.append(summary.strip() if summary else "(no summary)")
        lines.append("")
    return lines


def _render_active_task_work_order(session: Session) -> str:
    """Render the active task as a clear executor work order."""
    store = session.task_store
    active = store.get_active_task()
    if active is None:
        return "## Current State\nNo active task."
    parent_title = ""
    if active.parent_id and active.parent_id in store.tasks:
        parent_title = store.tasks[active.parent_id].title
    lines = [
        "## Current State",
        f"- Active task id: `{active.task_id}`",
        f"- Status: `{active.status.value}`",
        f"- Task: {active.title}",
    ]
    if parent_title:
        lines.append(f"- Parent task: {parent_title}")
    if active.description.strip():
        lines.append(f"- Description: {active.description.strip()}")
    if active.result is not None:
        lines.extend(
            [
                "",
                "## Existing Result",
                active.result.summary.strip() or active.result.content.strip(),
            ]
        )
    clauses = store.unmet_acceptance_clauses(active)
    unmet = store.unmet_acceptance_clauses()
    if clauses or unmet:
        lines.extend(["", "## Acceptance Clauses"])
        if clauses:
            lines.append("Active task coverage:")
            lines.extend(f"- {clause['text']}" for clause in clauses)
        other_unmet = [clause for clause in unmet if clause not in clauses]
        if other_unmet:
            lines.append("Unmet root clauses:")
            lines.extend(f"- {clause['text']}" for clause in other_unmet)
    if active.reviewer_decisions:
        lines.append("")
        lines.append("## Past Review Feedback")
        for decision in active.reviewer_decisions[-3:]:
            lines.append(
                f"- {decision.get('decision', 'unknown')}: "
                f"{decision.get('rationale', '')}"
            )
    # Completed Sibling Results (Milestone 8 Stream A): surface full result
    # summaries of completed direct siblings so the executor sees what
    # previous tasks found.
    lines.extend(_render_completed_sibling_results(store, active))
    context = str(active.metadata.get("context", "")).strip()
    if context:
        lines.extend(["", "## Useful Prior Context", context])
    request_contract = _render_request_contract(session)
    if request_contract:
        lines.extend(["", request_contract])
    lines.extend(
        [
            "",
            "## What Needs To Be Done",
            "Complete this active task only. Use workspace, shell, Python, or "
            "research tools when they provide evidence. Do not just plan.",
            "If writing to a file that previous tasks already wrote to (e.g. "
            "the deliverable file), use `read_file` first to check existing content, then "
            "`append_file` or `str_replace` to add your section. Do NOT "
            "overwrite the entire file unless this is the first task writing "
            "to it.",
            "",
            "## Success Criteria",
            "- At least one action/research/file/shell tool result supports success.",
            "- Summarize the evidence and any specific blocker for the commit phase.",
        ]
    )
    return "\n".join(lines)


def _render_request_contract(session: Session) -> str:
    """Render original request and constraints for downstream task prompts.

    Derives the original request and constraints from the most recent
    ``DigestedInformation`` in session_context only. Does NOT fall back to
    raw ``input_context`` — the canonical mission (FR-001) is the single
    source for the original request, rendered via ``_render_mission_block``.
    This keeps the executor/reviewer scoped: they see the digested contract,
    not the raw user turn.
    """
    original = ""
    constraints: list[str] = []
    content = find_latest_entry(session, DigestedInformation)
    if content is not None:
        original = content.original_query or original
        constraints = list(content.constraints)
    if not original and not constraints:
        return ""
    lines = ["## Original user request"]
    if original:
        lines.append(original)
    if constraints:
        lines.append("## Hard constraints")
        lines.extend(f"- {constraint}" for constraint in constraints if constraint)
    return "\n".join(lines)


def _render_mission_block(session: Session) -> str:
    r"""Render a compact canonical mission block from the root task.

    The mission is the single canonical "goal" carried with the task tree so
    every worker-internal node sees the same goal without inheriting the full
    session context. See FR-003.

    Structured as ``{context}\n{query}``: the InformationDigester's
    comprehensive research (``mission_context`` + ``mission_key_points``)
    appears first as context, followed by the original request and hard
    constraints. Empty sections are omitted (no empty headers). This gives
    downstream planning/review nodes the first-layer exploration findings
    so they don't anchor on training-data priors (e.g. "2024-2025" for a
    "current" research task).

    Returns an empty string when no mission is stored (no-op).
    """
    store = session.task_store
    if store.root_task_id is None or store.root_task_id not in store.tasks:
        return ""
    root = store.tasks[store.root_task_id]
    mission = str(root.metadata.get("mission", "") or "").strip()
    mission_context = str(root.metadata.get("mission_context", "") or "").strip()
    key_points = root.metadata.get("mission_key_points", [])
    if not isinstance(key_points, list):
        key_points = []
    key_points = [str(point).strip() for point in key_points if str(point).strip()]
    constraints = root.metadata.get("inherited_constraints", [])
    if not isinstance(constraints, list):
        constraints = []
    constraints = [str(c).strip() for c in constraints if str(c).strip()]
    if not (mission or mission_context or key_points or constraints):
        return ""
    lines = [
        "## Current Mission — Context Only",
        "This is the overall workflow objective, not your assigned task. Use it "
        "only to understand the context for your delegated role.",
    ]
    if mission_context:
        lines.append(mission_context)
    if key_points:
        lines.append("Key findings:")
        lines.extend(f"- {point}" for point in key_points)
    if mission:
        lines.append(f"Original request: {mission}")
    if constraints:
        lines.append("Hard constraints:")
        lines.extend(f"- {constraint}" for constraint in constraints)
    return "\n".join(lines)


class TinyCUATaskAssessorNode(ProcessNode):
    """Assess the task tree for decomposition readiness."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str | None = None,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the task assessor node."""
        mode = str(config.metadata.get("task_assessor_mode", "upfront_decomposition"))
        if instruction is None:
            instruction = (
                _TASK_ASSESSOR_LOCAL_REPLAN_INSTRUCTION
                if mode == "local_replan"
                else _TASK_ASSESSOR_UPFRONT_INSTRUCTION
            )
        continuation = (
            _TASK_ASSESSOR_LOCAL_REPLAN_CONTINUATION
            if mode == "local_replan"
            else _TASK_ASSESSOR_UPFRONT_CONTINUATION
        )
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=continuation,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build assessor continuation with the full task-tree snapshot."""
        base = super().build_continuation(session)
        if session is None:
            return base
        mode = str(self.config.metadata.get("task_assessor_mode", "upfront_decomposition"))
        mission = _render_mission_block(session)
        prefix = f"{mission}\n\n" if mission else ""
        if mode == "local_replan":
            return (
                f"{prefix}Local roadmap region for reviewer-requested replan:\n"
                f"{_render_local_region_markdown(_local_task_region(session))}\n\n{base}"
            )
        return (
            f"{prefix}Roadmap:\n{session.task_store.render_markdown()}\n\n"
            f"{base}"
        )

    def build_tool_system_prompt(self, resolved_tools: list[Any] | None = None) -> str:
        """Behavioral guidance keyed on present assessor tools (FR-005)."""
        names = {getattr(tool, "name", "") for tool in (resolved_tools or [])}
        if "terminate" in names:
            return "Tool guidance: Call terminate now."
        if "node_handoff" in names:
            return (
                "Tool guidance: Commit node_handoff with payload decision='analyze' "
                "and selected_task_ids, or decision='ready' and selected_task_ids=[]."
            )
        if not names.intersection({"task_inspect", "web_search", "fetch_url", "read_file", "run_shell"}):
            return ""
        return (
            "Tool guidance: use task_inspect for read-only assessment when available. "
            "Explore (web_search/fetch_url/read_file/run_shell) to verify "
            "the roadmap targets current reality for research tasks. Do not mutate task state."
        )

class TinyCUATaskExecutorNode(ProcessNode):
    """Execute or dispatch task work."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _TASK_EXECUTOR_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the task executor node."""
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=_TASK_EXECUTOR_CONTINUATION,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build executor continuation with active task and unified context."""
        base = super().build_continuation(session)
        if session is None:
            return base
        active = session.task_store.get_active_task()
        if active is None:
            return base
        workspace_dir = None
        if session.session_config is not None and session.session_config.workspace_dir:
            workspace_dir = str(session.session_config.workspace_dir)
        mission = _render_mission_block(session)
        mission_prefix = f"{mission}\n\n" if mission else ""
        # Child Verification Gate: when the active task is a parent (has
        # children), the executor must verify that the children's combined
        # work achieves the parent's goal. Only DIRECT children are listed —
        # grandchildren were already verified by the child's own gate.
        verification_note = ""
        if active.children:
            child_lines = []
            for child_id in active.children:
                child = session.task_store.tasks.get(child_id)
                if child:
                    line = f"  - [{child.status.value}] {child.title}"
                    if child.result and child.result.summary:
                        line += f" — {child.result.summary}"
                    child_lines.append(line)
            verification_note = (
                "\n## Child Task Verification Gate\n"
                "This is a PARENT task with completed child tasks. For this "
                "task to be approved, all child tasks below must remain "
                "completed and their results must still be valid. Verify "
                "integration — run tests, check the app starts, confirm "
                "endpoints are wired. Fix issues if needed. Do NOT re-execute "
                "the children.\n\n"
                "Child tasks (direct children only):\n"
                + "\n".join(child_lines)
                + "\n"
            )
        path_note = (
            f"Workspace root: {workspace_dir or 'not configured'}\n"
            "You are already inside the workspace root — file tools and "
            "shell commands run from here. Use relative paths only; do not "
            "prepend the workspace directory name or use absolute paths."
        )

        return (
            f"{mission_prefix}{_render_active_task_work_order(session)}\n"
            f"{verification_note}"
            f"{path_note}\n"
            "Shell discipline: commands run under /bin/sh; do not rely on "
            "shell-specific brace expansion such as 'mkdir -p {a,b}'. Use "
            "explicit POSIX-safe paths/commands instead.\n"
            f"\n## Roadmap\n{session.task_store.render_markdown()}\n\n{base}"
        )

    def _artifacts_from_tool_results(self, tool_results: list[dict]) -> list[dict]:
        """Extract artifact references from file-writing tool results."""
        artifacts = []
        for item in tool_results:
            output = item.get("output") if isinstance(item, dict) else None
            if item.get("name") not in {"write_file", "str_replace", "append_file"} or not isinstance(output, dict):
                continue
            if output.get("success") and output.get("path"):
                artifacts.append(
                    {
                        "path": output["path"],
                        "kind": "file",
                        "metadata": {"tool_name": item.get("name", "write_file")},
                    }
                )
        return artifacts

    def build_tool_system_prompt(self, resolved_tools: list[Any] | None = None) -> str:
        """Behavioral guidance keyed on present executor tools (FR-005)."""
        names = {getattr(tool, "name", "") for tool in (resolved_tools or [])}
        if "terminate" in names:
            return "Tool guidance: Call terminate now."
        lines: list[str] = []
        if "str_replace" in names and "write_file" in names:
            lines.append(
                "Prefer str_replace for targeted edits, append_file for additions. "
                "Use write_file only for new files or full rewrites."
            )
        if "search_files" in names:
            lines.append("Use search_files instead of run_shell grep for content search.")
        if "task_result_update" in names:
            lines.append("Your final action MUST call task_result_update with the outcome report.")
        if not lines:
            return ""
        return "Tool guidance: " + " ".join(lines)


class TinyCUAResultReviewerNode(ProcessNode):
    """Review task execution results."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _RESULT_REVIEWER_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the result reviewer node."""
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=_RESULT_REVIEWER_CONTINUATION,
            is_terminal=is_terminal,
        )

    def _reviewer_context_blocks(self, task: Task, session: Session) -> str:
        """Assemble active-task review context (child gate and failure note)."""
        # FR-021: surface the failure count as SOFT context so the reviewer —
        # which still LLM-decides — can weigh replan over retry when a task has
        # bounced many times. Not a forced decision; just visible signal.
        failure_count = task.failure_count
        failure_note = ""
        if failure_count >= 5:
            failure_note = (
                f"\nNote: this task has been sent back for rework "
                f"{failure_count} times. Repeated identical retries are unlikely "
                f"to succeed; consider replan (the plan may be wrong) rather than "
                f"another retry.\n"
            )
        # Child Verification Gate: when reviewing a parent task (has children),
        # surface the direct children so the reviewer knows it's a verification
        # review, not a leaf review. Only direct children — grandchildren were
        # already verified by the child's own gate.
        child_gate = ""
        if task.children:
            child_lines = []
            for child_id in task.children:
                child = session.task_store.tasks.get(child_id)
                if child:
                    line = f"  - [{child.status.value}] {child.title}"
                    if child.result and child.result.summary:
                        line += f" — {child.result.summary}"
                    child_lines.append(line)
            child_gate = (
                "\n## Child Task Verification Gate\n"
                "This is a PARENT task. For this task to be approved, all "
                "child tasks below must remain completed and their results "
                "must still be valid. Verify integration — do not re-execute "
                "the children.\n\n"
                "Child tasks (direct children only):\n"
                + "\n".join(child_lines)
                + "\n"
            )
        return f"{child_gate}{failure_note}"

    def _failsafe_result_content(self, task: Task, session: Session) -> str:
        """Failsafe transcript when the executor left no result report."""
        transcript_lines = []
        for entry in session.session_context:
            content = entry_content(entry)
            role = entry.get("role", "") if isinstance(entry, dict) else getattr(entry, "role", "")
            if role and content:
                transcript_lines.append(f"[{role}] {content}")
        return "(No result report from executor)\n\nExecutor transcript:\n" + "\n".join(transcript_lines[-10:])

    def build_continuation(self, session: Session | None = None) -> str:
        """Build reviewer continuation with latest result and unified context."""
        base = super().build_continuation(session)
        if session is None:
            return base
        task = self._task_to_review()
        if task is None:
            return base
        # Primary review target: the executor's outcome report
        result_content = task.result.content if task.result is not None else ""
        if not result_content.strip():
            result_content = self._failsafe_result_content(task, session)
        mission = _render_mission_block(session)
        mission_prefix = f"{mission}\n\n" if mission else ""
        context_blocks = self._reviewer_context_blocks(task, session)
        clauses = session.task_store.unmet_acceptance_clauses(task)
        clause_block = ""
        if clauses:
            clause_block = "Acceptance clauses under review:\n" + "\n".join(
                f"- {clause['text']}" for clause in clauses
            )
        return (
            f"{mission_prefix}Task under review: {task.task_id} — {task.title}\n"
            f"Task status: {task.status.value}\n"
            f"Outcome report: {result_content}\n"
            f"{_render_request_contract(session)}\n"
            f"Unified task context:\n{session.task_store.render_markdown()}\n"
            f"{context_blocks}\n{clause_block}\n{base}"
        )

    def _task_to_review(self):
        """Return the most recent completed task that needs review."""
        if self.session is None:
            return None
        active = self.session.task_store.get_active_task()
        if active is not None and active.result is not None:
            return active
        for task in reversed(list(self.session.task_store.tasks.values())):
            if task.children:
                continue
            if task.result is not None and not task.reviewer_decisions:
                return task
        return active

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Schedule retry, replan, next task, or aggregation from task state."""
        del response
        if self.session is None:
            return
        from tinycua.loops.worker_runtime import WorkerRuntimeController

        terminal_nodes = [node for node in queue.items[1:] if node.is_terminal]
        queue.clear_after_current()
        sc = self.session.session_config
        enable_oq = bool(sc.enable_open_question_review) if sc is not None else False
        replan_threshold = sc.replan_threshold if sc is not None else 5
        WorkerRuntimeController(
            self.session.task_store,
            enable_open_question_review=enable_oq,
            replan_threshold=replan_threshold,
            session=self.session,
        ).schedule_after_review(queue)
        existing_terminal_ids = {
            node.node_id for node in queue.items if node.is_terminal
        }
        for terminal in terminal_nodes:
            if terminal.node_id not in existing_terminal_ids:
                queue.items.append(terminal)
                existing_terminal_ids.add(terminal.node_id)

    def parse_loop_result(
        self,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Clear transient runtime recovery context after accepted successful work."""
        del node_input
        if self.session is None:
            return
        task = self._reviewed_task_from_result(llm_result)
        if task is None or task.result is None or not task.reviewer_decisions:
            return
        if task.result.success:
            task.metadata.pop("runtime_validation_failure", None)

    def _reviewed_task_from_result(self, llm_result: LLMResult):
        """Return the task referenced by task_review_decision tool output."""
        if self.session is None:
            return None
        for item in reversed(llm_result.metadata.get("tool_results", [])):
            if item.get("name") != "task_review_decision":
                continue
            output = item.get("output")
            if not isinstance(output, dict):
                continue
            task_id = output.get("task_id")
            if isinstance(task_id, str) and task_id in self.session.task_store.tasks:
                return self.session.task_store.tasks[task_id]
        return self._task_to_review()

    def build_tool_system_prompt(self, resolved_tools: list[Any] | None = None) -> str:
        """Delegate to the reviewer guidance builder (FR-005, FR-008, FR-056)."""
        return build_reviewer_tool_guidance(resolved_tools)


class TinyCUAResultAggregationNode(ProcessNode):
    """Aggregate task results into worker output."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _RESULT_AGGREGATION_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the result aggregation node."""
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=_RESULT_AGGREGATION_CONTINUATION,
            is_terminal=is_terminal,
        )

    def build_continuation(self, session: Session | None = None) -> str:
        """Build aggregation continuation with completed task evidence as markdown.

        Tasks are listed in reverse execution order (last-completed leaf first,
        root goal last) — most relevant context first.
        """
        base = super().build_continuation(session)
        if session is None:
            return base
        store = session.task_store
        lines: list[str] = []
        # Reverse post-order: last-executed leaf first, root last.
        ordered_ids = list(reversed(store._ordered_ids()))
        # Append root last (it's the goal, not in _ordered_ids).
        if store.root_task_id and store.root_task_id in store.tasks:
            ordered_ids.append(store.root_task_id)
        for task_id in ordered_ids:
            task = store.tasks.get(task_id)
            if task is None or task.result is None:
                continue
            status_mark = " ✓" if task.status.value == "completed" else ""
            lines.append(f"- **{task.title}** [{task.status.value}]{status_mark}")
            summary = task.result.summary or task.result.content
            if summary:
                lines.append(f"  {summary}")
            if task.artifacts:
                paths = [a.get("path", "") for a in task.artifacts if a.get("path")]
                if paths:
                    lines.append(f"  Artifacts: {', '.join(paths)}")
        evidence_block = "\n".join(lines) if lines else "No completed tasks."
        mission = _render_mission_block(session)
        mission_prefix = f"{mission}\n\n" if mission else ""
        return f"{mission_prefix}## Completed Task Evidence\n{evidence_block}\n\n{base}"

    def parse_loop_result(
        self,
        llm_result: LLMResult,
        node_input: NodeInputLike | None,
    ) -> None:
        """Persist aggregation output on the root task."""
        del node_input
        if not self._has_root_task:
            return
        root_id = self.session.task_store.root_task_id
        store = self.session.task_store
        if not store.all_done():
            return
        root = store.tasks[root_id]
        root.result = TaskResult(
            content=llm_result.content or self._summarize_task_results(),
            success=True,
            metadata={"source_node_id": self.node_id},
        )
        root.status = TaskStatus.COMPLETED
        aggregated = self._build_aggregated_result(llm_result.content)
        root.metadata["aggregated_result"] = aggregated.__dict__
        # FR-074: use idempotent_by_identity to avoid duplicating if the
        # orchestration layer's _record_node_output already recorded the
        # same aggregated object. This handles both the direct-call test
        # path (where parse_loop_result is the only recorder) and the
        # production path (where _record_node_output runs first).
        from tinycua.models.session_context_entry import append_output_entry

        append_output_entry(
            self.session, aggregated, self.node_id,
            idempotent_by_identity=True,
        )

    def _summarize_task_results(self) -> str:
        """Summarize child task outputs for aggregation content (reverse execution order)."""
        if self.session is None:
            return "Completed worker roadmap."
        store = self.session.task_store
        parts = []
        for task_id in reversed(store._ordered_ids()):
            task = store.tasks.get(task_id)
            if (
                task
                and task.status == TaskStatus.COMPLETED
                and task.result is not None
                and task.parent_id is not None
            ):
                parts.append(f"{task.title}: {task.result.content}")
        return "\n".join(parts) or "Completed worker roadmap."

    def _build_aggregated_result(self, model_context: str) -> AggregatedResult:
        """Build a response-ready aggregation from roadmap state (reverse execution order)."""
        if not self._has_root_task:
            return AggregatedResult(root_task_id="", final_context=model_context)
        store = self.session.task_store
        task_summaries: list[str] = []
        accepted_results: list[TaskResult] = []
        artifacts: list[dict] = []
        # Reverse post-order: last-executed leaf first, root last.
        ordered_ids = list(reversed(store._ordered_ids()))
        if store.root_task_id and store.root_task_id in store.tasks:
            ordered_ids.append(store.root_task_id)
        for task_id in ordered_ids:
            task = store.tasks.get(task_id)
            if (
                task is None
                or task.status != TaskStatus.COMPLETED
                or task.result is None
            ):
                continue
            task_summaries.append(f"{task.title}: {task.result.summary}")
            accepted_results.append(task.result)
            artifacts.extend(task.artifacts)
        final_context = "\n".join(
            part for part in [model_context.strip(), *task_summaries] if part
        )
        return AggregatedResult(
            root_task_id=store.root_task_id,
            task_summaries=task_summaries,
            accepted_results=accepted_results,
            artifacts=artifacts,
            final_context=final_context,
            response_continuation="Use this aggregated result to answer the user.",
            metadata={"source_node_id": self.node_id},
        )


class TinyCUAAnalysisEffortNode(ProcessNode):
    """Determine analysis effort for worker-mode planning."""

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _ANALYSIS_EFFORT_INSTRUCTION,
        is_terminal: bool = False,
        pass_count: int = 0,
        pass_limit: int | None = None,
    ) -> None:
        """Initialize the analysis effort node."""
        super().__init__(
            node_id,
            config,
            instruction=instruction,
            continuation=_ANALYSIS_EFFORT_CONTINUATION,
            is_terminal=is_terminal,
        )
        self.pass_count = pass_count
        self.pass_limit = pass_limit

    def _configured_pass_limit(self) -> int:
        """Return pass limit from explicit value or session worker effort."""
        if self.pass_limit is not None:
            return self.pass_limit
        effort = "medium"
        if self.session is not None and self.session.session_config is not None:
            effort = getattr(self.session.session_config, "worker_effort", "medium")
        return {"none": 0, "low": 1, "medium": 2, "high": 3}.get(
            str(effort),
            2,
        )

    def run_deterministic(self, queue: NodeQueue) -> LLMResult:
        """Schedule documented effort passes without an LLM call."""
        pass_limit = self._configured_pass_limit()
        if self.session is not None and self.session.task_store.root_task_id is not None:
            root = self.session.task_store.tasks[self.session.task_store.root_task_id]
            root.metadata["analysis_effort_pass_limit"] = pass_limit
            root.metadata["analysis_effort_pass_count"] = self.pass_count

        if self.pass_count < pass_limit:
            next_effort = TinyCUAAnalysisEffortNode(
                node_id="analysis_effort",
                config=create_node_config("analysis_effort", self.config),
                pass_count=self.pass_count + 1,
                pass_limit=pass_limit,
            )
            queue.spawn_after_current(
                [
                    TinyCUATaskAssessorNode(
                        node_id="task_assessor",
                        config=create_node_config("task_assessor", self.config),
                    ),
                    TinyCUATaskAnalyzerNode(
                        node_id="task_analyzer",
                        config=create_node_config(
                            "task_analyzer",
                            self.config,
                            mode="effort_loop_decomposition",
                        ),
                    ),
                    next_effort,
                ]
            )
            content = (
                "Scheduled analysis effort pass "
                f"{self.pass_count + 1} of {pass_limit}."
            )
        else:
            content = f"Analysis effort complete after {pass_limit} pass(es)."

        return LLMResult(content=content, role="assistant")
