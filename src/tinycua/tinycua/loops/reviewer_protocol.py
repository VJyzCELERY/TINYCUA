"""Root-review falsification lifecycle and provenance helpers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from tinycua.loops.node_contract import LifecyclePhase


class ReviewerProtocolMixin:
    """Root-only PLAN initialization and blind continuation rendering."""

    def ensure_session(self, root_or_parent_session: Any) -> Any:
        """Attach the session and initialize root review in blind PLAN phase."""
        session = super().ensure_session(root_or_parent_session)
        if not self.progress.lifecycle_history and not self.progress.visited_tools:
            initialize_reviewer_lifecycle(self)
        return session

    def _build_plan_continuation(self, session: Any, task: Any) -> str:
        """Build root planning context without Executor conclusions."""
        from tinycua.loops.mission import _render_mission_block
        from tinycua.loops.task_nodes import _render_request_contract

        return render_plan_continuation(
            task=task,
            acceptance_clauses=session.task_store.acceptance_clauses(),
            mission=_render_mission_block(session),
            request_contract=_render_request_contract(session),
        )


def initialize_reviewer_lifecycle(node: Any) -> None:
    """Start an unplanned root review in PLAN; leave other reviews in ACTION."""
    if node.node_id != "result_reviewer" or node.session is None:
        return
    store = node.session.task_store
    active = store.get_active_task()
    if (
        active is not None
        and active.task_id == store.root_task_id
        and bool(store.acceptance_clauses())
        and not store.staged_review_plan(active.task_id)
    ):
        node.progress.lifecycle_phase = LifecyclePhase.PLAN


def reset_reviewer_attempt(node: Any) -> bool:
    """Reset root plan and observations before a new Reviewer attempt."""
    if node.node_id != "result_reviewer" or node.session is None:
        return False
    store = node.session.task_store
    active = store.get_active_task()
    if (
        active is None
        or active.task_id != store.root_task_id
        or not store.acceptance_clauses()
    ):
        return False
    plan = store._staged_review_plans.pop(active.task_id, None)
    decision = store._staged_reviewer_decisions.pop(active.task_id, None)
    changed = bool(plan or decision)
    if changed:
        store._bump_version()
    node.progress.visited_tools.clear()
    node.progress.satisfied_requirements.clear()
    node.progress.correlated_outcomes.clear()
    node.progress.lifecycle_history.clear()
    node.progress.lifecycle_phase = LifecyclePhase.PLAN
    node.progress.action_summary = ""
    node.progress.accumulated_tool_results.pop("task_review_plan", None)
    node.progress.accumulated_tool_results.pop("task_review_decision", None)
    return True


def issue_observation_ids(
    tool_call: dict[str, Any], node: Any, results: list[dict[str, Any]]
) -> tuple[str, str]:
    """Return provider provenance and a unique runtime evidence ID."""
    call_id = str(tool_call.get("id") or f"runtime-{uuid4().hex}")
    prior = node.progress.correlated_outcomes if node is not None else []
    used = {
        str(outcome.get("evidence_id"))
        for outcome in [
            *prior,
            *(item.get("outcome", {}) for item in results),
        ]
        if outcome.get("evidence_id")
    }
    evidence_id = call_id if call_id not in used else f"runtime-{uuid4().hex}"
    return call_id, evidence_id


def render_plan_continuation(
    *,
    task: Any,
    acceptance_clauses: list[dict[str, str]],
    mission: str,
    request_contract: str,
) -> str:
    """Render root planning context without Executor conclusions."""
    criteria = "\n".join(
        f"- {clause['id']}: {clause['text']}" for clause in acceptance_clauses
    )
    mission_prefix = f"{mission}\n\n" if mission else ""
    description = task.description.strip() or "(none provided)"
    return (
        f"{mission_prefix}Root task under review: {task.task_id} — {task.title}\n"
        f"Root task description: {description}\n"
        f"{request_contract}\n"
        "Root acceptance criteria (final review gates) to falsify:\n"
        f"{criteria}\n\n"
        "Verify every applicable criterion by first committing exactly one "
        "falsification check per criterion before inspecting Executor claims or "
        "deciding the review."
    )


def advance_lifecycle_phase(node: Any, result: Any) -> bool:
    """Advance root planning or the normal ACTION-to-COMMIT lifecycle."""
    if not node.contract.requires_terminate:
        return False
    if node.progress.lifecycle_phase == LifecyclePhase.PLAN:
        planned = any(
            isinstance(item, dict)
            and item.get("name") == "task_review_plan"
            and isinstance(item.get("output"), dict)
            and item["output"].get("success") is True
            for item in result.metadata.get("tool_results", [])
        )
        if not planned:
            return False
        node.progress.advance_lifecycle(
            LifecyclePhase.ACTION, "Root falsification plan committed."
        )
        return True
    if node.progress.lifecycle_phase != LifecyclePhase.ACTION:
        return False
    commit_tools = set(node.contract.required_tools)
    for group in node.contract.any_of_tools:
        commit_tools.update(group)
    attempted_commit = any(
        isinstance(item, dict) and item.get("name") in commit_tools
        for item in result.metadata.get("tool_results", [])
    )
    if attempted_commit or not result.tool_calls:
        node.progress.advance_lifecycle(LifecyclePhase.SUMMARY, result.content.strip())
        node.progress.advance_lifecycle(LifecyclePhase.COMMIT)
        return True
    return False


def review_action_directive(node: Any) -> str:
    """Reveal the Executor outcome only after the root plan is committed."""
    if node.node_id != "result_reviewer" or node.session is None:
        return ""
    active = node.session.task_store.get_active_task()
    report = active.result.content.strip() if active and active.result else ""
    suffix = f"\nExecutor outcome report:\n{report}" if report else ""
    return (
        "PLAN committed. Independently execute the planned falsification checks now. "
        f"Executor claims are context, not observations.{suffix}"
    )


def annotate_outcome(
    outcome: dict[str, Any],
    *,
    call_id: str,
    evidence_id: str,
    node: Any,
    task_id: str | None,
    task_version: int,
) -> None:
    """Attach runtime-issued observation provenance to one tool outcome."""
    outcome.update(
        {
            "call_id": call_id,
            "evidence_id": evidence_id,
            "node_id": node.node_id if node is not None else None,
            "task_id": task_id,
            "review_attempt": node.progress.attempt_count if node is not None else None,
            "lifecycle_phase": (
                node.progress.lifecycle_phase.value if node is not None else None
            ),
            "task_version": task_version,
        }
    )


def reviewer_assurance_errors(node: Any, store: Any) -> list[str]:
    """Return invalid empirical observation references for a staged root verdict."""
    active_id = store.active_task_id
    if active_id != store.root_task_id or active_id not in store._staged_review_plans:
        return []
    staged = store._staged_reviewer_decisions.get(active_id)
    if not staged:
        return []
    assessments = (staged.get("metadata") or {}).get("criterion_assessments", [])
    allowed = {
        outcome["evidence_id"]
        for outcome in node.progress.correlated_outcomes
        if _is_allowed_observation(
            outcome,
            active_id,
            node.progress.attempt_count,
            store.version,
        )
    }
    cited = {
        evidence_id
        for assessment in assessments
        if isinstance(assessment, dict)
        for evidence_id in assessment.get("evidence_ids", [])
        if isinstance(evidence_id, str)
    }
    invalid = sorted(cited - allowed)
    if not invalid:
        return []
    return [
        "Root assessments must cite successful observations from the current "
        f"Reviewer ACTION attempt and task version; invalid evidence IDs: {invalid}."
    ]


def reviewer_assurance_validation(node: Any, store: Any) -> Any:
    """Return runtime validation and clear a verdict with invalid observations."""
    from tinycua.config.types import ValidationResult

    errors = reviewer_assurance_errors(node, store)
    if errors:
        store._staged_reviewer_decisions.pop(store.active_task_id, None)
    return ValidationResult(is_valid=not errors, errors=errors)


def _is_allowed_observation(
    outcome: dict[str, Any],
    task_id: str,
    review_attempt: int,
    task_version: int,
) -> bool:
    """Return whether an outcome can support an empirical root assessment."""
    tool_name = str(outcome.get("tool_name") or "")
    evidence_id = outcome.get("evidence_id")
    return bool(
        outcome.get("success") is True
        and outcome.get("node_id") == "result_reviewer"
        and outcome.get("task_id") == task_id
        and outcome.get("review_attempt") == review_attempt
        and outcome.get("lifecycle_phase") == "action"
        and outcome.get("task_version") == task_version
        and isinstance(evidence_id, str)
        and evidence_id
        and not tool_name.startswith("task_")
        and tool_name != "terminate"
    )
