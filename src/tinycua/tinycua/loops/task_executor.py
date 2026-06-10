"""TinyCUATaskExecutorNode — ReAct-style task execution ProcessNode.

Executes the active task using a ReAct loop (reason → act → observe)
bounded by max_react_iterations. Produces a TaskResult without mutating
the active task. on_complete advances queue with ResultReviewer next.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tinycua.loops.node import NodeExecutionError, ProcessNode

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)


class TinyCUATaskExecutorNode(ProcessNode):
    """ReAct-style task execution node.

    Executes the active task using a bounded ReAct loop. Receives the
    active task via NodeInput metadata. Produces a TaskResult without
    mutating the active task.

    Attributes:
        node_id: Always "task_executor" by default.
        max_react_iterations: Maximum ReAct iterations (default 10).
    """

    def __init__(
        self,
        node_id: str = "task_executor",
        config: NodeConfigBase | None = None,
        max_react_iterations: int = 10,
    ) -> None:
        """Initialize TaskExecutorNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            max_react_iterations: Maximum ReAct iterations before forced stop.
        """
        super().__init__(
            node_id=node_id,
            config=config,  # type: ignore[arg-type]
            instruction=(
                "You are a task executor node. Execute the assigned task step by step. "
                "When execution is complete, produce a summary with status 'succeeded' or 'failed'."
            ),
        )
        self.max_react_iterations = max_react_iterations

    def _extract_active_task(self, input_data: NodeInputLike) -> Any:
        """Extract the active task from node input metadata.

        Args:
            input_data: The node input containing active_task in metadata.

        Returns:
            The active Task object.

        Raises:
            NodeExecutionError: If no active task is provided.
        """
        from tinycua.models.node_input import NodeInput

        if isinstance(input_data, NodeInput):
            task = input_data.metadata.get("active_task")
            if task is not None:
                return task

        msg = f"Node {self.node_id}: no active_task provided in input metadata"
        raise NodeExecutionError(msg)

    def _build_execution_result(
        self,
        task: Any,
        status: str = "succeeded",
        summary: str = "",
    ) -> dict[str, Any]:
        """Build a TaskResult dict from the execution.

        Args:
            task: The task that was executed.
            status: Execution status string.
            summary: Human-readable summary.

        Returns:
            Dict representation of TaskResult.
        """
        return {
            "task_id": task.task_id,
            "execution_status": status,
            "summary": summary,
            "artifacts": [],
            "metadata": {"executor_iterations": self.max_react_iterations},
        }

    def __call__(self, input_data: NodeInputLike) -> LLMResult:
        """Execute the task with a bounded ReAct loop.

        Orchestrates: extract active task → call LLM → produce TaskResult.

        Args:
            input_data: Node input with active_task in metadata.

        Returns:
            LLMResult containing execution output.

        Raises:
            NodeExecutionError: If no active task is provided or LLM fails.
        """
        if self.session is None:
            msg = f"Node {self.node_id} has no session attached"
            raise NodeExecutionError(msg)

        task = self._extract_active_task(input_data)
        logger.info(
            "node=%s executing task_id=%s",
            self.node_id,
            task.task_id,
        )

        # Build messages and call LLM
        from tinycua.config.types import LLMResult

        messages = self.build_messages(self.session, input_data)
        last_response = self._call_llm(messages)

        # Build execution result
        result_dict = self._build_execution_result(
            task,
            status="succeeded",
            summary=last_response.content[:500],
        )

        logger.info(
            "node=%s task_id=%s execution_complete status=%s",
            self.node_id,
            task.task_id,
            result_dict["execution_status"],
        )

        return LLMResult(
            content=last_response.content,
            role="assistant",
            metadata={"execution_result": result_dict},
        )

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Post-completion hook: advance queue.

        TaskExecutor is followed by ResultReviewer in the queue.
        The orchestrator (AnalysisEffortNode or WorkerNode) should
        have already spawned both executor and reviewer.

        Args:
            queue: The node queue.
            response: The execution result.
        """
        logger.info(
            "node=%s on_complete advancing queue",
            self.node_id,
        )
        # Default behavior: advance queue (ResultReviewer should be next)
        queue.advance()
