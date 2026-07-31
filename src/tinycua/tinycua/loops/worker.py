"""WorkerNode for task planning and execution orchestration."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from tinycua.config.types import LLMResult
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
from tinycua.models.node_input import NodeInput
from tinycua.loops.session_context_query import find_latest_entry
from tinycua.tools.routing import WorkerRouteSelectionTool

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.node import Node
    from tinycua.models.node_input import NodeInputLike
    from tinycua.models.session import Session

_WORKER_INSTRUCTION = (
    "You are a worker node responsible for task planning and execution "
    "orchestration. Analyze the request context and MUST call select_worker_route "
    "with exactly one route allowed by that tool's current schema. Do not "
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
        self._current_ceq: NodeInput | None = None
        # ponytail: cache the route-selection tool per label-set so identical
        # valid-route sets reuse the same tool object and keep the tools-prefix
        # byte-stable for prompt caching (FR-018).
        self._route_tool_cache: dict[tuple[str, ...], object] = {}

    def state_valid_route_labels(self) -> list[str]:
        """Return only worker routes that are valid for current task state."""
        if not self._has_root_task:
            return ["task_creation"]
        if self.session is not None and self.session.task_store.all_done():
            return ["task_recreation", "passthrough"]
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

    def should_run_deterministically(self) -> bool:
        """Return whether task state leaves Worker exactly one valid route."""
        return len(self.state_valid_route_labels()) == 1

    def run_deterministic(self, queue: NodeQueue) -> LLMResult:
        """Commit the sole state-valid route without asking the model again."""
        route = self.state_valid_route_labels()[0]
        result = LLMResult(
            tool_calls=[
                {
                    "id": f"deterministic_{self.node_id}_route",
                    "type": "function",
                    "function": {
                        "name": "select_worker_route",
                        "arguments": f'{{"route":"{route}"}}',
                    },
                }
            ]
        )
        self.on_complete(
            queue,
            DecisionResult(
                route_label=route,
                analysis_response=result,
                classification_response=result,
            ),
        )
        return result

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
        elif (
            isinstance(input, NodeInput)
            and input.input_type == "context_enhanced_query"
        ):
            self._current_ceq = input
        return super().build_messages(session, input, resolved_tools)

    def _digest_enabled(self) -> bool:
        """Return whether this Worker should consume a fresh digest."""
        return bool(
            getattr(self.config.metadata.get("session_config"), "digest_enabled", True)
        )

    def _review_enabled(self) -> bool:
        """Return whether this Worker should schedule a ResultReviewer."""
        return bool(
            getattr(self.config.metadata.get("session_config"), "review_enabled", True)
        )

    def _set_downstream_input(
        self,
        queue: NodeQueue,
        node: Node,
        digest: DigestedInformation | None,
        instruction: str,
    ) -> None:
        """Pass a fresh digest or direct CEQ to the immediate downstream node."""
        node_id = node.node_id
        if digest is not None:
            queue.set_input(
                node,
                NodeHandoff(
                    source_node=self.node_id,
                    target_node=node_id,
                    instruction=instruction,
                    payload={"digested_information": digest},
                ),
            )
        elif self._current_ceq is not None:
            queue.set_input(
                node,
                replace(self._current_ceq, target_node=node_id),
            )

    def _get_digested_input(self) -> DigestedInformation | None:
        """Retrieve DigestedInformation from session_context.

        Scans session_context for the most recent DigestedInformation
        entry. Returns None if not found (fallback to raw user_query).

        Returns:
            The most recent DigestedInformation, or None if not found.
        """
        if self.session is None:
            return None
        return find_latest_entry(self.session, DigestedInformation)

    def propagate(self) -> None:
        """Forward DigestedInformation to downstream nodes.

        If a current digest is available, stores it in the session_context
        so downstream nodes (TaskCreateNode, etc.) receive it as context.
        The original query is preserved within DigestedInformation.original_query.
        """
        if self.session is not None and self._current_digest is not None:
            from tinycua.models.session_context_entry import append_output_entry

            append_output_entry(
                self.session,
                self._current_digest,
                self.node_id,
                idempotent_by_identity=True,
            )

    @staticmethod
    def _digest_overlay(digest: DigestedInformation) -> dict[str, object]:
        """Return the one current-turn context overlay derived from a fresh digest."""
        return {
            "original_query": digest.original_query,
            "context_summary": digest.context_summary,
            "key_points": list(digest.key_points),
            "advisory_instructions": list(digest.advisory_instructions),
            "constraints": list(digest.constraints),
            "known_gaps": list(digest.known_gaps),
        }

    def _replace_context_overlay(self, digest: DigestedInformation | None) -> None:
        """Replace the mutable root's latest context overlay, never append one."""
        if (
            digest is None
            or self.session is None
            or self.session.task_store.root_task_id is None
        ):
            return
        root_id = self.session.task_store.root_task_id
        self.session.task_store.update_task(
            root_id,
            metadata={"current_context_overlay": self._digest_overlay(digest)},
        )

    def _archive_and_reset_task_tree(self) -> None:
        """Preserve the old tree as retrieval context before starting a new root."""
        if self.session is None or self.session.task_store.root_task_id is None:
            return
        from tinycua.models.session_context_entry import append_output_entry

        append_output_entry(
            self.session,
            {
                "archive_type": "task_tree",
                "reason": "task_recreation",
                "task_tree": self.session.task_store.snapshot(),
            },
            self.node_id,
        )
        self.session.task_store.reset()
        self.session.task = None

    def _spawn_task_creation(
        self,
        queue: NodeQueue,
        digest: DigestedInformation | None,
    ) -> None:
        """Schedule fresh root creation and hand the full digest to TaskCreate."""
        spawned = [
            TinyCUATaskCreateNode(
                node_id="task_create",
                config=create_node_config("task_create", self.config),
            ),
            TinyCUATaskAnalyzerNode(
                node_id="task_analyzer",
                config=create_node_config(
                    "task_analyzer", self.config, mode="initial_analysis"
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
        ]
        if self._review_enabled():
            spawned.append(
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer", self.config),
                )
            )
        queue.spawn_after_current(spawned)
        self._set_downstream_input(
            queue, spawned[0], digest, "Use the digested request to create the roadmap."
        )

    def _spawn_reanalysis(
        self,
        queue: NodeQueue,
        route_label: str,
        digest: DigestedInformation | None,
    ) -> None:
        """Schedule Analyzer work and hand it the current full digest."""
        analyzer = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer", self.config, mode=route_label),
        )
        queue.spawn_after_current(
            [
                analyzer,
                TinyCUAAnalysisEffortNode(
                    node_id="analysis_effort",
                    config=create_node_config("analysis_effort", self.config),
                ),
                TinyCUATaskExecutorNode(
                    node_id="task_executor",
                    config=create_node_config("task_executor", self.config),
                ),
            ]
        )
        if self._review_enabled():
            queue.items.insert(
                queue.items.index(analyzer) + 3,
                TinyCUAResultReviewerNode(
                    node_id="result_reviewer",
                    config=create_node_config("result_reviewer", self.config),
                ),
            )
        self._set_downstream_input(
            queue,
            analyzer,
            digest,
            "Use the fresh digested context to revise the roadmap.",
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
        digest = (
            self._current_digest or self._get_digested_input()
            if self._digest_enabled()
            else None
        )
        if digest is not None:
            self._current_digest = digest

        route_label = (
            response.route_label if isinstance(response, DecisionResult) else ""
        )
        if route_label == "task_creation":
            self._spawn_task_creation(queue, digest)
        elif route_label == "task_recreation":
            self._archive_and_reset_task_tree()
            self._spawn_task_creation(queue, digest)
        elif route_label == "task_reanalysis":
            self._replace_context_overlay(digest)
            self._spawn_reanalysis(queue, route_label, digest)
        elif route_label == "proceed_execution":
            self._replace_context_overlay(digest)
            executor = TinyCUATaskExecutorNode(
                node_id="task_executor",
                config=create_node_config("task_executor", self.config),
            )
            spawned = [executor]
            if self._review_enabled():
                spawned.append(
                    TinyCUAResultReviewerNode(
                        node_id="result_reviewer",
                        config=create_node_config("result_reviewer", self.config),
                    )
                )
            queue.spawn_after_current(spawned)
            self._set_downstream_input(
                queue, executor, digest, "Use the fresh digested context to execute."
            )

        super().on_complete(queue, response)
