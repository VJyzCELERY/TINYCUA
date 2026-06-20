"""InformationDigesterNode for structured context digestion."""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING

from tinycua.loops.context_rendering import clean_context_enhanced_query
from tinycua.loops.node import ProcessNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.node_input import NodeInput, convert_node_input_to_messages
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)

_DIGESTER_INSTRUCTION = (
    "You are the InformationDigester. Your role is strictly exploration "
    "and understanding — you do NOT solve, write, code, or execute the "
    "user's request. Your job is to understand what the user is asking for "
    "and gather relevant context that will help downstream task planning. "
    "Gather context in this priority order: 1. Existing session context — "
    "use enhanced_context_retrieval to inspect prior conversation history "
    "and any context from upstream nodes. 2. External research — use "
    "web_search for current information when the request involves topics "
    "that benefit from up-to-date knowledge (frameworks, APIs, current "
    "model landscape, etc.). Always prefer the latest information. Use the "
    "current date (shown in the context) as the time frame unless the "
    "request explicitly asks about a historical period. When researching, "
    "seek current/recent sources over older ones. After gathering context, "
    "call digest_information with a concise summary of what you found: key "
    "points, constraints, advisory notes, and known gaps. Do NOT write "
    "code, produce solutions, or attempt the task itself."
)

_DIGESTER_CONTINUATION = (
    "Understand the request above. Explore for relevant context using the "
    "priority order: (1) existing session context via "
    "enhanced_context_retrieval, (2) external research via web_search if "
    "the topic benefits from current information. Then call "
    "digest_information with your findings. Do NOT attempt to solve, write, "
    "or execute the request — your output is context for downstream "
    "planning, not a solution."
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
            continuation=_DIGESTER_CONTINUATION,
            is_terminal=is_terminal,
        )
        self._current_digest: DigestedInformation | None = None

    def __call__(self, input_data: NodeInputLike) -> LLMResult:
        """Execute the digester: call LLM and parse response into DigestedInformation.

        Invokes the parent ProcessNode.__call__ to perform the LLM call,
        then parses the response text into a DigestedInformation object.
        Falls back to DigestedInformation.fallback() on parse failure.

        Args:
            input_data: The node input.

        Returns:
            The LLM response.
        """
        original_query = self._extract_original_query(input_data)
        response = super().__call__(input_data)
        self._current_digest = self._parse_digest_response(
            response.content,
            original_query,
        )
        return response

    def parse_loop_result(
        self,
        response: LLMResult,
        input_data: NodeInputLike | None,
    ) -> DigestedInformation:
        """Parse loop-owned LLM output into DigestedInformation."""
        original_query = self._extract_original_query(input_data or "")
        self._current_digest = self._parse_digest_response(
            response.content,
            original_query,
        )
        self.propagate()
        return self._current_digest

    def _parse_digest_response(
        self,
        content: str,
        original_query: str,
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
        cleaned_query = clean_context_enhanced_query(content)
        if not original_query and cleaned_query:
            original_query = cleaned_query

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
                "Digester LLM response not JSON, using raw text as context_summary",
            )
            context_summary = cleaned_query if cleaned_query else content
            return DigestedInformation(
                context_summary=context_summary,
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
        self.session.parent_id = root_or_parent_session.session_id
        self.session.session_config = root_or_parent_session.session_config
        self.session.input_context = list(root_or_parent_session.input_context)
        self.session.task = root_or_parent_session.task
        self.session.task_store = root_or_parent_session.task_store
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

    def _extract_original_query(self, input_data: NodeInputLike) -> str:
        """Extract original user query from input data.

        Args:
            input_data: The node input.

        Returns:
            The original user query string, or empty string if not found.
        """
        if isinstance(input_data, NodeInput):
            original_query = input_data.metadata.get("original_query")
            if isinstance(original_query, str) and original_query.strip():
                return original_query.strip()
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
