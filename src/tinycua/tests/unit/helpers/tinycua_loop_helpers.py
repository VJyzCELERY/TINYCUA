"""Shared test helpers for TinyCUALoop tests.

Provides lightweight StubNode and StubResponseNode classes for unit and
integration tests without requiring the full ProcessNode machinery.
"""

from __future__ import annotations

from tinycua.config.node_config import NodeConfigBase
from tinycua.loops.node import Node


class StubNode(Node):
    """Lightweight test node that captures processed content.

    Used by unit and integration tests to verify queue execution,
    message building, and session recording without requiring a
    real LLM client or the full ProcessNode lifecycle.

    Attributes:
        node_id: Unique identifier for this node.
        config: Node configuration with default policies.
        is_terminal: Whether this node is terminal (always False).
        processed_content: Content captured during execution.
    """

    def __init__(
        self,
        content: str = "stub output",
        node_id: str = "stub",
    ) -> None:
        """Initialize StubNode.

        Args:
            content: Content to associate with this node.
            node_id: Unique identifier for this node.
        """
        super().__init__(
            node_id=node_id,
            config=NodeConfigBase(),
            instruction=f"Stub instruction: {content}",
        )
        self.processed_content = content

    def __call__(self, input: object) -> str:  # noqa: ARG002
        """Execute the stub node.

        Args:
            input: Ignored input data.

        Returns:
            The stub content string.
        """
        return self.processed_content


class StubResponseNode(Node):
    """Terminal test node that captures the final response content.

    Used as a terminal node in queue bootstrap tests to verify
    that the loop stops at terminal nodes and captures their output.

    Attributes:
        node_id: Unique identifier for this node.
        config: Node configuration with default policies.
        is_terminal: Whether this node is terminal (always True).
        captured_content: Content captured during execution.
    """

    def __init__(
        self,
        content: str = "final response",
        node_id: str = "response",
    ) -> None:
        """Initialize StubResponseNode.

        Args:
            content: Content to associate with this terminal node.
            node_id: Unique identifier for this node.
        """
        super().__init__(
            node_id=node_id,
            config=NodeConfigBase(),
            instruction=f"Response instruction: {content}",
            is_terminal=True,
        )
        self.captured_content = content

    def __call__(self, input: object) -> str:  # noqa: ARG002
        """Execute the response node.

        Args:
            input: Ignored input data.

        Returns:
            The captured content string.
        """
        self.captured_content = input if isinstance(input, str) else str(input)
        return self.captured_content
