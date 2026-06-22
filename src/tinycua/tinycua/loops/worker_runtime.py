"""State-driven worker runtime queue controller."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from tinycua.config.node_config import create_node_config
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_nodes import (
    TinyCUAResultAggregationNode,
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskAssessorNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.session import Session
from tinycua.models.task import ReviewerDecision, TaskStateStore

logger = logging.getLogger(__name__)

# Sentinel decision value inserted into reviewer_decisions by schedule_replan
# to reset the consecutive_failures baseline (FR-049). Not a real reviewer
# decision — never emitted by the LLM. The derived counter breaks on it.
_REPLAN_BOUNDARY = "replan_boundary"

# Effort → max_replans fallback when no session config is available (FR-050).
_EFFORT_MAX_REPLANS: dict[str, int] = {"none": 0, "low": 1, "medium": 3, "high": 6}


@dataclass
class WorkerRuntimeController:
    """Mutate worker queues from task state instead of fixed linear chains.

    Args:
        store: The session-owned task tree.
        enable_open_question_review: When True, allow ``OPEN_QUESTION``
            reviewer decisions to bail to ResponseNode for unresolved
            upstream questions. Defaults to False — one-shot worker mode
            must not bail while tasks remain unfinished.
        replan_threshold: Consecutive reviewer rejections before auto-replan.
            When a task's ``consecutive_failures`` reaches this threshold,
            the runtime routes to TaskAnalyzer for replan instead of
            retrying the executor. Defaults to 5.
        session: Optional session used to resolve ``max_replans`` from the
            worker effort profile when ``max_replans`` is not set explicitly.
        max_replans: Maximum replans per task before force-approve (FR-050).
            When None, resolved from ``session.session_config.max_replans``
            (which is itself effort-derived: none=0, low=1, medium=3, high=6).
    """

    store: TaskStateStore
    enable_open_question_review: bool = False
    replan_threshold: int = 5
    session: Session | None = None
    max_replans: int | None = None

    def __post_init__(self) -> None:
        """Resolve max_replans from session config when not explicit."""
        if self.max_replans is None:
            if self.session is not None and self.session.session_config is not None:
                self.max_replans = self.session.session_config.max_replans
            else:
                self.max_replans = 3  # medium default

    def schedule_replan(self, queue: NodeQueue, replan_reason: str = "") -> None:
        """Schedule local assessor/analyzer replan before execution.

        Also inserts a ``replan_boundary`` sentinel into the active task's
        ``reviewer_decisions`` audit trail (FR-049) so the derived
        ``consecutive_failures`` counter resets. The full audit trail is
        preserved — only the consecutive run is broken.

        Args:
            queue: The node queue to mutate.
            replan_reason: Optional reason string (e.g. auto-replan trigger
                context) passed to the analyzer via config metadata.
        """
        active = self.store.get_active_task()
        if active is not None:
            active.reviewer_decisions.append(
                {
                    "decision": _REPLAN_BOUNDARY,
                    "rationale": replan_reason or "replan triggered",
                    "metadata": {},
                }
            )
            self.store._bump_version()
        analyzer_config = create_node_config("task_analyzer", mode="local_replan")
        if replan_reason:
            analyzer_config.metadata["replan_reason"] = replan_reason
        queue.items.extend(
            [
                TinyCUATaskAssessorNode(
                    node_id="task_assessor",
                    config=create_node_config("task_assessor", mode="local_replan"),
                ),
                TinyCUATaskAnalyzerNode(
                    node_id="task_analyzer",
                    config=analyzer_config,
                ),
                TinyCUATaskExecutorNode(
                    node_id="task_executor",
                    config=create_node_config("task_executor"),
                ),
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer"),
                ),
            ]
        )

    def _replan_count(self, task: Any) -> int:
        """Count replan_boundary entries in the task's reviewer_decisions."""
        return sum(
            1
            for d in task.reviewer_decisions
            if d.get("decision") == _REPLAN_BOUNDARY
        )

    def _force_approve_at_cap(self, task: Any, queue: NodeQueue) -> None:
        """Force-approve the task when the replan budget is exhausted (FR-050)."""
        effort = "medium"
        if self.session is not None and self.session.session_config is not None:
            effort = str(self.session.session_config.worker_effort)
        cap = self.max_replans if self.max_replans is not None else 3
        rationale = (
            f"Replan budget exhausted (effort={effort}, cap={cap}). "
            "The task could not be completed within the replan budget; "
            "accepting the current result to preserve zero-exit."
        )
        logger.info(
            "replan_budget_exhausted task_id=%s replan_count=%d cap=%d — force-approving",
            task.task_id,
            self._replan_count(task),
            cap,
        )
        self.store.record_reviewer_decision(
            task.task_id, ReviewerDecision.APPROVED, rationale=rationale
        )
        self.schedule_next(queue)

    def schedule_after_review(self, queue: NodeQueue) -> None:
        """Schedule the next nodes after a reviewer decision.

        When a task has been sent back for rework ``replan_threshold``
        consecutive times (needs_revision/rejected), the runtime
        deterministically routes to TaskAnalyzer for replan instead of
        retrying the executor. The replan reason (including rejection
        rationales) is passed to the analyzer so it knows what went wrong.

        FR-050: when the task has already been replanned ``max_replans``
        times (counted via ``replan_boundary`` entries), the next send-back
        force-approves the task instead of queueing another replan —
        bounding the loop without violating the zero-exit guarantee.
        """
        active = self.store.get_active_task()
        latest = active.reviewer_decisions[-1] if active and active.reviewer_decisions else {}
        decision = latest.get("decision")
        if decision in {ReviewerDecision.NEEDS_REVISION.value, ReviewerDecision.REJECTED.value}:
            # FR-050: if the replan budget is exhausted, force-approve.
            if active is not None and self._replan_count(active) >= (
                self.max_replans if self.max_replans is not None else 3
            ):
                self._force_approve_at_cap(active, queue)
                return
            # Auto-replan gate: if consecutive failures reach the threshold,
            # route to TaskAnalyzer instead of retrying the executor.
            if active and active.consecutive_failures >= self.replan_threshold:
                reason = self._build_replan_reason(active)
                logger.info(
                    "replan_triggered task_id=%s consecutive_failures=%d threshold=%d "
                    "decision=%s — routing to TaskAnalyzer for replan",
                    active.task_id,
                    active.consecutive_failures,
                    self.replan_threshold,
                    decision,
                )
                self.schedule_replan(queue, replan_reason=reason)
                return
            queue.items.extend(
                [
                    TinyCUATaskExecutorNode(
                        node_id="task_executor",
                        config=create_node_config("task_executor"),
                    ),
                    TinyCUAResultReviewerNode(
                        node_id="result_reviewer",
                        config=create_node_config("result_reviewer"),
                    ),
                ]
            )
            return
        if decision == ReviewerDecision.REPLAN.value:
            # FR-050: explicit replan also respects the cap.
            if active is not None and self._replan_count(active) >= (
                self.max_replans if self.max_replans is not None else 3
            ):
                self._force_approve_at_cap(active, queue)
                return
            reason = self._build_replan_reason(active) if active else ""
            self.schedule_replan(queue, replan_reason=reason)
            return
        if (
            decision == ReviewerDecision.OPEN_QUESTION.value
            and self.enable_open_question_review
        ):
            from tinycua.loops.response_node import ResponseNode

            queue.items.append(
                ResponseNode(
                    node_id="response",
                    config=create_node_config("response"),
                )
            )
            return
        self.schedule_next(queue)

    def _build_replan_reason(self, task: Any) -> str:
        """Build a replan reason string from the task's rejection history.

        Includes the consecutive failure count and the last 2 rejection
        rationales so the analyzer knows what went wrong.
        """
        count = task.consecutive_failures
        lines = [
            f"Auto-replan triggered: this task has been sent back for rework "
            f"{count} times."
        ]
        # Collect the last 2 rejection rationales.
        back_decisions = {
            ReviewerDecision.NEEDS_REVISION.value,
            ReviewerDecision.REJECTED.value,
            ReviewerDecision.REPLAN.value,
        }
        rationales = []
        for d in reversed(task.reviewer_decisions):
            if d.get("decision") in back_decisions:
                rationale = d.get("rationale", "").strip()
                if rationale:
                    rationales.append(rationale)
                if len(rationales) >= 2:
                    break
            else:
                break
        if rationales:
            lines.append(f"Recent rejection rationale: {rationales[0]}")
            if len(rationales) > 1:
                lines.append(f"Previous rejection rationale: {rationales[1]}")
        lines.append(
            "The current approach is not working — decompose it differently, "
            "merge it, or adjust the plan."
        )
        return "\n".join(lines)

    def schedule_next(self, queue: NodeQueue) -> None:
        """Schedule execution for the next active task or final aggregation."""
        if self.store.all_done():
            queue.items.append(
                TinyCUAResultAggregationNode(
                    node_id="result_aggregation",
                    config=create_node_config("result_aggregation"),
                )
            )
            return
        if self.store.get_active_task() is not None:
            queue.items.extend(
                [
                    TinyCUATaskExecutorNode(
                        node_id="task_executor",
                        config=create_node_config("task_executor"),
                    ),
                    TinyCUAResultReviewerNode(
                        node_id="result_reviewer",
                        config=create_node_config("result_reviewer"),
                    ),
                ]
            )
