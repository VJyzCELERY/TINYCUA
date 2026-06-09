"""TinyCUAWorkerNode — concrete DecisionNode for task planning and execution orchestration."""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

from tinycua.loops.node import DecisionNode, DecisionResult
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.route_map import RouteMap

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node import Node
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)


class WorkerRouteLabel(str, Enum):
    """Route labels for WorkerNode routing.

    All five labels are implemented:
    - task_creation: Deterministic (no LLM), creates task from scratch
    - task_recreation: LLM-assisted, recreates task with TaskInit/TaskCreate tools
    - task_reanalysis: LLM-assisted, reanalyzes task without TaskInit/TaskCreate
    - passthrough: LLM-assisted, forwards to next worker-spawned node
    - proceed_execution: LLM-assisted, ensures terminal response path
    """

    task_creation = "task_creation"
    task_recreation = "task_recreation"
    task_reanalysis = "task_reanalysis"
    passthrough = "passthrough"
    proceed_execution = "proceed_execution"


# Default classification labels for WorkerNode
_DEFAULT_WORKER_LABELS: tuple[str, ...] = tuple(label.value for label in WorkerRouteLabel)


class TinyCUAWorkerNode(DecisionNode):
    """Concrete DecisionNode for task planning and execution orchestration.

    Replaces old worker subgraph and worker QueryAnalyst input gate.
    Performs deterministic prechecks before LLM decision.

    Attributes:
        node_id: Always "worker" by default.
        route_map: Dispatch table for classification labels.
        default_response_node: Terminal node for ensure_terminal() calls.
    """

    default_response_node: Node  # Terminal node for ensure_terminal() calls

    def __init__(
        self,
        node_id: str = "worker",
        config: NodeConfigBase | None = None,
        route_map: RouteMap | None = None,
        effort: str = "none",
    ) -> None:
        """Initialize WorkerNode with default classification labels.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            route_map: Optional pre-configured RouteMap. Created with
                default handlers if None.
            effort: WorkerEffort level ("none", "low", "medium", "high").
                Defaults to "none" (pass_limit=0).
        """
        super().__init__(
            node_id=node_id,
            config=config,  # type: ignore[arg-type]
            instruction=(
                "You are a worker node that orchestrates task planning and execution. "
                "Analyze the current task state and determine the next route "
                "(e.g., task_creation, task_recreation). Delegate task execution "
                "to specialized downstream nodes."
            ),
            classification_labels=list(_DEFAULT_WORKER_LABELS),  # All five labels
        )
        self.default_response_node = ResponseNode(config=self.config)
        self.route_map = route_map or self._build_default_route_map()
        self._queue: NodeQueue | None = None
        self._last_input: NodeInputLike | None = None
        self._effort = effort

    def _build_default_route_map(self) -> RouteMap:
        """Build the default RouteMap with all five route handlers.

        Returns:
            A configured RouteMap with all route handlers.
        """
        route_map = RouteMap()
        route_map.register(
            WorkerRouteLabel.task_creation.value, self._route_task_creation,
        )
        route_map.register(
            WorkerRouteLabel.task_recreation.value, self._route_task_recreation,
        )
        route_map.register(
            WorkerRouteLabel.task_reanalysis.value, self._route_task_reanalysis,
        )
        route_map.register(
            WorkerRouteLabel.passthrough.value, self._route_passthrough,
        )
        route_map.register(
            WorkerRouteLabel.proceed_execution.value, self._route_proceed_execution,
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

    def _has_worker_spawned_nodes(self, queue: NodeQueue) -> bool:
        """Check if worker-spawned nodes exist in the queue.

        Convenience wrapper around _detect_worker_spawned_nodes() that
        returns a boolean instead of the list.

        Args:
            queue: The node queue to search.

        Returns:
            True if worker-spawned nodes exist, False otherwise.
        """
        return len(self._detect_worker_spawned_nodes(queue)) > 0

    def _get_classification_labels(self, queue: NodeQueue) -> list[str]:
        """Return dynamic classification labels based on queue state.

        Always includes task_recreation, task_reanalysis, proceed_execution.
        Includes passthrough only when worker-spawned nodes exist.

        Args:
            queue: The node queue to check for worker-spawned nodes.

        Returns:
            List of valid classification labels.
        """
        labels = [
            WorkerRouteLabel.task_recreation.value,
            WorkerRouteLabel.task_reanalysis.value,
            WorkerRouteLabel.proceed_execution.value,
        ]
        if self._has_worker_spawned_nodes(queue):
            labels.append(WorkerRouteLabel.passthrough.value)
        return labels

    def _route_task_creation(
        self, queue: NodeQueue, result: DecisionResult,
    ) -> None:
        """Deterministic route: spawn TaskCreateNode then TaskAnalyzerNode.

        Clears the queue after current and spawns TaskCreateNode followed by
        TaskAnalyzerNode (mode=initial_analysis), ensuring terminal response
        path is maintained.

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
        queue.ensure_terminal(self.default_response_node)

        logger.info(
            "node=%s route_task_creation spawned task_create, task_analyzer",
            self.node_id,
        )

    def _route_task_recreation(
        self, queue: NodeQueue, result: DecisionResult,
    ) -> None:
        """LLM-assisted route: clear worker-spawned nodes, spawn TaskAnalyzerNode with TaskInit/TaskCreate tools.

        Clears the queue after current and spawns TaskAnalyzerNode with
        mode="analysis" (includes TaskInit/TaskCreate tools), ensuring
        terminal response path is maintained.

        Args:
            queue: The node queue (may be mutated to spawn task_analyzer).
            result: The decision result.
        """
        from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

        # Clear stale worker-spawned nodes
        queue.clear_after_current()

        # Spawn TaskAnalyzerNode with analysis mode (includes TaskInit/TaskCreate)
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=self.config,
            mode="analysis",
        )
        queue.spawn_after_current([task_analyzer])

        # Ensure terminal response path is maintained
        queue.ensure_terminal(self.default_response_node)

        logger.info(
            "node=%s route_task_recreation spawned task_analyzer (mode=analysis)",
            self.node_id,
        )

    def _route_task_reanalysis(
        self, queue: NodeQueue, result: DecisionResult,
    ) -> None:
        """LLM-assisted route: clear worker-spawned nodes, spawn TaskAnalyzerNode without TaskInit/TaskCreate.

        Clears the queue after current and spawns TaskAnalyzerNode with
        mode="initial_analysis" (excludes TaskInit/TaskCreate tools),
        ensuring terminal response path is maintained.

        Args:
            queue: The node queue (may be mutated to spawn task_analyzer).
            result: The decision result.
        """
        from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode

        # Clear stale worker-spawned nodes
        queue.clear_after_current()

        # Spawn TaskAnalyzerNode with initial_analysis mode (excludes TaskInit/TaskCreate)
        task_analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer", config=self.config,
            mode="initial_analysis",
        )
        queue.spawn_after_current([task_analyzer])

        # Ensure terminal response path is maintained
        queue.ensure_terminal(self.default_response_node)

        logger.info(
            "node=%s route_task_reanalysis spawned task_analyzer (mode=initial_analysis)",
            self.node_id,
        )

    def _route_passthrough(
        self, queue: NodeQueue, result: DecisionResult,
    ) -> None:
        """LLM-assisted route: advance queue and forward input to next worker-spawned node.

        WorkerNode is transient; after forwarding, the next node takes over.
        Does NOT re-insert WorkerNode into the queue.

        Args:
            queue: The node queue (may be mutated to advance and forward input).
            result: The decision result.
        """
        from tinycua.loops.node import NodeExecutionError

        # Defensive validation: check that worker-spawned nodes exist
        if not self._has_worker_spawned_nodes(queue):
            msg = (
                f"Node {self.node_id}: passthrough dispatched but no "
                "worker-spawned nodes exist in queue"
            )
            raise NodeExecutionError(msg)

        # Get the next node (items[1]) before advancing
        next_node = queue.items[1]

        # Advance to remove worker from front of queue
        queue.advance()

        # Forward input to the next worker-spawned node
        if self._last_input is not None:
            queue.set_input(next_node, self._last_input)

        logger.info(
            "node=%s route_passthrough forwarded to next node",
            self.node_id,
        )

    def _route_proceed_execution(
        self, queue: NodeQueue, result: DecisionResult,
    ) -> None:
        """LLM-assisted route: ensure terminal response path (Milestone 2.3).

        TaskExecutor and ResultReviewer spawning deferred to Milestone 3.2 (Phase 2).
        Handler ensures queue reaches stable state with terminal response.

        Args:
            queue: The node queue (may be mutated to ensure terminal path).
            result: The decision result.
        """
        # Ensure terminal response path is maintained
        queue.ensure_terminal(self.default_response_node)

        logger.info(
            "node=%s route_proceed_execution ensured terminal response path",
            self.node_id,
        )

    def on_complete(self, queue: NodeQueue, result: DecisionResult) -> None:  # type: ignore[override]
        """Dispatch route after classification.

        Accepts DecisionResult (not LLMResult | DecisionResult) because
        WorkerNode's __call__ returns a structured decision result.

        Stores the queue reference for dynamic label adjustment on the
        next __call__ invocation.

        Args:
            queue: The node queue (may be mutated by route handler).
            result: The decision result from classification.
        """
        self._queue = queue
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

        # Store input for passthrough forwarding
        self._last_input = input

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

        # Task exists — adjust labels dynamically based on queue state
        if self._queue is not None:
            self.classification_labels = self._get_classification_labels(self._queue)

        # Delegate to standard LLM decision flow (Milestone 2.3)
        return super().__call__(input)
