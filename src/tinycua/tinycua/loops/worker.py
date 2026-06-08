"""TinyCUAWorkerNode — concrete DecisionNode for task planning and execution orchestration."""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from tinycua.loops.node import DecisionNode, DecisionResult
from tinycua.loops.route_map import RouteMap

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node import Node
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)


class WorkerRouteLabel(str, Enum):
    """Route labels for WorkerNode routing.

    Only task_creation is implemented in this milestone.
    Remaining labels (task_recreation, task_reanalysis, passthrough,
    proceed_execution) are deferred to Milestone 2.3 — see design.md:46-51.
    """

    task_creation = "task_creation"


# Default classification labels for WorkerNode
_DEFAULT_WORKER_LABELS: list[str] = [label.value for label in WorkerRouteLabel]


class TinyCUAWorkerNode(DecisionNode):
    """Concrete DecisionNode for task planning and execution orchestration.

    Replaces old worker subgraph and worker QueryAnalyst input gate.
    Performs deterministic prechecks before LLM decision.

    Attributes:
        node_id: Always "worker" by default.
        route_map: Dispatch table for classification labels.
    """

    def __init__(
        self,
        node_id: str = "worker",
        config: NodeConfigBase | None = None,
        route_map: RouteMap | None = None,
    ) -> None:
        """Initialize WorkerNode with default classification labels.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            route_map: Optional pre-configured RouteMap. Created with
                default handlers if None.
        """
        super().__init__(
            node_id=node_id,
            config=config,  # type: ignore[arg-type]
            instruction=(
                "You are a worker node. Analyze the current task state and "
                "determine the next action. You have access to task tools "
                "for creating and managing tasks."
            ),
            classification_labels=list(_DEFAULT_WORKER_LABELS),
        )
        self.route_map = route_map or self._build_default_route_map()

    def _build_default_route_map(self) -> RouteMap:
        """Build the default RouteMap with task_creation handler.

        Returns:
            A configured RouteMap with default route handlers.
        """
        route_map = RouteMap()
        route_map.register(
            WorkerRouteLabel.task_creation.value, self._route_task_creation,
        )
        return route_map

    def _detect_task_exists(self) -> bool:
        """Check if a task already exists in the session.

        Returns:
            True if session.task is set and non-empty, False otherwise.
        """
        if self.session is None:
            return False
        return self.session.task is not None and len(self.session.task) > 0

    def _detect_worker_spawned_nodes(self, queue: NodeQueue) -> list[Node]:
        """Find worker-owned nodes in the queue before terminal ResponseNode.

        Args:
            queue: The node queue to search.

        Returns:
            List of worker-spawned nodes.
        """
        return queue.find_worker_spawned_nodes()

    def _route_task_creation(
        self, queue: NodeQueue, result: DecisionResult,
    ) -> None:
        """Deterministic route: spawn TaskCreateNode for root task creation.

        Clears the queue after current and spawns TaskCreateNode,
        ensuring terminal response path is maintained.

        Args:
            queue: The node queue (may be mutated to spawn task_create).
            result: The decision result.
        """
        from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
        from tinycua.loops.task_create import TinyCUATaskCreateNode

        # Clear stale worker-spawned nodes
        queue.clear_after_current()

        # Spawn TaskCreateNode and TaskAnalyzerNode after current worker
        task_create = TinyCUATaskCreateNode(
            node_id="task_create", config=self.config,
        )
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=self.config,
            mode="initial_analysis",
        )
        queue.spawn_after_current([task_create, task_analyzer])

        # Ensure terminal response path is maintained
        from tinycua.loops.response_node import ResponseNode

        default_terminal = ResponseNode(config=self.config)
        queue.ensure_terminal(default_terminal)

        logger.info(
            "node=%s route_task_creation spawned task_create, task_analyzer",
            self.node_id,
        )

    def on_complete(self, queue: NodeQueue, result: DecisionResult) -> None:  # type: ignore[override]
        """Dispatch route after classification.

        Accepts DecisionResult (not LLMResult | DecisionResult) because
        WorkerNode's __call__ returns a structured decision result.

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
        """Execute the worker node with deterministic precheck.

        Performs deterministic precheck for task_creation before LLM decision.
        When no task exists, routes to task_creation without LLM calls.

        Args:
            input: The node input.

        Returns:
            DecisionResult with route label and LLM responses.
        """
        if self.session is None:
            from tinycua.loops.node import NodeExecutionError

            msg = f"Node {self.node_id} has no session attached"
            raise NodeExecutionError(msg)

        # Deterministic precheck: if no task exists, route to task_creation
        if not self._detect_task_exists():
            from tinycua.config.types import LLMResult

            logger.info(
                "node=%s no task exists, deterministic route to task_creation",
                self.node_id,
            )
            # Record the decision without LLM calls
            self.session.session_context.append(
                {
                    "role": "assistant",
                    "content": "[Deterministic] task_creation: no task exists",
                }
            )
            return DecisionResult(
                route_label=WorkerRouteLabel.task_creation.value,
                analysis_response=LLMResult(
                    content="No task exists, routing to task_creation",
                    role="assistant",
                ),
                classification_response=LLMResult(
                    content=WorkerRouteLabel.task_creation.value,
                    role="assistant",
                ),
            )

        # Task exists — delegate to standard LLM decision flow (Milestone 2.3)
        return super().__call__(input)
