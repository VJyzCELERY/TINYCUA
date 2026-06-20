"""WorkerNode for task planning and execution orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from tinycua.loops.node import DecisionNode, DecisionResult
from tinycua.config.node_config import create_node_config
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.task_nodes import (
    TinyCUAAnalysisEffortNode,
    TinyCUAResultReviewerNode,
    TinyCUATaskAnalyzerNode,
    TinyCUATaskExecutorNode,
)
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.node_handoff import NodeHandoff
from tinycua.tools.routing import WorkerRouteSelectionTool

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike
    from tinycua.models.session import Session

_WORKER_INSTRUCTION = (
    "You are a worker node responsible for task planning and execution "
    "orchestration. Analyze the request context and determine the "
    "appropriate next step: create tasks, recreate tasks, reanalyze, "
    "pass through, or proceed with execution. You MUST call "
    "select_worker_route with exactly one route. Do not produce a text-only route answer; "
    "the route decision must be expressed by the function call: task_creation, task_recreation, "
    "task_reanalysis, passthrough, or proceed_execution. Choose "
    "task_creation for a new task plan that has not yet been initialized. Do not "
    "answer the user directly from this node."
)

_WORKER_CONTINUATION = (
    "Based on the request context and current task state above, call "
    "select_worker_route with the next Worker route. Do not answer the user "
    "directly from this node."
)


class TinyCUAWorkerNode(DecisionNode):
    """Decision hub for task planning and execution orchestration.

    Receives DigestedInformation from session_context (populated by
    InformationDigesterNode spawned by QueryAnalyst).

    Attributes:
        ROUTE_LABELS: Allowed classification labels for routing.
        _current_digest: The current DigestedInformation for propagation.
    """

    ROUTE_LABELS: ClassVar[list[str]] = [
        "task_creation",
        "task_recreation",
        "task_reanalysis",
        "passthrough",
        "proceed_execution",
    ]

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _WORKER_INSTRUCTION,
        classification_labels: list[str] | None = None,
        is_terminal: bool = False,
    ) -> None:
        """Initialize WorkerNode.

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
            continuation=_WORKER_CONTINUATION,
            classification_labels=classification_labels or self.ROUTE_LABELS,
            is_terminal=is_terminal,
        )
        self._current_digest: DigestedInformation | None = None
        # ponytail: cache the route-selection tool per label-set so identical
        # valid-route sets reuse the same tool object and keep the tools-prefix
        # byte-stable for prompt caching (FR-018).
        self._route_tool_cache: dict[tuple[str, ...], object] = {}

    def state_valid_route_labels(self) -> list[str]:
        """Return only worker routes that are valid for current task state."""
        if self.session is None or self.session.task_store.root_task_id is None:
            return ["task_creation"]
        return [
            "task_recreation",
            "task_reanalysis",
            "passthrough",
            "proceed_execution",
        ]

    def refresh_route_options(self) -> None:
        """Refresh worker route schema and classifier labels from session state.

        Caches the route tool per label-set (FR-018) so identical label sets
        reuse the same tool object — keeps the tools-prefix byte-stable for
        prompt caching. Rebuilds only when the valid labels actually change.
        """
        labels = self.state_valid_route_labels()
        self.classification_labels = labels
        cache_key = tuple(labels)
        cached = self._route_tool_cache.get(cache_key)
        if cached is None:
            cached = WorkerRouteSelectionTool(labels)
            self._route_tool_cache[cache_key] = cached
        for index, tool in enumerate(self.config.tool_policy.node_tools):
            if tool.name == "select_worker_route":
                self.config.tool_policy.node_tools[index] = cached
                break

    def build_messages(
        self,
        session: Session,
        input: NodeInputLike,
        resolved_tools: list[object] | None = None,
    ) -> list[dict[str, str]]:
        """Refresh dynamic route choices before each worker LLM request."""
        self.refresh_route_options()
        if isinstance(input, NodeHandoff):
            digest = input.payload.get("digested_information")
            if isinstance(digest, DigestedInformation):
                self._current_digest = digest
        return super().build_messages(session, input, resolved_tools)

    def _get_digested_input(self) -> DigestedInformation | None:
        """Retrieve DigestedInformation from session_context.

        Scans session_context for the most recent DigestedInformation
        entry. Returns None if not found (fallback to raw user_query).

        Returns:
            The most recent DigestedInformation, or None if not found.
        """
        if self.session is None:
            return None

        for entry in reversed(self.session.session_context):
            # Handle both dict and SessionContextEntry
            if isinstance(entry, dict):
                content = entry.get("content")
            else:
                content = entry.content
            if isinstance(content, DigestedInformation):
                return content

        return None

    def propagate(self) -> None:
        """Forward DigestedInformation to downstream nodes.

        If a current digest is available, stores it in the session_context
        so downstream nodes (TaskCreateNode, etc.) receive it as context.
        The original query is preserved within DigestedInformation.original_query.
        """
        if self.session is not None and self._current_digest is not None:
            from tinycua.models.session_context_entry import SessionContextEntry

            if any(
                entry.content is self._current_digest
                for entry in self.session.session_context
                if entry.segment == "output"
            ):
                return

            self.session.session_context.append(
                SessionContextEntry(
                    content=self._current_digest,
                    segment="output",
                    source_node_id=self.node_id,
                    source_session_id=self.session.session_id,
                )
            )

    def on_complete(
        self, queue: NodeQueue, response: LLMResult | DecisionResult
    ) -> None:
        """Post-completion hook for queue mutations.

        Retrieves DigestedInformation from session_context and stores it
        in _current_digest so propagate() can forward it to downstream
        nodes (TaskCreateNode, etc.).

        Args:
            queue: The node queue that can be mutated.
            response: The final LLM response (DecisionResult).
        """
        digest = self._current_digest or self._get_digested_input()
        if digest is not None:
            self._current_digest = digest

        route_label = (
            response.route_label if isinstance(response, DecisionResult) else ""
        )
        if route_label == "task_creation":
            spawned = [
                TinyCUATaskCreateNode(
                    node_id="task_create",
                    config=create_node_config("task_create", self.config),
                ),
                TinyCUATaskAnalyzerNode(
                    node_id="task_analyzer",
                    config=create_node_config(
                        "task_analyzer",
                        self.config,
                        mode="initial_analysis",
                    ),
                ),
                TinyCUAAnalysisEffortNode(
                    node_id="analysis_effort",
                    config=create_node_config("analysis_effort", self.config),
                ),
                TinyCUATaskExecutorNode(
                    node_id="task_executor",
                    config=create_node_config("task_executor", self.config),
                ),
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer", self.config),
                ),
            ]
            queue.spawn_after_current(
                spawned
            )
            if digest is not None:
                queue.set_input(
                    spawned[0],
                    NodeHandoff(
                        source_node=self.node_id,
                        target_node=spawned[0].node_id,
                        instruction="Use the digested request to create the roadmap.",
                        payload={"digested_information": digest},
                    ),
                )
        elif route_label in {"task_recreation", "task_reanalysis"}:
            queue.spawn_after_current(
                [
                    TinyCUATaskAnalyzerNode(
                        node_id="task_analyzer",
                        config=create_node_config(
                            "task_analyzer",
                            self.config,
                            mode=route_label,
                        ),
                    ),
                    TinyCUAAnalysisEffortNode(
                        node_id="analysis_effort",
                        config=create_node_config("analysis_effort", self.config),
                    ),
                    TinyCUATaskExecutorNode(
                        node_id="task_executor",
                        config=create_node_config("task_executor", self.config),
                    ),
                    TinyCUAResultReviewerNode(
                        node_id="result_reviewer",
                        config=create_node_config("result_reviewer", self.config),
                    ),
                ]
            )
        elif route_label == "proceed_execution":
            queue.spawn_after_current(
                [
                    TinyCUATaskExecutorNode(
                        node_id="task_executor",
                        config=create_node_config("task_executor", self.config),
                    ),
                    TinyCUAResultReviewerNode(
                        node_id="result_reviewer",
                        config=create_node_config("result_reviewer", self.config),
                    ),
                ]
            )

        super().on_complete(queue, response)
