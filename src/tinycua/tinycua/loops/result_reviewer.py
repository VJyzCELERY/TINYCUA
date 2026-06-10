"""TinyCUAResultReviewerNode — result evaluation ProcessNode.

Evaluates TaskExecutor output and decides accept/retry/replan/open_question.
Uses ReviewerRetryState from loop to check threshold. on_complete dispatches
based on decision.
"""

from __future__ import annotations

import json
import re
import logging
from typing import TYPE_CHECKING, Any

from tinycua.loops.node import ProcessNode

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)


class TinyCUAResultReviewerNode(ProcessNode):
    """Result evaluation node.

    Evaluates TaskExecutor output and decides accept/retry/replan/open_question.
    Uses ReviewerRetryState from loop to check threshold.

    Attributes:
        node_id: Always "result_reviewer" by default.
        loop: Reference to TinyCUALoop for accessing retry state.
    """

    def __init__(
        self,
        node_id: str = "result_reviewer",
        config: NodeConfigBase | None = None,
        loop: Any | None = None,
    ) -> None:
        """Initialize ResultReviewerNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            loop: Reference to TinyCUALoop for retry state access.
        """
        super().__init__(
            node_id=node_id,
            config=config,  # type: ignore[arg-type]
            instruction=(
                "You are a result reviewer node. Evaluate the execution result "
                "and decide: 'accept' (task is complete), 'retry' (retry execution), "
                "'replan' (needs replanning), or 'open_question' (cannot be solved). "
                "Respond with JSON: {\"outcome\": \"...\", \"rationale\": \"...\"}"
            ),
        )
        self.loop = loop

    def _parse_decision(self, response: LLMResult) -> dict[str, Any]:
        """Parse reviewer decision from LLM response.

        Attempts to parse JSON from the response. Falls back to retry
        if parsing fails.

        Args:
            response: The LLM response containing reviewer decision.

        Returns:
            Dict with 'outcome' and 'rationale' keys.
        """
        try:
            data = json.loads(response.content)
            if isinstance(data, dict) and "outcome" in data:
                return data
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: check if outcome keyword appears in response (word-boundary match)
        match = re.fullmatch(r'\s*(accept|retry|replan|open_question)\s*', response.content, re.IGNORECASE)
        if match:
            return {"outcome": match.group(1).lower(), "rationale": response.content[:200]}

        # Default fallback: retry
        logger.warning(
            "node=%s could not parse reviewer decision, falling back to retry",
            self.node_id,
        )
        return {"outcome": "retry", "rationale": "Could not parse decision, defaulting to retry"}

    def __call__(self, input_data: NodeInputLike) -> LLMResult:
        """Evaluate the execution result.

        Args:
            input_data: Node input containing execution result.

        Returns:
            LLMResult with reviewer decision in metadata.
        """
        if self.session is None:
            from tinycua.loops.node import NodeExecutionError

            msg = f"Node {self.node_id} has no session attached"
            raise NodeExecutionError(msg)

        from tinycua.config.types import LLMResult
        from tinycua.models.node_input import NodeInput

        messages = self.build_messages(self.session, input_data)
        response = self._call_llm(messages)
        decision_data = self._parse_decision(response)

        # Forward active_task from input metadata as a top-level metadata key
        # so on_complete can dispatch to loop handlers with a typed Task reference.
        active_task = None
        if isinstance(input_data, NodeInput):
            active_task = input_data.metadata.get("active_task")

        logger.info(
            "node=%s decision=%s",
            self.node_id,
            decision_data.get("outcome"),
        )

        return LLMResult(
            content=response.content,
            role="assistant",
            metadata={"reviewer_decision": decision_data, "active_task": active_task},
        )

    def _spawn_replan_nodes(self, queue: NodeQueue, active_task: Any) -> None:
        """Spawn TaskAssessor + TaskAnalyzer + TaskExecutor for replan.

        Args:
            queue: The node queue to mutate.
            active_task: The task being replanned.
        """
        if self.loop is None:
            logger.error("Cannot spawn replan nodes: loop reference is None")
            return

        from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
        from tinycua.loops.task_assessor import TinyCUATaskAssessorNode
        from tinycua.loops.task_executor import TinyCUATaskExecutorNode

        task_assessor = TinyCUATaskAssessorNode(
            node_id="task_assessor",
            config=self.loop.session_config,
            mode="reviewer_replan",
        )
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=self.loop.session_config,
            mode="local_replan",
        )
        # TaskExecutorNode intentionally does NOT receive loop — it does not
        # access loop-level state (retry counts, active task ID, etc.).  The
        # reviewer receives loop so it can dispatch decisions to loop handlers.
        task_executor = TinyCUATaskExecutorNode(
            node_id="task_executor",
            config=self.loop.session_config,
        )

        queue.spawn_after_current([task_assessor, task_analyzer, task_executor])

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Dispatch based on reviewer decision.

        Routes to the appropriate handler on the loop based on the
        reviewer's decision outcome.

        Args:
            queue: The node queue (may be mutated for replan routing).
            response: The reviewer decision response.
        """
        decision_data = response.metadata.get("reviewer_decision", {})
        outcome = decision_data.get("outcome", "retry")
        active_task = response.metadata.get("active_task")

        if self.loop is not None:
            if outcome == "accept" and active_task is not None:
                self.loop._on_reviewer_accept(active_task)
            elif outcome == "retry" and active_task is not None:
                if self.loop._reviewer_retry_state.can_retry():
                    self.loop._on_reviewer_retry(active_task)
                else:
                    # Force accept when threshold reached
                    self.loop._on_reviewer_accept(active_task)
            elif outcome == "replan" and active_task is not None:
                self.loop._on_reviewer_replan(active_task)
                queue.clear_after_current()
                self._spawn_replan_nodes(queue, active_task)
                if self.loop.default_terminal_node is not None:
                    queue.ensure_terminal(self.loop.default_terminal_node)
            elif outcome == "open_question" and active_task is not None:
                self.loop._on_reviewer_open_question(active_task)

        logger.info(
            "node=%s on_complete outcome=%s",
            self.node_id,
            outcome,
        )
