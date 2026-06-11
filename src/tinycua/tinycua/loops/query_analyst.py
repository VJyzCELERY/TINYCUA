"""TinyCUAQueryAnalystNode — top-level entry DecisionNode for TinyCUA."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionNode, DecisionResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.route_map import RouteMap
from tinycua.models.classification import (
    PASSTHROUGH,
    UNCERTAIN,
    WORKER,
    MandatoryPassthrough,
)
from tinycua.models.node_input import NodeInput, NodeInputLike

if TYPE_CHECKING:
    from tinycua.loops.node import Node

logger = logging.getLogger(__name__)

# Default classification labels for QueryAnalyst
_DEFAULT_LABELS = [PASSTHROUGH, WORKER, UNCERTAIN]


class TinyCUAQueryAnalystNode(DecisionNode):
    """Top-level entry DecisionNode for TinyCUA.

    Classifies user input into passthrough/worker/uncertain using a
    two-step decision process (analysis + classification) and routes
    the queue via RouteMap dispatch.

    When MandatoryPassthrough is present in input metadata, classification
    is bypassed and routing is deterministic.

    Attributes:
        node_id: Always "query_analyst" by default.
        route_map: Dispatch table for classification labels.
    """

    def __init__(
        self,
        node_id: str = "query_analyst",
        config: NodeConfigBase | None = None,
        route_map: RouteMap | None = None,
    ) -> None:
        """Initialize QueryAnalyst with default classification labels.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            route_map: Optional pre-configured RouteMap. Created with
                default handlers if None.
        """
        super().__init__(
            node_id=node_id,
            config=config or NodeConfigBase(),
            instruction=(
                "You are a query analyst. Analyze the user's input and classify it "
                "into one of these categories: passthrough, worker, uncertain. "
                "Passthrough means the input should be forwarded directly to a target. "
                "Worker means the input requires active work/processing. "
                "Uncertain means the input is unclear or ambiguous."
            ),
            classification_labels=list(_DEFAULT_LABELS),
        )
        self.route_map = route_map or self._build_default_route_map()

    def _build_default_route_map(self) -> RouteMap:
        """Build the default RouteMap with passthrough/worker/uncertain handlers.

        Returns:
            A configured RouteMap with default route handlers.
        """
        route_map = RouteMap()
        route_map.register(PASSTHROUGH, self.route_passthrough)
        route_map.register(WORKER, self.route_worker)
        route_map.register(UNCERTAIN, self.route_uncertain)
        return route_map

    def check_mandatory_passthrough(
        self, input_data: NodeInputLike
    ) -> MandatoryPassthrough | None:
        """Check for a valid MandatoryPassthrough in the input metadata.

        Args:
            input_data: The node input to check.

        Returns:
            The MandatoryPassthrough directive if found and valid, None otherwise.
        """
        if not isinstance(input_data, NodeInput):
            return None

        mandatory = input_data.metadata.get("mandatory_passthrough")
        if mandatory is None:
            return None

        if not isinstance(mandatory, MandatoryPassthrough):
            logger.warning(
                "node=%s mandatory_passthrough is not MandatoryPassthrough type: %s",
                self.node_id,
                type(mandatory),
            )
            return None

        # Stale guard: check if session IDs match
        if (
            self.session is not None
            and mandatory.target_session_id is not None
            and mandatory.target_session_id != self.session.session_id
        ):
            if mandatory.allow_query_analyst_restart:
                logger.info(
                    "node=%s stale passthrough with allow_restart, dropping",
                    self.node_id,
                )
                return None
            logger.warning(
                "node=%s stale passthrough without allow_restart, dropping",
                self.node_id,
            )
            return None

        return mandatory

    def find_existing_worker(self, queue: NodeQueue) -> Node | None:
        """Find an existing WorkerNode in the queue before terminal ResponseNode.

        Delegates to NodeQueue.find_existing_worker_node() for worker-node
        lookup to avoid duplicating logic with WorkerNode's detection.

        Args:
            queue: The node queue to search.

        Returns:
            The existing worker node, or None if not found.
        """
        return queue.find_existing_worker_node()

    def route_passthrough(self, queue: NodeQueue, result: DecisionResult) -> None:
        """Route handler for passthrough label.

        Forwards the input directly to the target node/session without
        further processing. This is a no-op at the queue level since
        the actual forwarding happens via MandatoryPassthrough metadata.

        Args:
            queue: The node queue (not mutated for passthrough).
            result: The decision result.
        """
        logger.info(
            "node=%s route_passthrough target=%s",
            self.node_id,
            result.route_label,
        )
        # Passthrough is a no-op at queue level — the orchestrator
        # handles forwarding based on MandatoryPassthrough metadata.

    def route_worker(self, queue: NodeQueue, result: DecisionResult) -> None:
        """Route handler for worker label.

        If a WorkerNode already exists in the queue, reuse it.
        Otherwise, spawn a new TinyCUAWorkerNode after the current node.

        Args:
            queue: The node queue (may be mutated to spawn worker).
            result: The decision result.
        """
        existing_worker = self.find_existing_worker(queue)
        if existing_worker is not None:
            logger.info(
                "node=%s route_worker reusing existing worker=%s",
                self.node_id,
                existing_worker.node_id,
            )
            return

        # Spawn a new TinyCUAWorkerNode (Milestone 2.2)
        from tinycua.loops.worker import TinyCUAWorkerNode

        worker_node = TinyCUAWorkerNode(
            node_id="worker", config=self.config,
        )
        queue.spawn_after_current([worker_node])

        # Ensure terminal response path is maintained after spawning worker
        from tinycua.loops.response_node import TinyCUAResponseNode

        default_terminal = TinyCUAResponseNode(config=self.config)
        queue.ensure_terminal(default_terminal)

        logger.info("node=%s route_worker spawned new worker", self.node_id)

    def route_uncertain(self, queue: NodeQueue, result: DecisionResult) -> None:
        """Route handler for uncertain label.

        QueryAnalyst stays active and waits for more user input.
        Queue does not advance.

        Args:
            queue: The node queue (not mutated for uncertain).
            result: The decision result.
        """
        logger.info("node=%s route_uncertain — remaining active", self.node_id)
        # No-op: QueryAnalyst stays at queue front, waiting for continuation.

    def on_complete(self, queue: NodeQueue, result: DecisionResult) -> None:  # type: ignore[override]
        """Dispatch route after classification.

        Note: `on_complete` accepts `DecisionResult` (not `LLMResult` like the base `Node`)
        because QueryAnalyst's `__call__` returns a structured decision result containing
        the route label alongside LLM responses. The queue mutation logic (RouteMap dispatch)
        depends on the route label, not just the raw LLM output.

        Args:
            queue: The node queue (may be mutated by route handler).
            result: The decision result from classification.
        """
        logger.info(
            "node=%s on_complete route_label=%s",
            self.node_id,
            result.route_label,
        )
        self.route_map.dispatch(result.route_label, queue, result)

    def __call__(self, input: NodeInputLike) -> DecisionResult:  # type: ignore[override]
        """Execute the decision node with mandatory_passthrough precheck.

        Checks for MandatoryPassthrough first. If present, short-circuits
        to passthrough without LLM classification. Otherwise, delegates
        to the parent DecisionNode's two-step flow.

        Args:
            input: The node input.

        Returns:
            DecisionResult with route label and LLM responses.

        Raises:
            NodeExecutionError: If no session is attached or LLM fails.
        """
        # Precheck: mandatory_passthrough overrides LLM classification
        mandatory = self.check_mandatory_passthrough(input)
        if mandatory is not None:
            logger.info(
                "node=%s mandatory_passthrough detected, bypassing LLM",
                self.node_id,
            )
            # Record the passthrough decision without LLM calls
            if self.session is not None:
                self.session.session_context.append(
                    {
                        "role": "assistant",
                        "content": f"[Passthrough] target={mandatory.target_node_id} reason={mandatory.reason}",
                    }
                )
            return DecisionResult(
                route_label=PASSTHROUGH,
                analysis_response=LLMResult(content="", role="assistant"),
                classification_response=LLMResult(content=PASSTHROUGH, role="assistant"),
            )

        # Standard two-step decision flow
        return super().__call__(input)


