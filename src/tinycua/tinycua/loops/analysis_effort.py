"""TinyCUAAnalysisEffortNode — deterministic ProcessNode for effort control.

Controls how many [TaskAssessor, TaskAnalyzer] passes occur before advancing
to execution. Maps WorkerEffort levels to pass limits (0, 1, 2, 3).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from tinycua.loops.node import ProcessNode

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)


class WorkerEffort(str, Enum):
    """Effort levels for task analysis passes.

    Controls how many [TaskAssessor, TaskAnalyzer] rounds precede execution.
    """

    none = "none"  # pass_limit=0: skip extra analysis, advance directly to executor
    low = "low"  # pass_limit=1: one extra [TaskAssessor, TaskAnalyzer] pass
    medium = "medium"  # pass_limit=2: two extra passes
    high = "high"  # pass_limit=3: three extra passes


def effort_to_pass_limit(effort: WorkerEffort) -> int:
    """Map WorkerEffort to pass limit.

    Args:
        effort: The configured effort level.

    Returns:
        Number of [TaskAssessor, TaskAnalyzer] passes to prepend.
    """
    return {
        WorkerEffort.none: 0,
        WorkerEffort.low: 1,
        WorkerEffort.medium: 2,
        WorkerEffort.high: 3,
    }[effort]


class TinyCUAAnalysisEffortNode(ProcessNode):
    """Deterministic ProcessNode that controls planning depth.

    Maps WorkerEffort to pass limits and prepends [TaskAssessor, TaskAnalyzer]
    pairs until the threshold is reached. When threshold is reached, spawns
    TaskExecutor before advancing.

    Attributes:
        node_id: Always "analysis_effort" by default.
        effort: The configured WorkerEffort level.
        pass_limit: Derived from effort via effort_to_pass_limit().
        pass_count: Current number of passes completed (starts at 0).
    """

    def __init__(
        self,
        node_id: str = "analysis_effort",
        config: NodeConfigBase | None = None,
        effort: WorkerEffort = WorkerEffort.none,
    ) -> None:
        """Initialize AnalysisEffortNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            effort: The configured effort level. Defaults to "none".
        """
        super().__init__(
            node_id=node_id,
            config=config,  # type: ignore[arg-type]
            instruction=(
                "You are an analysis effort control node. Your role is to "
                "determine how many additional [TaskAssessor, TaskAnalyzer] "
                "passes should occur before execution. This is a deterministic "
                "operation — no LLM call is required."
            ),
        )
        self.effort = effort
        self.pass_limit = effort_to_pass_limit(effort)
        self.pass_count = 0

    def _should_spawn_executor(self) -> bool:
        """Check if pass_limit has been reached.

        Returns:
            True if pass_count >= pass_limit, False otherwise.
        """
        return self.pass_count >= self.pass_limit

    def _prepend_assessor_analyzer_pair(self, queue: NodeQueue) -> None:
        """Prepend a [TaskAssessor, TaskAnalyzer] pair to the queue.

        Creates TinyCUATaskAssessorNode (mode=effort_loop) and
        TinyCUATaskAnalyzerNode (mode=effort_loop_decomposition),
        prepends them before the current node position.

        Args:
            queue: The node queue to mutate.
        """
        from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
        from tinycua.loops.task_assessor import TinyCUATaskAssessorNode

        task_assessor = TinyCUATaskAssessorNode(
            node_id="task_assessor", config=self.config, mode="effort_loop",
        )
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=self.config,
            mode="effort_loop_decomposition",
        )

        # Prepend before current node (suspends current, inserts at front)
        queue.suspend_current_and_prepend([task_assessor, task_analyzer])
        self.pass_count += 1

        logger.info(
            "node=%s prepended assessor+analyzer pass_count=%d pass_limit=%d",
            self.node_id,
            self.pass_count,
            self.pass_limit,
        )

    def _spawn_task_executor(self, queue: NodeQueue) -> None:
        """Spawn TaskExecutor and ResultReviewer, ensure terminal response path.

        Creates TinyCUATaskExecutorNode and TinyCUAResultReviewerNode, spawns
        them after the current position, ensuring terminal response path is
        maintained.

        Args:
            queue: The node queue to mutate.
        """
        from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
        from tinycua.loops.task_executor import TinyCUATaskExecutorNode

        task_executor = TinyCUATaskExecutorNode(
            node_id="task_executor", config=self.config,
        )
        result_reviewer = TinyCUAResultReviewerNode(
            node_id="result_reviewer", config=self.config,
        )

        # Spawn executor + reviewer after current position
        queue.spawn_after_current([task_executor, result_reviewer])

        # Ensure terminal response path is maintained
        terminal = next((n for n in queue.items if n.is_terminal), None)
        if terminal is not None:
            queue.ensure_terminal(terminal)

        logger.info(
            "node=%s spawned task_executor and result_reviewer",
            self.node_id,
        )

    def __call__(self, input: NodeInputLike) -> LLMResult:  # type: ignore[override]
        """Execute the effort control logic.

        Deterministic behavior:
        - If pass_count < pass_limit: prepend [TaskAssessor, TaskAnalyzer],
          increment pass_count, return a summary response.
        - If pass_count >= pass_limit: spawn TaskExecutor, return a summary response.

        Args:
            input: The node input (ignored for deterministic logic).

        Returns:
            LLMResult with summary of effort control action taken.
        """
        from tinycua.config.types import LLMResult

        if self._should_spawn_executor():
            content = (
                f"Analysis effort complete: pass_count={self.pass_count} "
                f">= pass_limit={self.pass_limit}. Ready for TaskExecutor."
            )
            logger.info(
                "node=%s threshold_reached pass_count=%d spawning_executor",
                self.node_id,
                self.pass_count,
            )
        else:
            content = (
                f"Analysis effort pass {self.pass_count + 1}/{self.pass_limit}: "
                f"prepending [TaskAssessor, TaskAnalyzer]."
            )
            logger.info(
                "node=%s prepending_pass pass_count=%d pass_limit=%d",
                self.node_id,
                self.pass_count,
                self.pass_limit,
            )

        return LLMResult(content=content, role="assistant")

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:  # type: ignore[override]
        """Post-completion hook for queue mutations.

        Called by the orchestrator after __call__ completes. Handles the
        queue mutations (prepending or spawning) based on pass_count state.

        Args:
            queue: The node queue (may be mutated).
            response: The summary response from __call__.
        """
        if self._should_spawn_executor():
            self._spawn_task_executor(queue)
        else:
            self._prepend_assessor_analyzer_pair(queue)
