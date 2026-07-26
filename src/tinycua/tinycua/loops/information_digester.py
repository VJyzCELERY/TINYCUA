"""InformationDigesterNode for structured context digestion."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from tinycua.loops.context_rendering import clean_context_enhanced_query
from tinycua.loops._input_messages import extract_user_query
from tinycua.loops.node import ProcessNode
from tinycua.models.digested_information import DigestedInformation

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)

_DIGESTER_INSTRUCTION = (
    "You are the InformationDigester. Your role is strictly exploration "
    "and understanding — you do NOT solve, write, code, or execute the "
    "user's request. Your job is to understand what the user is asking for "
    "and gather comprehensive relevant context that will help downstream "
    "task planning. You are the first layer of information gathering: "
    "downstream nodes (TaskAnalyzer, TaskExecutor) rely on your findings "
    "as the context that grounds their work, so be thorough. Gather context in "
    "this priority order: 1. Explicitly referenced workspace files — inspect "
    "them with file tools. 2. Existing session context — use "
    "enhanced_context_retrieval. 3. External research — use web_search only "
    "when material facts remain uncertain. Honor the requested timeframe and "
    "prefer authoritative sources appropriate to the claim. Stop once planning "
    "has enough reliable context; leave execution downstream. After gathering "
    "context, call digest_information with a concise summary of what you "
    "found: context_summary, key_points, constraints, advisory notes, and "
    "known gaps. The runtime preserves the original query separately. Your "
    "structured context travels with the mission so every downstream node "
    "sees it. Do NOT write code, produce solutions, or "
    "attempt the task itself."
)
_DIGESTER_CONTINUATION = (
    "Understand the request above. Explore for relevant context using the "
    "priority order: (1) explicitly referenced workspace files via file tools, "
    "(2) existing session context via enhanced_context_retrieval, (3) external "
    "research via web_search if "
    "material facts remain uncertain. Honor the requested timeframe and stop "
    "when planning has enough reliable context. Then call digest_information "
    "with a structured summary of your findings. The runtime preserves the "
    "original query. Do NOT attempt to solve, write, or execute the request — your "
    "output is context for downstream planning, not a solution."
)


class TinyCUAInformationDigesterNode(ProcessNode):
    """ProcessNode that gathers and digests context for downstream nodes.

    Spawned by QueryAnalyst before routing to WorkerNode, or by
    ResponseNode via suspend_current_and_prepend.

    Key behaviors:
    - Creates a fresh scoped child session
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
        """Parse the successful digest commit into DigestedInformation."""
        original_query = self._extract_original_query(input_data)
        self._current_digest = self._digest_from_tool_result(response, original_query)
        if self._current_digest is None:
            msg = "Digester completed without a successful digest_information result."
            raise RuntimeError(msg)
        self.propagate()
        return self._current_digest

    @staticmethod
    def _digest_from_tool_result(
        response: LLMResult,
        original_query: str,
    ) -> DigestedInformation | None:
        """Return the latest successful structured digest tool result."""
        for item in reversed(response.metadata.get("tool_results", [])):
            if not isinstance(item, dict) or item.get("name") != "digest_information":
                continue
            output = item.get("output")
            if not isinstance(output, dict) or output.get("success") is not True:
                continue
            return DigestedInformation(
                context_summary=str(output.get("context_summary", "")),
                original_query=original_query,
                key_points=list(output.get("key_points", [])),
                advisory_instructions=list(output.get("advisory_instructions", [])),
                constraints=list(output.get("constraints", [])),
                known_gaps=list(output.get("known_gaps", [])),
            )
        return None

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

    def propagate(self) -> None:
        """Propagate DigestedInformation to session_context.

        Stores the current digest in the node's session_context
        for consumption by downstream nodes.
        """
        if self.session is not None and self._current_digest is not None:
            from tinycua.models.session_context_entry import append_output_entry

            append_output_entry(
                self.session,
                self._current_digest,
                self.node_id,
                idempotent_by_identity=True,
            )

    def _extract_original_query(self, input_data: NodeInputLike | None) -> str:
        """Extract original user query from input data.

        Args:
            input_data: The node input.

        Returns:
            The original user query string, or empty string if not found.
        """
        query = extract_user_query(input_data, prefer_metadata_original=True)
        if query or self.session is None:
            return query
        return extract_user_query(
            self.session.input_context,
            prefer_metadata_original=True,
        )
