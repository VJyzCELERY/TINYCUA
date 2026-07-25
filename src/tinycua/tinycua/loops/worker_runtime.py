"""State-driven worker runtime queue controller."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
        session: Optional session for task-context access.
    """

    store: TaskStateStore
    enable_open_question_review: bool = False
    replan_threshold: int = 5
    session: Session | None = None
    max_replans: int | None = None

    def __post_init__(self) -> None:
        """Retain the configured value for diagnostics without enforcing a cap."""
        if self.max_replans is None:
            self.max_replans = (
                self.session.session_config.max_replans
                if self.session is not None and self.session.session_config is not None
                else 3
            )

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

    def schedule_after_review(self, queue: NodeQueue) -> None:
        """Schedule the next nodes after a reviewer decision.

        When a task has been sent back for rework ``replan_threshold``
        consecutive times (needs_revision/rejected), the runtime
        deterministically routes to TaskAnalyzer for replan instead of
        retrying the executor. The replan reason (including rejection
        rationales) is passed to the analyzer so it knows what went wrong.

        Replanning is intentionally unbounded: incomplete work never routes to
        the response node.
        """
        active = self.store.get_active_task()
        latest = active.reviewer_decisions[-1] if active and active.reviewer_decisions else {}
        decision = latest.get("decision")
        if decision in {ReviewerDecision.NEEDS_REVISION.value, ReviewerDecision.REJECTED.value}:
            # FR-057: needs_revision and rejected are unified (aliases) — both
            # send the task back for rework and increment consecutive_failures
            # identically. No terminal-failure path for rejected by design.
            # Auto-replan gate: if consecutive failures reach the threshold,
            # route to TaskAnalyzer instead of retrying the executor.
            if active and active.consecutive_failures >= self.replan_threshold:
                reason = self._build_replan_reason(active)
                logger.info(
                    "replan_triggered task_id=%s consecutive_failures=%d threshold=%d "
                    "replans=%d decision=%s — routing to TaskAnalyzer for replan",
                    active.task_id,
                    active.consecutive_failures,
                    self.replan_threshold,
                    self._replan_count(active),
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
            reason = self._build_replan_reason(active) if active else ""
            self.schedule_replan(queue, replan_reason=reason)
            return
        if decision == ReviewerDecision.OPEN_QUESTION.value:
            self.schedule_replan(queue, replan_reason=self._build_replan_reason(active))
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
        """Schedule execution for the next active task or final aggregation.

        FR-067: state-driven queue. The queue checks the active task's state:
        - No result → spawn [executor, reviewer] (work needs to be done).
        - Has result, no negative review → spawn [executor, reviewer] so a
          completed node never advances directly to another instance of itself.
        - Has result + last review was needs_revision/rejected → spawn
          [executor, reviewer] (rework needed).
        - All done → spawn [result_aggregation].
        Post-order traversal is maintained via next_unfinished_leaf.
        """
        if self.store.all_done():
            queue.items.append(
                TinyCUAResultAggregationNode(
                    node_id="result_aggregation",
                    config=create_node_config("result_aggregation"),
                )
            )
            return
        active = self.store.get_active_task()
        if active is None:
            raise RuntimeError("Task tree is incomplete but has no active task.")
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
