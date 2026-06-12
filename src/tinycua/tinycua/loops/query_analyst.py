"""QueryAnalystNode for classifying and routing user input."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node import DecisionNode, Node
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

_QUERY_ANALYST_INSTRUCTION = (
    "You are a query analyst. Your role is to classify user input and "
    "route it to the appropriate handler. "
    "Analyze the user's request and determine whether it requires "
    "task execution (worker), is uncertain, or should pass through directly."
)


class TinyCUAQueryAnalystNode(DecisionNode):
    """Top-level entry node that classifies user input and routes the queue.

    Worker route handler spawns InformationDigesterNode before WorkerNode
    to provide structured digestion for downstream processing.

    Attributes:
        ROUTE_LABELS: Allowed classification labels for routing.
        _queue: Reference to the NodeQueue for queue mutations.
    """

    ROUTE_LABELS = ["worker", "uncertain", "passthrough"]

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _QUERY_ANALYST_INSTRUCTION,
        classification_labels: list[str] | None = None,
        is_terminal: bool = False,
    ) -> None:
        """Initialize QueryAnalystNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration.
            instruction: Instruction string for this node type.
            classification_labels: Allowed classification labels.
                Defaults to ROUTE_LABELS if not provided.
            is_terminal: Whether this node is terminal.
        """
        super().__init__(
            node_id=node_id,
            config=config,
            instruction=instruction,
            classification_labels=classification_labels or self.ROUTE_LABELS,
            is_terminal=is_terminal,
        )
        self._queue: NodeQueue | None = None

    def _route_worker(self, input_data: NodeInputLike) -> None:
        """Route to WorkerNode with information digestion.

        1. Check if target Worker session already has DigestedInformation
           → If yes, advance to existing Worker (no digest spawn)
        2. Otherwise, spawn InformationDigesterNode before WorkerNode
           → queue.spawn_after_current([digester, worker_node])

        Args:
            input_data: The node input containing the user query.
        """
        user_query = self._extract_user_query(input_data)
        queue = self._queue

        # Create WorkerNode
        worker_node = TinyCUAWorkerNode(
            node_id="worker",
            config=self.config,
        )

        # Attach a session to the worker
        worker_session = Session()
        worker_node.session = worker_session

        # Check for existing digest
        if self._check_existing_digest(worker_node):
            # Already digested — just ensure worker is in queue
            if queue is not None:
                queue.spawn_after_current([worker_node])
            return

        # Create InformationDigesterNode
        digester = TinyCUAInformationDigesterNode(
            node_id="digester",
            config=self.config,
        )

        # Assign the user query as original query for the digester
        digester._original_query = user_query

        if queue is not None:
            queue.spawn_after_current([digester, worker_node])

    def _check_existing_digest(self, worker: Node) -> bool:
        """Check if the worker's session already has DigestedInformation.

        Scans session_context for existing DigestedInformation entries.

        Args:
            worker: The worker node to check.

        Returns:
            True if DigestedInformation exists in the worker's session.
        """
        if worker.session is None:
            return False

        for entry in worker.session.session_context:
            if isinstance(entry.get("content"), DigestedInformation):
                return True

        return False

    def _extract_user_query(self, input_data: NodeInputLike) -> str:
        """Extract original user query from input data.

        Args:
            input_data: The node input.

        Returns:
            The last user message content, or first message if no user role,
            or empty string if no messages.
        """
        from tinycua.models.node_input import (
            NodeInput,
            convert_node_input_to_messages,
        )

        messages: list[dict[str, Any]] = []

        if isinstance(input_data, NodeInput):
            messages = input_data.messages
        else:
            try:
                messages = convert_node_input_to_messages(input_data)
            except (ValueError, TypeError):
                return ""

        if not messages:
            return ""

        # Try to find the last user message
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return str(msg.get("content", ""))

        # Fallback to first message content
        first = messages[0]
        return str(first.get("content", ""))

    def on_complete(self, queue: NodeQueue, response: Any) -> None:  # type: ignore[override]
        """Post-completion hook for queue mutations.

        Args:
            queue: The node queue that can be mutated.
            response: The final LLM response (DecisionResult or raw).
        """
        # The actual route dispatch happens via the DecisionNode flow
        # We need to handle the "worker" route dispatch here
        super().on_complete(queue, response)
