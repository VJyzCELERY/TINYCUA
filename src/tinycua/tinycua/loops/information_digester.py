"""InformationDigesterNode for structured context digestion."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from tinycua.loops.node import ProcessNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.models.node_input import NodeInputLike

_DIGESTER_INSTRUCTION = (
    "You are an information digester. Your task is to analyze the "
    "conversation context and produce a structured summary. "
    "Extract key points, advisory instructions, constraints, and "
    "known gaps from the available context."
)


class TinyCUAInformationDigesterNode(ProcessNode):
    """ProcessNode that gathers and digests context for downstream nodes.

    Spawned by QueryAnalyst before routing to WorkerNode, or by
    ResponseNode via suspend_current_and_prepend.

    Key behaviors:
    - Creates fresh node session (does not inherit parent)
    - Receives selected QueryAnalyst session context via NodeInput
    - Produces DigestedInformation output
    - Propagates to parent (WorkerNode) session_context via
      selected-output propagation rule
    - Falls back to DigestedInformation.fallback(original_query)
      when no useful context found
    """

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _DIGESTER_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize InformationDigesterNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration.
            instruction: Instruction string for this node type.
            is_terminal: Whether this node is terminal.
        """
        super().__init__(
            node_id=node_id,
            config=config,
            instruction=instruction,
            is_terminal=is_terminal,
        )
        self._current_digest: DigestedInformation | None = None

    def ensure_session(self, root_or_parent_session: Session) -> Session:
        """Create a fresh node session (does not inherit parent).

        Overrides the base class to always create a fresh session,
        ensuring the digester does not inherit QueryAnalyst's session.

        Args:
            root_or_parent_session: The root session or parent session
                (used only for root context access).

        Returns:
            The newly created fresh session.
        """
        if self.session is not None:
            return self.session

        # Always create a fresh session — do NOT inherit parent
        self.session = Session()
        self.session.session_id = uuid.uuid4().hex
        self.session.parent_id = None
        return self.session

    def _produce_fallback(self, original_query: str) -> DigestedInformation:
        """Produce fallback DigestedInformation when no useful context.

        Args:
            original_query: The original user query to preserve.

        Returns:
            A fallback DigestedInformation instance.
        """
        return DigestedInformation.fallback(original_query)

    def propagate(self) -> None:
        """Propagate DigestedInformation to session_context.

        Stores the current digest in the node's session_context
        for consumption by downstream nodes.
        """
        if self.session is not None and self._current_digest is not None:
            self.session.session_context.append({
                "role": "assistant",
                "content": self._current_digest,
            })

    def _extract_original_query(self, input_data: NodeInputLike) -> str:
        """Extract original user query from input data.

        Args:
            input_data: The node input.

        Returns:
            The original user query string, or empty string if not found.
        """
        from tinycua.models.node_input import (
            NodeInput,
            convert_node_input_to_messages,
        )

        if isinstance(input_data, NodeInput) and input_data.messages:
            # Try to find the last user message
            for msg in reversed(input_data.messages):
                if msg.get("role") == "user":
                    return msg.get("content", "")
            # Fallback to first message content
            return input_data.messages[0].get("content", "")

        # For other input types, try to extract from messages
        try:
            messages = convert_node_input_to_messages(input_data)
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    return msg.get("content", "")
        except (ValueError, TypeError):
            pass

        return ""
