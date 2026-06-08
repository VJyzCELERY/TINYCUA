"""TinyCUATaskCreateNode — ProcessNode for deterministic first-time root task creation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tinycua.loops.node import ProcessNode

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)


class TinyCUATaskCreateNode(ProcessNode):
    """Concrete ProcessNode for deterministic first-time root task creation.

    Uses TaskInit/TaskCreate tools to create root tasks. After task creation,
    advances the queue to TaskAnalyzerNode.

    Attributes:
        node_id: Always "task_create" by default.
        tool_scope: List of tool names available to this node.
    """

    def __init__(
        self,
        node_id: str = "task_create",
        config: NodeConfigBase | None = None,
    ) -> None:
        """Initialize TaskCreateNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
        """
        super().__init__(
            node_id=node_id,
            config=config,  # type: ignore[arg-type]
            instruction=(
                "You are a task creation node. Create a root task for the user's "
                "request. Use the TaskInit tool to initialize the task structure, "
                "then TaskCreate to finalize the task. Set a clear, actionable "
                "task description and break it into subtasks if appropriate."
            ),
        )
        self.tool_scope: list[str] = ["TaskInit", "TaskCreate"]

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute task creation.

        Calls the LLM to create a root task using TaskInit/TaskCreate tools.
        Records the task in the session.

        Args:
            input: The node input containing the user's request.

        Returns:
            The LLM response from task creation.
        """
        result = super().__call__(input)

        # Record task creation in session
        if self.session is not None:
            # Set the task in the session from the LLM response
            if not result.content:
                self.session.task = "Task created"
            else:
                self.session.task = result.content
            logger.info(
                "node=%s task_created task=%s",
                self.node_id,
                self.session.task[:100] if self.session.task else "None",
            )

        return result

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Advance queue; next node is TaskAnalyzerNode.

        Removes the current TaskCreateNode from the queue, making
        the next node (TaskAnalyzerNode) the current node.

        Args:
            queue: The node queue (will be advanced).
            response: The LLM response from task creation.
        """
        logger.info(
            "node=%s on_complete advancing queue",
            self.node_id,
        )
        queue.advance()
