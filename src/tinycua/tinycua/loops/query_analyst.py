"""QueryAnalystNode for classifying and routing user input."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from tinycua.config.node_config import create_node_config
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops._input_messages import extract_user_query
from tinycua.loops.node import DecisionNode, DecisionResult
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.node_input import NodeInput

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult, ValidationResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)

_QUERY_ANALYST_INSTRUCTION = (
    "You are a query analyst. You only classify and route; you do not answer "
    "the user, execute tasks, or mutate state. Your role is to classify user "
    "input and route it to the appropriate handler. "
    "Analyze the user's request and determine whether it requires "
    "task execution (worker), is uncertain, or should pass through directly. "
    "You MUST call select_query_route with exactly one route: worker, "
    "uncertain, or passthrough. Do not produce a text-only route answer; "
    "the route decision must be expressed by the function call. Choose worker for requests that ask you to "
    "plan, create, execute, decompose, inspect, or update tasks. Choose "
    "passthrough for simple conversational or factual responses. Choose "
    "uncertain only when the request cannot be classified safely. Do not answer "
    "the user directly from this node."
)

_QUERY_ANALYST_CONTINUATION = (
    "Based on the external user request above, classify the route by calling "
    "select_query_route. Do not answer the user from this node."
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
            continuation=_QUERY_ANALYST_CONTINUATION,
            classification_labels=classification_labels or self.ROUTE_LABELS,
            is_terminal=is_terminal,
        )
        self._queue: NodeQueue | None = None
        self._current_context_summary = ""

    def build_tool_system_prompt(self, resolved_tools: list[Any] | None = None) -> str:
        """Behavioral guidance keyed on present route tools (FR-005, FR-006)."""
        names = {getattr(tool, "name", "") for tool in (resolved_tools or [])}
        if not {"summarize_query_context", "select_query_route"}.issubset(names):
            return ""
        return (
            "Tool guidance: call summarize_query_context with a concise preliminary "
            "summary of the user's request in its session context, then call "
            "select_query_route with exactly one route."
        )

    def _route_worker(self, input_data: NodeInputLike = "") -> None:
        """Route to WorkerNode with information digestion.

        Always spawn InformationDigesterNode before WorkerNode so each user
        turn is consolidated with retrievable session context.

        Args:
            input_data: The original node input used to preserve the user query.
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

        # Create InformationDigesterNode
        digester = TinyCUAInformationDigesterNode(
            node_id="digester",
            config=create_node_config("information_digester", self.config),
        )

        queue.spawn_after_current([digester, worker_node])
        ceq = self._original_query_input(input_data, target_node="digester")
        if ceq is not None:
            queue.set_input(digester, ceq)

    def _original_query_input(
        self,
        input_data: NodeInputLike,
        *,
        target_node: str,
    ) -> NodeInputLike | None:
        """Return assistant-role CEQ input for the worker digester."""
        original_query = ""
        if self.session is not None and self.session.input_context:
            original_query = self._extract_user_query(list(self.session.input_context))
        if not original_query:
            original_query = self._extract_user_query(input_data)
        if original_query and self._current_context_summary:
            return NodeInput(
                input_type="context_enhanced_query",
                source_node=self.node_id,
                target_node=target_node,
                messages=[
                    {
                        "role": "assistant",
                        "content": (
                            f"Context:\n{self._current_context_summary}\n\n"
                            f"User Request:\n{original_query}"
                        ),
                    }
                ],
                metadata={
                    "original_query": original_query,
                    "context_summary": self._current_context_summary,
                },
            )
        return None

    @staticmethod
    def _context_summary_from(response: LLMResult) -> str:
        """Return the latest successful preliminary summary tool result."""
        for item in reversed(response.metadata.get("tool_results", [])):
            if (
                not isinstance(item, dict)
                or item.get("name") != "summarize_query_context"
            ):
                continue
            output = item.get("output")
            if isinstance(output, dict) and output.get("success") is True:
                return str(output.get("context_summary", "")).strip()
        return ""

    def parse_loop_result(
        self,
        response: LLMResult,
        input_data: NodeInputLike | None,  # noqa: ARG002 - lifecycle signature.
    ) -> str:
        """Capture the committed summary before route completion mutates the queue."""
        self._current_context_summary = self._context_summary_from(response)
        if not self._current_context_summary:
            msg = "QueryAnalyst completed without summarize_query_context."
            raise RuntimeError(msg)
        return self._current_context_summary

    def validate_output(self, response: LLMResult) -> ValidationResult:
        """Require a successful summary commit in addition to the route call."""
        validation = super().validate_output(response)
        if not self._context_summary_from(response):
            validation.is_valid = False
            validation.errors.append(
                "QueryAnalyst must successfully call summarize_query_context."
            )
        return validation

    def _set_response_handoff(self, queue: NodeQueue, route_label: str) -> None:
        """Forward direct-response context as assistant-role continuation."""
        if len(queue.items) < 2:
            return
        next_node = queue.items[1]
        ceq = self._original_query_input({}, target_node=next_node.node_id)
        if ceq is not None:
            ceq.input_type = f"{route_label}_response_context"
            ceq.metadata["route"] = route_label
            queue.set_input(next_node, ceq)

    def _extract_user_query(self, input_data: NodeInputLike) -> str:
        """Extract original user query from input data.

        Args:
            input_data: The node input.

        Returns:
            The last user message content, or first message if no user role,
            or empty string if no messages.
        """
        return extract_user_query(input_data)

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
            self._current_context_summary = (
                self._current_context_summary
                or self._context_summary_from(response.classification_response)
            )
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
            strategy = getattr(policy, "uncertain_strategy", "passthrough")
            if strategy == "route_worker":
                self._route_worker()
            elif strategy == "ask" and not getattr(policy, "hitl_enabled", False):
                logger.info(
                    "QueryAnalyst uncertain with HITL disabled — passthrough response"
                )
            elif strategy == "fail":
                raise RuntimeError("QueryAnalyst uncertain route failed by policy")
            else:
                self._set_response_handoff(queue, "uncertain")
                logger.info("QueryAnalyst routed to 'uncertain' — passthrough response")
        elif route_label == "passthrough":
            self._set_response_handoff(queue, "passthrough")
            logger.info("QueryAnalyst routed to 'passthrough' — no action taken")
        else:
            logger.warning("QueryAnalyst unknown route: %s", route_label)
        super().on_complete(queue, response)
