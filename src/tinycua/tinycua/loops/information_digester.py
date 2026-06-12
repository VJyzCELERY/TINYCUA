"""InformationDigesterNode for structured context digestion."""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

from tinycua.loops.node import ProcessNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)

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

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute the digester: call LLM and parse response into DigestedInformation.

        Invokes the parent ProcessNode.__call__ to perform the LLM call,
        then parses the response text into a DigestedInformation object.
        Falls back to DigestedInformation.fallback() on parse failure.

        Args:
            input: The node input.

        Returns:
            The LLM response.
        """
        original_query = self._extract_original_query(input)
        response = super().__call__(input)
        self._current_digest = self._parse_digest_response(
            response.content, original_query,
        )
        return response

    def _parse_digest_response(
        self, content: str, original_query: str,
    ) -> DigestedInformation:
        """Parse LLM response text into a DigestedInformation object.

        Attempts to parse as JSON first, then falls back to constructing
        a DigestedInformation with the raw content as context_summary.

        Args:
            content: The raw LLM response text.
            original_query: The original user query.

        Returns:
            A DigestedInformation instance.
        """
        if not content or not content.strip():
            return DigestedInformation.fallback(original_query)

        try:
            data = json.loads(content)
            return DigestedInformation(
                context_summary=data.get("context_summary", content),
                original_query=data.get("original_query", original_query),
                key_points=data.get("key_points", []),
                advisory_instructions=data.get("advisory_instructions", []),
                constraints=data.get("constraints", []),
                known_gaps=data.get("known_gaps", []),
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            logger.debug(
                "Digester LLM response not JSON, using raw text as context_summary"
            )
            return DigestedInformation(
                context_summary=content,
                original_query=original_query,
            )

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
