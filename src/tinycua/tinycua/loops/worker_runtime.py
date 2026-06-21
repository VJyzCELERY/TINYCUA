"""State-driven worker runtime queue controller."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from tinycua.config.node_config import create_node_config
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_nodes import (
    TinyCUAAnalysisEffortNode,
    TinyCUAResultAggregationNode,
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskAssessorNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.task import ReviewerDecision, TaskStateStore

logger = logging.getLogger(__name__)


@dataclass
class WorkerRuntimeController:
    """Mutate worker queues from task state instead of fixed linear chains.

    Attributes:
        store: The session-owned task tree.
        enable_open_question_review: When True, allow ``OPEN_QUESTION``
            reviewer decisions to bail to ResponseNode for unresolved
            upstream questions. Defaults to False — one-shot worker mode
            must not bail while tasks remain unfinished.
        replan_threshold: Consecutive reviewer rejections before auto-replan.
            When a task's ``consecutive_failures`` reaches this threshold,
            the runtime routes to TaskAnalyzer for replan instead of
            retrying the executor. Defaults to 5.
    """

    store: TaskStateStore
    enable_open_question_review: bool = False
    replan_threshold: int = 5

    def schedule_initial(self, queue: NodeQueue) -> None:
        """Schedule the initial analysis-through-review lifecycle."""
        queue.items.extend(
            [
                TinyCUATaskAnalyzerNode(
                    node_id="task_analyzer",
                    config=create_node_config("task_analyzer", mode="initial_analysis"),
                ),
                TinyCUAAnalysisEffortNode(
                    node_id="analysis_effort",
                    config=create_node_config("analysis_effort"),
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

    def schedule_replan(self, queue: NodeQueue, replan_reason: str = "") -> None:
        """Schedule local assessor/analyzer replan before execution.

        Args:
            queue: The node queue to mutate.
            replan_reason: Optional reason string (e.g. auto-replan trigger
                context) passed to the analyzer via config metadata.
        """
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

    def schedule_after_review(self, queue: NodeQueue) -> None:
        """Schedule the next nodes after a reviewer decision.

        When a task has been sent back for rework ``replan_threshold``
        consecutive times (needs_revision/rejected), the runtime
        deterministically routes to TaskAnalyzer for replan instead of
        retrying the executor. The replan reason (including rejection
        rationales) is passed to the analyzer so it knows what went wrong.
        """
        active = self.store.get_active_task()
        latest = active.reviewer_decisions[-1] if active and active.reviewer_decisions else {}
        decision = latest.get("decision")
        if decision in {ReviewerDecision.NEEDS_REVISION.value, ReviewerDecision.REJECTED.value}:
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
