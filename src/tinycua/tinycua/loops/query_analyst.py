"""QueryAnalystNode for classifying and routing user input."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from tinycua.config.node_config import create_node_config
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node import DecisionNode, DecisionResult, Node
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.node_input import NodeInput, convert_node_input_to_messages
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)

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

    ROUTE_LABELS: ClassVar[list[str]] = ["worker", "uncertain", "passthrough"]

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

    def _route_worker(self, _input_data: NodeInputLike = "") -> None:
        """Route to WorkerNode with information digestion.

        1. Check if target Worker session already has DigestedInformation
           → If yes, advance to existing Worker (no digest spawn)
        2. Otherwise, spawn InformationDigesterNode before WorkerNode
           → queue.spawn_after_current([digester, worker_node])

        Args:
            _input_data: The node input (kept for API compatibility).
        """
        queue = self._queue

        if queue is None:
            logger.warning("QueryAnalyst._route_worker called but _queue is not set")
            return

        # Create WorkerNode
        worker_node = TinyCUAWorkerNode(
            node_id="worker",
            config=create_node_config("worker", self.config),
        )

        # Attach a session to the worker
        worker_session = Session()
        worker_node.session = worker_session

        # Check for existing digest
        if self._check_existing_digest(worker_node):
            # Already digested — just ensure worker is in queue
            queue.spawn_after_current([worker_node])
            return

        # Create InformationDigesterNode
        digester = TinyCUAInformationDigesterNode(
            node_id="digester",
            config=create_node_config("information_digester", self.config),
        )

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
            # Handle both dict and SessionContextEntry
            if isinstance(entry, dict):
                content = entry.get("content")
            else:
                content = entry.content
            if isinstance(content, DigestedInformation):
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

    def on_complete(
        self, queue: NodeQueue, response: LLMResult | DecisionResult
    ) -> None:
        """Post-completion hook for queue mutations.

        Dispatches to the appropriate route handler based on the
        classification result. For the "worker" route, spawns
        InformationDigesterNode before WorkerNode.

        Args:
            queue: The node queue that can be mutated.
            response: The final LLM response (LLMResult or DecisionResult).
        """
        if isinstance(response, DecisionResult):
            route_label = response.route_label
        else:
            route_label = response.content.strip().lower()

        if route_label == "worker":
            self._route_worker()
        elif route_label == "uncertain":
            policy = getattr(
                self.config.metadata.get("session_config"),
                "interaction_policy",
                None,
            )
            strategy = getattr(policy, "uncertain_strategy", "fallback_response")
            if strategy == "route_worker":
                self._route_worker()
            elif strategy == "ask" and not getattr(policy, "hitl_enabled", False):
                logger.info("QueryAnalyst uncertain with HITL disabled — fallback response")
            elif strategy == "fail":
                raise RuntimeError("QueryAnalyst uncertain route failed by policy")
            else:
                logger.info("QueryAnalyst routed to 'uncertain' — fallback response")
        elif route_label == "passthrough":
            logger.info("QueryAnalyst routed to 'passthrough' — no action taken")
        else:
            logger.warning("QueryAnalyst unknown route: %s", route_label)
        super().on_complete(queue, response)
