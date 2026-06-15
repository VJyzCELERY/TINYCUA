"""ResponseNode — terminal ProcessNode that captures the final response content."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinycua.loops.node import ProcessNode

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.models.node_input import NodeInputLike
    from tinycua.config.types import LLMResult


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

        super().__init__(
            node_id=node_id,
            config=config or create_node_config("response"),
            instruction=(
                "Generate the final user-facing response. Use the available "
                "conversation and node outputs as context, and always return "
                "a concise non-empty answer."
            ),
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
