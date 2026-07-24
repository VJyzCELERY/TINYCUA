"""ResponseNode — terminal ProcessNode that captures the final response content."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua.loops.node import ProcessNode
from tinycua.models.node_input import NodeInput

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

_RESPONSE_CONTINUATION = (
    "The work is already done — the completed task evidence above shows what "
    "was accomplished. Summarize it as the final user-facing answer. Be "
    "concise, mention relevant artifacts or outputs and key findings. Do "
    "NOT redo the work (no web searches, no file writes, no new research). "
    "Do not emit JSON, tool-call protocol payloads, or internal routing "
    "details."
)

_FAILURE_RESPONSE_CONTINUATION = (
    "The task could not be completed because its replan budget was exhausted. "
    "Summarize the failure and its rationale honestly for the user. Do not "
    "claim the work was completed or redo the work."
)


class ResponseNode(ProcessNode):
    """Terminal node that captures the final response content.

    Used as the default terminal node for TinyCUALoop queue bootstrap.
    When the loop encounters a ResponseNode, it stops processing and
    returns the captured content.

    Attributes:
        node_id: Unique identifier for this node.
        config: Node configuration with default policies.
        is_terminal: Always True — marks this node as terminal.
        captured_content: Content captured from the LLM response.
    """

    def __init__(
        self,
        node_id: str = "response",
        config: NodeConfigBase | None = None,
    ) -> None:
        """Initialize ResponseNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default NodeConfigBase if None.
        """
        from tinycua.config.node_config import create_node_config

        node_config = config or create_node_config("response")
        continuation = (
            _FAILURE_RESPONSE_CONTINUATION
            if node_config.metadata.get("replan_budget_exhausted")
            else _RESPONSE_CONTINUATION
        )
        super().__init__(
            node_id=node_id,
            config=node_config,
            instruction=(
                "Generate the final user-facing response. Use the available "
                "conversation and node outputs as context, and always return "
                "a concise non-empty answer in natural language. Do not emit "
                "JSON or tool-call protocol payloads."
            ),
            continuation=continuation,
            is_terminal=True,
        )
        self.captured_content: str = ""

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute the response node.

        Delegates to ProcessNode.__call__() which handles the full
        lifecycle: build messages → validate → call LLM → retry →
        record → propagate → on_complete.

        Args:
            input: The node input.

        Returns:
            The LLM response with captured content.
        """
        result = super().__call__(input)
        self.captured_content = result.content
        return result

    def build_messages(
        self,
        session: Any,
        input: NodeInputLike,
        resolved_tools: list[Any] | None = None,
    ) -> list[dict[str, str]]:
        """Build clean final-response messages without internal handoff prose."""
        if isinstance(input, NodeInput) and input.metadata.get("original_query"):
            system = self.build_system_message(resolved_tools)
            messages = [system] if system.get("content") else []
            messages.append({"role": "user", "content": str(input.metadata["original_query"])})
            return messages
        return super().build_messages(session, input, resolved_tools)

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Optionally suspend for information digestion before final response."""
        del response
        if not self._should_request_digest():
            return

        from tinycua.config.node_config import create_node_config
        from tinycua.loops.information_digester import TinyCUAInformationDigesterNode

        digester = TinyCUAInformationDigesterNode(
            node_id="digester",
            config=create_node_config("digester"),
        )
        digester.parent = self
        self.config.metadata["digest_requested"] = True
        queue.suspend_current_and_prepend([digester])

    def _should_request_digest(self) -> bool:
        """Return whether response synthesis should first gather context."""
        if not self.config.metadata.get("require_digest"):
            return False
        if self.config.metadata.get("digest_requested"):
            return False
        if self.session is None:
            return True
        from tinycua.models.digested_information import DigestedInformation

        return not any(
            isinstance(entry.content, DigestedInformation)
            for entry in self.session.session_context
        )
