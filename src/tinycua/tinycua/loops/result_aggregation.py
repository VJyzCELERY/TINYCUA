"""TinyCUAResultAggregationNode — read-only aggregation of accepted root task trees.

Performs guided BFS right-to-left traversal of the accepted root task tree,
consolidates task results, artifacts, and reviewer decisions, and produces an
AggregatedResult for ResponseNode consumption.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tinycua.loops.node import NodeExecutionError, ProcessNode

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike
    from tinycua.models.task import Task, TaskResult

logger = logging.getLogger(__name__)


@dataclass
class AggregatedResult:
    """Consolidated result from traversing an accepted root task tree.

    Attributes:
        root_task_id: The ID of the root task that was accepted.
        task_summaries: Human-readable summaries of each inspected task.
        accepted_results: TaskResult objects from accepted tasks.
        artifacts: Artifact dicts collected from task results.
        final_context: Consolidated context string for ResponseNode.
            Built by joining each task summary ("{title}: {summary}" or
            "{title}: not_executed") with newline separators, prefixed
            with the root task title.
        response_continuation: Continuation text to guide ResponseNode synthesis.
            Implementation-defined for MVP; empty string is valid.
        metadata: Additional metadata (traversal depth, count of tasks
            inspected, etc.).
    """

    root_task_id: str
    task_summaries: list[str] = field(default_factory=list)
    accepted_results: list[TaskResult] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    final_context: str = ""
    response_continuation: str = ""
    metadata: dict = field(default_factory=dict)


class TinyCUAResultAggregationNode(ProcessNode):
    """Read-only aggregation node for accepted root task trees.

    Extends ProcessNode with node_id="result_aggregation".  Performs guided
    BFS right-to-left traversal of the accepted root task tree, consolidates
    task results/artifacts/reviewer decisions, and produces an AggregatedResult
    for ResponseNode.

    Attributes:
        node_id: Always "result_aggregation" by default.
        loop: Optional reference to TinyCUALoop for accessing root_task
            and session context.
    """

    def __init__(
        self,
        node_id: str = "result_aggregation",
        config: NodeConfigBase | None = None,
        loop: Any | None = None,
    ) -> None:
        """Initialize TinyCUAResultAggregationNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            loop: Optional reference to TinyCUALoop.
        """
        super().__init__(
            node_id=node_id,
            config=config,  # type: ignore[arg-type]
            instruction="",
        )
        self.loop = loop

    def __call__(self, input_data: NodeInputLike) -> LLMResult:
        """Execute the aggregation node.

        1. Guard: assert session is attached and root task is done.
        2. Traverse task tree: ``list(self._traverse_bfs_right_to_left(root_task))``.
        3. Consolidate: ``result = self._consolidate(traversal_results)``.
        4. Record result to session context / response metadata.
        5. ``propagate()``.
        6. Return ``LLMResult`` with ``AggregatedResult`` in
           ``metadata["aggregated_result"]``.

        Args:
            input_data: Node input (not used directly; traversal reads from
                session/loop root task).

        Returns:
            LLMResult with AggregatedResult in metadata.

        Raises:
            NodeExecutionError: If session is not attached, no root task is
                available, or root task is not done.
        """
        if self.session is None:
            msg = f"Node {self.node_id} has no session attached"
            raise NodeExecutionError(msg)

        # Resolve root task: prefer loop.root_task, fall back to session.task
        root_task = None
        if self.loop is not None and hasattr(self.loop, "root_task"):
            root_task = self.loop.root_task
        if root_task is None and hasattr(self.session, "task"):
            root_task = self.session.task  # type: ignore[union-attr]

        if root_task is None:
            msg = f"Node {self.node_id}: no root task available"
            raise NodeExecutionError(msg)

        if root_task.status != "done":
            msg = (
                f"Node {self.node_id}: root task is not done "
                f"(status={root_task.status})"
            )
            raise NodeExecutionError(msg)

        # Traverse and consolidate
        traversal_results = list(self._traverse_bfs_right_to_left(root_task))
        result = self._consolidate(traversal_results)

        # Record to session context
        if result.final_context:
            self.session.session_context.append(
                {
                    "role": "assistant",
                    "content": f"[AggregatedResult] {result.final_context}",
                }
            )

        self.propagate()

        from tinycua.config.types import LLMResult

        return LLMResult(
            content=result.final_context,
            role="assistant",
            metadata={"aggregated_result": result},
        )

    def _traverse_bfs_right_to_left(
        self,
        task: Task,
        max_inspected_tasks: int | None = None,
        context_sufficient_fn: Callable[[Task, AggregatedResult], bool] | None = None,
    ) -> Iterator[Task]:
        """Generator-based guided BFS right-to-left / most-recent-first.

        Uses ``collections.deque`` with a reversed children queue so that
        children are visited right-to-left (most-recent-first).

        Supports early termination via:
        - ``max_inspected_tasks`` threshold: stop after yielding N tasks.
        - ``context_sufficient_fn`` callback: called for each inspected task
          with ``(current_task, partial_result)``.  Return ``True`` to stop.
          The ``partial_result`` is built incrementally from already-inspected
          tasks via ``_update_partial_from_task``.

        Args:
            task: The root task to start traversal from.
            max_inspected_tasks: Maximum number of tasks to yield before
                stopping.  ``None`` means no limit.
            context_sufficient_fn: Optional callback to check if enough
                context has been gathered.  Called with the current task and
                a partial AggregatedResult built so far.

        Yields:
            Each inspected Task in BFS right-to-left order.
        """
        queue: deque[Task] = deque()
        queue.append(task)
        inspected = 0
        partial_result = AggregatedResult(root_task_id=task.task_id)

        while queue:
            current = queue.popleft()

            # Early termination: max_inspected_tasks
            if max_inspected_tasks is not None and inspected >= max_inspected_tasks:
                break

            yield current
            inspected += 1

            # Update partial result from this task (for context_sufficient_fn)
            self._update_partial_from_task(partial_result, current)

            # Early termination: context_sufficient_fn callback
            if context_sufficient_fn is not None:
                if context_sufficient_fn(current, partial_result):
                    break

            # Enqueue children right-to-left (most-recent-first)
            if current.children:
                # Reverse so rightmost child is dequeued first
                for child in reversed(current.children):
                    queue.append(child)

    def _update_partial_from_task(
        self, partial: AggregatedResult, task: Task
    ) -> None:
        """Update a partial AggregatedResult from a single task's data.

        This is incremental — called for each task during traversal so
        ``context_sufficient_fn`` can make decisions based on partial state.

        Args:
            partial: The partial AggregatedResult to update.
            task: The task whose data to incorporate.
        """
        # Build task summary
        if task.result and task.result.summary:
            summary = f"{task.title}: {task.result.summary}"
        else:
            summary = f"{task.title}: not_executed"
        partial.task_summaries.append(summary)

        # Collect TaskResult if present
        if task.result is not None:
            partial.accepted_results.append(task.result)
            # Collect artifacts if present
            if task.result.artifacts:
                partial.artifacts.extend(task.result.artifacts)

    def _consolidate(self, traversal_results: list[Task]) -> AggregatedResult:
        """Build an AggregatedResult from a list of inspected tasks.

        Delegates to ``_update_partial_from_task`` for each task to avoid
        duplicating summary-building logic.  Then sets ``final_context``
        and ``metadata``.

        Args:
            traversal_results: List of tasks from the traversal, in
                BFS right-to-left order.

        Returns:
            An AggregatedResult containing the consolidated data.
        """
        if not traversal_results:
            return AggregatedResult(root_task_id="")

        result = AggregatedResult(root_task_id=traversal_results[0].task_id)

        for task in traversal_results:
            self._update_partial_from_task(result, task)

        result.final_context = "\n".join(result.task_summaries)
        result.metadata = {
            "task_count": len(traversal_results),
            "depth": self._max_depth(traversal_results),
        }

        return result

    def _max_depth(self, tasks: list[Task]) -> int:
        """Compute the actual maximum depth among a list of tasks.

        Builds a parent map in a single pass, then computes depths in a
        second pass for O(n) time complexity.  The root task is depth 0,
        its children depth 1, etc.

        Args:
            tasks: List of tasks from traversal (BFS order).

        Returns:
            Maximum depth (0 for root, 1 for children, etc.).
        """
        if not tasks:
            return 0

        depth_map: dict[str, int] = {tasks[0].task_id: 0}
        child_to_parent: dict[str, str] = {}
        for task in tasks:
            for child in task.children or []:
                child_to_parent[child.task_id] = task.task_id

        for task in tasks:
            parent_id = child_to_parent.get(task.task_id)
            if parent_id is not None:
                depth_map[task.task_id] = depth_map.get(parent_id, 0) + 1

        return max(depth_map.values())

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Post-completion hook: advance the queue to ResponseNode.

        Args:
            queue: The node queue to advance.
            response: The LLM response containing AggregatedResult
                in metadata.
        """
        logger.info(
            "node=%s on_complete — advancing queue",
            self.node_id,
        )
        queue.advance()
