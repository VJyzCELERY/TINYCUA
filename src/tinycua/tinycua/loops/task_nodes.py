"""Concrete worker-mode task nodes."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult
from tinycua.loops.node import ProcessNode
from tinycua.loops.mission import _render_mission_block
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
    "low": 15,  # rarely trigger
    "medium": 12,
    "high": 8,  # proactively trigger
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
    "You are the TaskAnalyzer. Produce or refine an actionable roadmap; do not "
    "execute requested work. Use available tools (web_search, fetch_url, read_file, "
    "list_files, search_files, run_shell) only to understand the request, state, "
    "constraints, dependencies, and material uncertainty. Use no more tasks than "
    "needed. Each task must own one "
    "coherent outcome that can be executed and verified independently, with enough "
    "context to act while leaving unsupported implementation choices open. Preserve "
    "explicit constraints and "
    "treat named outputs as required, not exhaustive. Avoid overlap and keep work "
    "governed by one acceptance criterion together. Split materially distinct "
    "concerns when each gives narrower context and independent evidence, even if "
    "sharing a file or deliverable. Keep tightly coupled work; never split "
    "lifecycle-only phases. Commit one appropriate structural decision."
)
_TASK_ANALYZER_CONTINUATION = (
    "Evaluate the current roadmap against the planning criteria above. Remove or "
    "merge redundant work, refine only where an outcome is not independently "
    "actionable, and preserve explicit constraints without prescribing unsupported "
    "implementation details. If the roadmap is already sound, record no structural "
    "change; otherwise commit the smallest supported structural change."
)
_TASK_ANALYZER_LOCAL_REPLAN_CONTINUATION = (
    "Refine only the active local region using the same planning criteria. Use "
    "available tools when evidence is needed. If the region already consists of "
    "coherent, independently actionable outcomes, record no structural change; "
    "otherwise commit the smallest supported local change. Do not decompose the "
    "root roadmap or otherwise restructure it from a local replan."
)

_TASK_ASSESSOR_UPFRONT_INSTRUCTION = (
    "You are the TaskAssessor. Your responsibility is to review roadmap quality. "
    "Do not execute work or mutate task state. Use available tools (web_search, "
    "fetch_url, read_file, run_shell) when evidence is needed. Inspect the whole "
    "roadmap. Each unfinished task should own "
    "one coherent outcome, contain sufficient context, be independently executable "
    "and verifiable, preserve explicit constraints, and leave unsupported "
    "implementation choices open. Select tasks that are vague, redundant, "
    "fragmented, too broad to execute or verify meaningfully, materially overlapping, "
    "or prematurely prescriptive. Do not impose architecture, output layout, tool "
    "choice, a fixed task count, or decomposition merely because a task is large. "
    "Split materially distinct concerns when each gives narrower context and "
    "independent evidence, even if sharing a file or deliverable. Keep tightly "
    "coupled work; never split lifecycle-only phases."
)
_TASK_ASSESSOR_UPFRONT_CONTINUATION = (
    "Review roadmap quality against the criteria above. Decide ready only when the "
    "unfinished work is coherent, actionable, nonredundant, appropriately scoped, "
    "and grounded in available evidence; otherwise select only the task IDs needing "
    "planning refinement and explain the material defect."
)
_TASK_ASSESSOR_LOCAL_REPLAN_INSTRUCTION = (
    "You are the TaskAssessor. Your responsibility is to review the active task's "
    "local roadmap region for a local replan. Do not execute work or mutate task state. Use available "
    "tools (read_file, search_files, run_shell) when evidence is needed. Each "
    "unfinished local task should own one "
    "coherent outcome, contain sufficient context, be independently executable and "
    "verifiable, preserve explicit constraints, and avoid material overlap or "
    "unsupported implementation choices. Select only tasks needing planning "
    "refinement. Do not impose architecture, output layout, tool choice, task count, "
    "or decomposition depth, and do not reassess the whole roadmap. Split materially "
    "distinct concerns when each gives narrower context and independent evidence, "
    "even if sharing a file or deliverable. Keep tightly coupled work; never split "
    "lifecycle-only phases."
)
_TASK_ASSESSOR_LOCAL_REPLAN_CONTINUATION = (
    "Review the active local region against the criteria above. Decide ready with "
    "no selected targets when it is coherent and actionable; otherwise select only "
    "the unfinished local task IDs needing refinement and explain the material "
    "planning defect."
)
_TASK_ASSESSOR_CANCELLATION_INSTRUCTION = (
    "You are the TaskAssessor. Decide whether one newly requested cancellation is "
    "valid. Do not execute or mutate work except through task_assessment_decision. "
    "Approve only when the task and its unfinished descendants are genuinely "
    "unnecessary for the original request and hard constraints, and the parent outcome "
    "remains achievable. Difficulty, a failed approach, or temporary blockage never "
    "justify cancellation. Ready approves; analyze rejects with one blocking finding "
    "on the cancellation target."
)
_TASK_ASSESSOR_CANCELLATION_CONTINUATION = (
    "Assess only the bound cancellation request. Use ready with no findings to approve "
    "it, or analyze with exactly one target-bound finding to reject it for repair."
)

_TASK_EXECUTOR_INSTRUCTION = (
    "You are the TaskExecutor. Execute only the active task; do not review, decompose, "
    "or curate others. Inspect workspace and task state before changes. You MUST use tools for "
    "inspection, changes, commands, research, and verification. Preserve explicit user "
    "constraints. Do not write a plan. Do not describe what you will do; act, then "
    "summarize concisely. "
    "Report only the active task's outcome. Do not intentionally implement pending "
    "sibling outcomes. Work may incidentally satisfy pending outcomes; report the "
    "effect, why it was required, evidence, and whether it appears partially or fully "
    "satisfied, but do not claim pending tasks are complete. Substantial sibling work "
    "is a scope mismatch for reviewer replanning. If the active outcome already exists, "
    "verify it and report no-change success."
)
_TASK_EXECUTOR_CONTINUATION = (
    "Based on the active task above, explore the current state (read_file/"
    "list_files/search_files/web_search) before making changes. Then use "
    "tools to complete it. Summarize what changed, was found, or blocked; do "
    "not keep repeating read/list inspection. Include verified incidental effects "
    "on pending outcomes without marking those tasks complete; report substantial "
    "sibling work as a scope mismatch."
)

_RESULT_REVIEWER_INSTRUCTION = (
    _RESULT_REVIEWER_INSTRUCTION  # re-exported from node_guidance
)
_RESULT_REVIEWER_CONTINUATION = (
    _RESULT_REVIEWER_CONTINUATION  # re-exported from node_guidance
)

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
            if mode in {"local_replan", "cancellation_repair"}
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
        if mode in {"local_replan", "cancellation_repair"}:
            region = _local_task_region(
                session, self.config.metadata.get("replan_task_id")
            )
            replan_reason = str(self.config.metadata.get("replan_reason", ""))
            reason_prefix = f"{replan_reason}\n\n" if replan_reason else ""
            return f"{reason_prefix}Local task region for replan:\n{_render_local_region_markdown(region)}\n\n{base}"
        mission = _render_mission_block(session)
        prefix = f"{mission}\n\n" if mission else ""
        return f"{prefix}Roadmap:\n{session.task_store.render_markdown()}\n\n{base}"

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Insert one cancellation assessment before execution can continue."""
        del response
        if self.session is None:
            return
        if self.config.metadata.get("task_analyzer_mode") == "cancellation_repair":
            return
        requests = self.session.task_store.pending_cancellation_requests()
        if not requests:
            return
        request = requests[0]
        request_id = request["request_id"]
        if any(
            node.config.metadata.get("cancellation_request_id") == request_id
            for node in queue.items[1:]
        ):
            return
        assessor_config = create_node_config(
            "task_assessor", self.config, mode="cancellation_review"
        )
        assessor_config.metadata["cancellation_request_id"] = request_id
        repair_config = create_node_config(
            "task_analyzer", self.config, mode="cancellation_repair"
        )
        repair_config.metadata["cancellation_request_id"] = request_id
        queue.spawn_after_current(
            [
                TinyCUATaskAssessorNode("task_assessor", assessor_config),
                TinyCUATaskAnalyzerNode("task_analyzer", repair_config),
            ]
        )

    def build_tool_system_prompt(self, resolved_tools: list[Any] | None = None) -> str:
        """Behavioral guidance keyed on present analyzer tools (FR-005)."""
        names = {getattr(tool, "name", "") for tool in (resolved_tools or [])}
        if "terminate" in names:
            return "Tool guidance: Call terminate now."
        commit_tools = names.intersection(
            {"task_create", "task_decompose", "task_shrink", "task_update"}
        )
        if commit_tools:
            guidance = (
                "Tool guidance: Commit the planned structural change with "
                + ", ".join(sorted(commit_tools))
                + "."
            )
            if "task_shrink" in commit_tools:
                guidance += (
                    " Review every TaskAssessor recommendation and decide whether "
                    "task_shrink, another available structural tool, or retaining the "
                    "current plan addresses it. Do not change tasks merely because "
                    "they are recommended."
                )
            guidance += (
                " Resolve every selected blocking target on that task or its local "
                "subtree. If retaining a target unchanged, call task_update on it "
                "with a non-empty planning_note. Unrelated changes do not resolve it."
            )
            if (
                "task_update" in commit_tools
                and self.config.metadata.get("task_analyzer_mode") == "local_replan"
            ):
                guidance += (
                    " Use metadata plan_unchanged=true when the plan needs no change."
                )
            if self.config.metadata.get("task_analyzer_mode") == "cancellation_repair":
                guidance += (
                    " Cancellation was rejected. Do not cancel again; repair the "
                    "target through a non-cancellation structural change."
                )
            return guidance
        if "terminate" in names:
            return "Tool guidance: Call terminate now."
        if not names.intersection(
            {
                "task_inspect",
                "web_search",
                "fetch_url",
                "read_file",
                "list_files",
                "search_files",
                "run_shell",
            }
        ):
            return ""
        return (
            "Tool guidance: use task_inspect to read state when available. Explore first "
            "(web_search/fetch_url/read_file/list_files/search_files/"
            "run_shell) only as needed to ground the decomposition in evidence. "
            "Do not execute the task itself."
        )


def _local_task_region(session: Session, task_id: str | None = None) -> dict:
    """Return a compact active-task region for local replan prompts."""
    store = session.task_store
    active = store.tasks.get(task_id) if task_id else store.get_active_task()
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
            }
            for task in siblings
        ],
    }


def _render_prior_planning_resolutions(session: Session) -> str:
    """Render bounded same-task finding/resolution pairs for reassessment."""
    lines = []
    for task in session.task_store.tasks.values():
        finding = task.metadata.get("planning_finding")
        resolution = task.metadata.get("planning_resolution")
        if not isinstance(finding, dict) or not isinstance(resolution, dict):
            continue
        if finding.get("assessment_id") != resolution.get("assessment_id"):
            continue
        finding_text = str(finding.get("finding", "")).strip()[:240]
        resolution_text = str(
            resolution.get("rationale") or resolution.get("summary") or ""
        ).strip()[:240]
        if finding_text and resolution_text:
            lines.append(
                f"- {task.task_id} ({task.title}): finding={finding_text}; "
                f"resolution={resolution_text}"
            )
        if len(lines) == 8:
            break
    if not lines:
        return ""
    return "Prior same-task planning findings and resolutions:\n" + "\n".join(lines)


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


def _render_task_tree_markdown(snapshot: dict, *, include_results: bool = True) -> str:
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
        if include_results and isinstance(result, dict) and result.get("summary"):
            lines.append(f"   Result: {result['summary']}")

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
        lines.append(
            f"Active: {active.get('title', 'unknown')} "
            f"(id={active.get('task_id', '?')}) [{active.get('status', '?')}]"
        )
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


def _render_review_journal(store: TaskStateStore, task: Task) -> list[str]:
    """Render one task's bounded review digest without full rationales."""
    digest = store.review_journal_digest(task.task_id)
    if not digest:
        return []
    lines = ["", "## Execution Review Journal"]
    sections = (
        ("open_findings", "Open findings"),
        ("deferred_findings", "Deferred findings"),
        ("recently_addressed_findings", "Recently addressed findings"),
    )
    for key, title in sections:
        findings = digest.get(key, [])
        if findings:
            lines.append(f"{title}:")
            lines.extend(
                f"- {finding['finding_id']} [{finding['status']}]: {finding['summary']}"
                for finding in findings
            )
    events = digest.get("recent_events", [])
    if events:
        lines.append("Recent review events:")
        lines.extend(
            f"- {event['event_id']} [{event['decision']}]: {event['review_summary']}"
            for event in events
        )
    return lines


def _render_approved_cancellations(store: TaskStateStore) -> str:
    """Render user-visible rationale for top-level approved cancellation requests."""
    lines = []
    for task in store.tasks.values():
        request = task.metadata.get("cancellation_request")
        if (
            task.status == TaskStatus.CANCELLED
            and isinstance(request, dict)
            and request.get("state") == "approved"
            and "cascade_from_task_id" not in request
        ):
            lines.append(f"- {task.title}: {request.get('rationale', '')}")
    return "## Approved cancellations\n" + "\n".join(lines) if lines else ""


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
    clauses = store.acceptance_clauses()
    if clauses:
        lines.extend(["", "## Acceptance Criteria (context)"])
        lines.extend(f"- {clause['text']}" for clause in clauses)
    advisories = active.metadata.get("planning_advisories", [])
    if isinstance(advisories, list):
        rendered_advisories = [
            str(advisory.get("advisory", "")).strip()
            for advisory in advisories[-5:]
            if isinstance(advisory, dict) and str(advisory.get("advisory", "")).strip()
        ]
        if rendered_advisories:
            lines.extend(["", "## Planning advisories"])
            lines.extend(f"- {advisory}" for advisory in rendered_advisories)
    lines.extend(_render_review_journal(store, active))
    context = str(active.metadata.get("context", "")).strip()
    if context:
        lines.extend(["", "## Useful Prior Context", context])
    if active.metadata.get("suggested_mode") == "verify_only":
        lines.extend(
            [
                "",
                "## Suggested execution mode",
                "Validate existing work before making changes. If it already satisfies "
                "the task, report the outcome with task_result_update.",
            ]
        )
    request_contract = _render_request_contract(session)
    if request_contract:
        lines.extend(["", request_contract])
    lines.extend(
        [
            "",
            "## What Needs To Be Done",
            "Complete this active task only. Use workspace, shell, Python, or "
            "research tools when they provide evidence. Do not just plan.",
            "Inspect existing outputs before changing them, preserve valid prior "
            "work, and use the least destructive operation appropriate to the "
            "requested result. Replace an existing artifact only when replacement "
            "is actually required.",
            "",
            "## Success Criteria",
            "- At least one action/research/file/shell tool result supports success.",
            "- Report the outcome as soon as it is known; otherwise summarize what "
            "was done and any specific blocker for commit-only fallback.",
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
    lines = [
        "## Original user request",
        "The original request and hard constraints control if generated task text, "
        "acceptance clauses, roadmap descriptions, or model assumptions conflict.",
    ]
    if original:
        lines.append(original)
    if constraints:
        lines.append("## Hard constraints")
        lines.extend(f"- {constraint}" for constraint in constraints if constraint)
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
            if mode == "cancellation_review":
                instruction = _TASK_ASSESSOR_CANCELLATION_INSTRUCTION
            else:
                instruction = (
                    _TASK_ASSESSOR_LOCAL_REPLAN_INSTRUCTION
                    if mode == "local_replan"
                    else _TASK_ASSESSOR_UPFRONT_INSTRUCTION
                )
            if mode == "final_assessment":
                instruction += (
                    " This is the final assessment after the analysis budget. Ready "
                    "proceeds; analyze records remaining findings as exhausted "
                    "task-local advisories and also proceeds without another analyzer."
                )
        continuation = (
            _TASK_ASSESSOR_CANCELLATION_CONTINUATION
            if mode == "cancellation_review"
            else (
                _TASK_ASSESSOR_LOCAL_REPLAN_CONTINUATION
                if mode == "local_replan"
                else _TASK_ASSESSOR_UPFRONT_CONTINUATION
            )
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
        mode = str(
            self.config.metadata.get("task_assessor_mode", "upfront_decomposition")
        )
        mission = _render_mission_block(session)
        prefix = f"{mission}\n\n" if mission else ""
        prior = _render_prior_planning_resolutions(session)
        prior_prefix = f"{prior}\n\n" if prior else ""
        if mode == "cancellation_review":
            request_id = str(self.config.metadata.get("cancellation_request_id", ""))
            request = next(
                (
                    item
                    for item in session.task_store.pending_cancellation_requests()
                    if item["request_id"] == request_id
                ),
                None,
            )
            if request is None:
                return f"{prefix}Cancellation request is no longer pending.\n\n{base}"
            task = session.task_store.tasks[request["task_id"]]
            affected = [
                session.task_store.tasks[task_id].title
                for task_id in request["affected_task_ids"]
                if task_id in session.task_store.tasks
            ]
            return (
                f"{prefix}Cancellation target: {task.task_id} — {task.title}\n"
                f"Request rationale: {request['rationale']}\n"
                f"Affected unfinished tasks: {', '.join(affected)}\n\n{base}"
            )
        if mode == "local_replan":
            replan_reason = str(self.config.metadata.get("replan_reason", ""))
            reason_prefix = f"{replan_reason}\n\n" if replan_reason else ""
            return (
                f"{prefix}{prior_prefix}{reason_prefix}Local roadmap region for "
                "reviewer-requested replan:\n"
                f"{_render_local_region_markdown(_local_task_region(session, self.config.metadata.get('replan_task_id')))}\n\n{base}"
            )
        return (
            f"{prefix}{prior_prefix}Roadmap:\n"
            f"{session.task_store.render_markdown()}\n\n{base}"
        )

    def build_tool_system_prompt(self, resolved_tools: list[Any] | None = None) -> str:
        """Behavioral guidance keyed on present assessor tools (FR-005)."""
        names = {getattr(tool, "name", "") for tool in (resolved_tools or [])}
        if "terminate" in names:
            return "Tool guidance: Call terminate now."
        if "task_assessment_decision" in names:
            if self.config.metadata.get("task_assessor_mode") == "cancellation_review":
                return (
                    "Tool guidance: assess only the bound cancellation request. Use "
                    "ready with no findings to approve it, or analyze with one finding "
                    "on its target to reject it for repair."
                )
            return (
                "Tool guidance: Commit task_assessment_decision with task-bound "
                "findings and advisories. Analyze requires a blocking finding; ready "
                "has no blocking findings but may include advisories. Include a "
                "concise rationale."
            )
        if not names.intersection(
            {"task_inspect", "web_search", "fetch_url", "read_file", "run_shell"}
        ):
            return ""
        return (
            "Tool guidance: use task_inspect for read-only assessment when available. "
            "Explore (web_search/fetch_url/read_file/run_shell) only when needed "
            "to verify material roadmap assumptions. Do not mutate task state."
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
                "Child tasks (direct children only):\n" + "\n".join(child_lines) + "\n"
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
            f"\n## Roadmap\n"
            f"{_render_task_tree_markdown(_task_context_snapshot(session), include_results=False)}"
            f"\n\n{base}"
        )

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Schedule validated executor results directly when review is disabled."""
        del response
        if self.session is None or getattr(
            self.session.session_config, "review_enabled", True
        ):
            return
        active = self.session.task_store.get_active_task()
        if active is None or active.result is None:
            raise RuntimeError("Executor completed without a validated task result.")
        from tinycua.loops.worker_runtime import WorkerRuntimeController

        terminal_nodes = [node for node in queue.items[1:] if node.is_terminal]
        queue.clear_after_current()
        WorkerRuntimeController(
            self.session.task_store,
            replan_threshold=self.session.session_config.replan_threshold,
            review_enabled=False,
            session=self.session,
        ).schedule_after_execution(queue, active.task_id)
        queue.items.extend(terminal_nodes)

    def _artifacts_from_tool_results(self, tool_results: list[dict]) -> list[dict]:
        """Extract artifact references from file-writing tool results."""
        artifacts = []
        for item in tool_results:
            output = item.get("output") if isinstance(item, dict) else None
            if item.get("name") not in {
                "write_file",
                "str_replace",
                "append_file",
            } or not isinstance(output, dict):
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
            lines.append(
                "Use search_files instead of run_shell grep for content search."
            )
        if "task_result_update" in names:
            lines.append(
                "Your final action MUST call task_result_update with the outcome report."
            )
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
        """Assemble active review and atomic future-task curation context."""
        unfinished = [
            f"  - [{other.status.value}] {other.title} (id={other.task_id})"
            for other in session.task_store.tasks.values()
            if other.status
            not in {
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
                TaskStatus.SUPERSEDED,
                TaskStatus.COMPROMISED,
            }
            and other.task_id != task.task_id
        ]
        curation_block = ""
        if unfinished:
            curation_block = (
                "\n## Future-Task Context Curation\n"
                "While reviewing the active task, identify useful claims relevant "
                "to these unfinished tasks. Include only useful handoffs in the "
                "task_review_decision context_updates argument so the verdict and "
                "curation commit atomically. Do not review or execute these tasks, "
                "and do not modify their artifacts.\n" + "\n".join(unfinished) + "\n"
            )
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
                "child tasks below must be terminal and their results must still "
                "be valid. Compromised children are unsuccessful limitations that "
                "must remain explicit. Verify integration — do not re-execute the "
                "children.\n\n"
                "Child tasks (direct children only):\n" + "\n".join(child_lines) + "\n"
            )
        journal = "\n".join(_render_review_journal(session.task_store, task))
        journal_block = f"{journal}\n" if journal else ""
        return f"{child_gate}{journal_block}{failure_note}{curation_block}"

    def _failsafe_result_content(self, task: Task, session: Session) -> str:
        """Failsafe transcript when the executor left no result report."""
        transcript_lines = []
        for entry in session.session_context:
            content = entry_content(entry)
            role = (
                entry.get("role", "")
                if isinstance(entry, dict)
                else getattr(entry, "role", "")
            )
            if role and content:
                transcript_lines.append(f"[{role}] {content}")
        return "(No result report from executor)\n\nExecutor transcript:\n" + "\n".join(
            transcript_lines[-10:]
        )

    @staticmethod
    def _executor_evidence(task: Task) -> str:
        """Render bounded executor tool evidence without replaying tool output."""
        if task.result is None:
            return ""
        evidence = task.result.metadata.get("tool_results", [])
        if not isinstance(evidence, list):
            return ""
        lines = []
        for item in evidence[-16:]:
            if not isinstance(item, dict):
                continue
            outcome = item.get("outcome")
            if not isinstance(outcome, dict):
                continue
            name = str(outcome.get("tool_name") or item.get("name") or "tool")
            bits = [f"success={outcome.get('success')}"]
            if outcome.get("exit_code") is not None:
                bits.append(f"exit_code={outcome['exit_code']}")
            if outcome.get("error"):
                bits.append(f"error={outcome['error']}")
            invocation = outcome.get("invocation")
            if isinstance(invocation, dict):
                bits.extend(f"{key}={value}" for key, value in invocation.items())
            if item.get("artifact_path"):
                bits.append(f"audit={item['artifact_path']}")
            lines.append(f"- {name}: " + "; ".join(bits))
        if not lines:
            return ""
        omitted = max(0, len(evidence) - 16)
        suffix = f"\n- ({omitted} earlier tool results omitted)" if omitted else ""
        return "## Executor evidence\n" + "\n".join(lines) + suffix

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
        evidence_block = self._executor_evidence(task)
        cancellation_block = (
            _render_approved_cancellations(session.task_store)
            if task.task_id == session.task_store.root_task_id
            else ""
        )
        clauses = session.task_store.acceptance_clauses()
        clause_block = ""
        if clauses:
            criteria = "\n".join(f"- {clause['text']}" for clause in clauses)
            if task.task_id == session.task_store.root_task_id:
                clause_block = (
                    "Root acceptance criteria (final review gates):\n"
                    "These generated restatements never override the original request. "
                    "Before approval, verify every applicable criterion with "
                    f"matching evidence.\n{criteria}"
                )
            else:
                clause_block = (
                    "Root acceptance criteria (immutable advisory context, not leaf "
                    "gates):\nUse these only to understand the overall mission. "
                    "Judge only the active task against its own description and "
                    f"outcome.\n{criteria}"
                )
        description = task.description.strip() or "(none provided)"
        return (
            f"{mission_prefix}Task under review: {task.task_id} — {task.title}\n"
            f"Active task description: {description}\n"
            f"Task status: {task.status.value}\n"
            f"Outcome report: {result_content}\n"
            f"{_render_request_contract(session)}\n"
            "Unified task context:\n"
            f"{_render_task_tree_markdown(_task_context_snapshot(session), include_results=False)}\n"
            f"{context_blocks}\n{evidence_block}\n{cancellation_block}\n{clause_block}\n{base}"
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
        if self.session is None:
            return
        from tinycua.loops.worker_runtime import WorkerRuntimeController

        terminal_nodes = [node for node in queue.items[1:] if node.is_terminal]
        queue.clear_after_current()
        sc = self.session.session_config
        enable_oq = bool(sc.enable_open_question_review) if sc is not None else False
        replan_threshold = sc.replan_threshold if sc is not None else 5
        reviewed = self._reviewed_task_from_result(response)
        if reviewed is None or not reviewed.reviewer_decisions:
            raise RuntimeError("Reviewer completed without a committed task decision.")
        decision = reviewed.reviewer_decisions[-1]["decision"]
        WorkerRuntimeController(
            self.session.task_store,
            enable_open_question_review=enable_oq,
            replan_threshold=replan_threshold,
            session=self.session,
        ).schedule_after_review(
            queue,
            reviewed_task_id=reviewed.task_id,
            decision=decision,
        )
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
            if task is None:
                continue
            request = task.metadata.get("cancellation_request")
            if (
                task.status == TaskStatus.CANCELLED
                and isinstance(request, dict)
                and request.get("state") == "approved"
                and "cascade_from_task_id" not in request
            ):
                lines.append(
                    f"[CANCELLED] {task.title}: {request.get('rationale', '')}"
                )
                continue
            if task.result is None:
                continue
            status_mark = " ✓" if task.status == TaskStatus.COMPLETED else ""
            if task.status == TaskStatus.COMPROMISED:
                status_mark = " ! COMPROMISED"
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
        if root.status != TaskStatus.COMPROMISED:
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
            self.session,
            aggregated,
            self.node_id,
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
        compromised_results: list[TaskResult] = []
        artifacts: list[dict] = []
        # Reverse post-order: last-executed leaf first, root last.
        ordered_ids = list(reversed(store._ordered_ids()))
        if store.root_task_id and store.root_task_id in store.tasks:
            ordered_ids.append(store.root_task_id)
        for task_id in ordered_ids:
            task = store.tasks.get(task_id)
            if task is None:
                continue
            request = task.metadata.get("cancellation_request")
            if (
                task.status == TaskStatus.CANCELLED
                and isinstance(request, dict)
                and request.get("state") == "approved"
                and "cascade_from_task_id" not in request
            ):
                task_summaries.append(
                    f"[CANCELLED] {task.title}: {request.get('rationale', '')}"
                )
                continue
            if task.result is None:
                continue
            if task.status == TaskStatus.COMPLETED:
                task_summaries.append(f"{task.title}: {task.result.summary}")
                accepted_results.append(task.result)
            elif task.status == TaskStatus.COMPROMISED:
                task_summaries.append(
                    f"[COMPROMISED] {task.title}: {task.result.summary}"
                )
                compromised_results.append(task.result)
            else:
                continue
            artifacts.extend(task.artifacts)
        final_context = "\n".join(
            part for part in [model_context.strip(), *task_summaries] if part
        )
        return AggregatedResult(
            root_task_id=store.root_task_id,
            task_summaries=task_summaries,
            accepted_results=accepted_results,
            compromised_results=compromised_results,
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
        if (
            self.session is not None
            and self.session.task_store.root_task_id is not None
        ):
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
                f"Scheduled analysis effort pass {self.pass_count + 1} of {pass_limit}."
            )
        else:
            queue.spawn_after_current(
                [
                    TinyCUATaskAssessorNode(
                        node_id="task_assessor",
                        config=create_node_config(
                            "task_assessor", self.config, mode="final_assessment"
                        ),
                    )
                ]
            )
            content = f"Analysis effort complete after {pass_limit} pass(es)."

        return LLMResult(content=content, role="assistant")
