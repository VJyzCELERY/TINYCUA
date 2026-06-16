"""State-driven worker runtime queue controller."""

from __future__ import annotations

from dataclasses import dataclass

from tinycua.config.node_config import create_node_config
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.task_nodes import (
    TinyCUAAnalysisEffortNode,
    TinyCUAResultAggregationNode,
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskAssessorNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.task import ReviewerDecision, TaskStateStore


@dataclass
class WorkerRuntimeController:
    """Mutate worker queues from task state instead of fixed linear chains."""

    store: TaskStateStore

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

    def schedule_replan(self, queue: NodeQueue) -> None:
        """Schedule local assessor/analyzer replan before execution."""
        queue.items.extend(
            [
                TinyCUATaskAssessorNode(
                    node_id="task_assessor",
                    config=create_node_config("task_assessor", mode="local_replan"),
                ),
                TinyCUATaskAnalyzerNode(
                    node_id="task_analyzer",
                    config=create_node_config("task_analyzer", mode="local_replan"),
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
        """Schedule the next nodes after a reviewer decision."""
        active = self.store.get_active_task()
        latest = active.reviewer_decisions[-1] if active and active.reviewer_decisions else {}
        decision = latest.get("decision")
        if decision in {ReviewerDecision.NEEDS_REVISION.value, ReviewerDecision.REJECTED.value}:
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
            self.schedule_replan(queue)
            return
        if decision == ReviewerDecision.OPEN_QUESTION.value:
            queue.items.append(
                ResponseNode(
                    node_id="response",
                    config=create_node_config("response"),
                )
            )
            return
        self.schedule_next(queue)

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
