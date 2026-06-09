"""TinyCUATaskAssessorNode — ProcessNode for task tree evaluation and selection.

Evaluates the task tree and selects unfinished tasks for processing.
Operates in effort-loop mode when called from AnalysisEffortNode.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from tinycua.loops.node import ProcessNode

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)


class TinyCUATaskAssessorNode(ProcessNode):
    """ProcessNode for task tree evaluation and selection.

    Evaluates the task tree and selects unfinished tasks for processing.
    Operates in two modes:
    - ``effort_loop``: Evaluates full tree, selects unfinished tasks (default).
    - ``reviewer_replan``: Full re-planning mode (deferred).

    Attributes:
        node_id: Always "task_assessor" by default.
        mode: The assessment mode.
        selected_tasks: List of task IDs selected for processing.
    """

    def __init__(
        self,
        node_id: str = "task_assessor",
        config: NodeConfigBase | None = None,
        mode: str = "effort_loop",
    ) -> None:
        """Initialize TaskAssessorNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            mode: Assessment mode. "effort_loop" evaluates full tree.
        """
        super().__init__(
            node_id=node_id,
            config=config,  # type: ignore[arg-type]
            instruction=(
                "You are a task assessor. Evaluate the current task tree and "
                "select only tasks that are NOT completed (status != 'completed'). "
                "Return a JSON list of selected task IDs. If all tasks are complete, "
                "return an empty list []."
            ),
        )
        self.mode = mode
        self.selected_tasks: list[str] = []

    def __call__(self, input: NodeInputLike) -> LLMResult:  # type: ignore[override]
        """Execute task assessment.

        Calls the LLM to evaluate the task tree and select unfinished tasks.
        Parses the response to extract selected task IDs.

        Args:
            input: The node input containing task context.

        Returns:
            The LLM response with task assessment.
        """
        result = super().__call__(input)

        # Parse selected task IDs from LLM response
        try:
            content = result.content.strip()
            # Handle JSON list response
            if content.startswith("["):
                self.selected_tasks = json.loads(content)
            else:
                # Fallback: treat as comma-separated or single task ID
                self.selected_tasks = [
                    t.strip() for t in content.split(",") if t.strip()
                ]
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "node=%s failed to parse selected_tasks from response: %s",
                self.node_id,
                result.content[:200],
            )
            self.selected_tasks = []

        logger.info(
            "node=%s mode=%s selected_tasks=%s",
            self.node_id,
            self.mode,
            self.selected_tasks,
        )
        return result

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:  # type: ignore[override]
        """Advance queue after task assessment.

        If tasks were selected, the queue advances to TaskAnalyzer.
        If no tasks selected, the queue advances back to AnalysisEffortNode.

        Args:
            queue: The node queue (will be advanced).
            response: The LLM response from task assessment.
        """
        logger.info(
            "node=%s on_complete selected_tasks=%s advancing queue",
            self.node_id,
            self.selected_tasks,
        )
        queue.advance()
