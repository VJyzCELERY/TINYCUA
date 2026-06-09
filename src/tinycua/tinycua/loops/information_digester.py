"""TinyCUAInformationDigesterNode — ProcessNode for context gathering and digestion.

Implements a concrete ProcessNode that gathers and digests context for
downstream nodes (primarily ResponseNode) when direct accumulated context
or tool access is insufficient.

Spec ref: src/tinycua/specs/2.5-information-digester-node/
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from tinycua.config.types import LLMResult
from tinycua.loops.node import ProcessNode
from tinycua.models.digested_information import DigestedInformation

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)

# Fallback continuation template — preserves user query for downstream.
_FALLBACK_TEMPLATE = (
    "The user asked {user_query!r}. No useful extra information was found. "
    "Downstream should proceed with the user request and plan carefully "
    "before action."
)

# Instruction constant for the digester node.
_DIGESTER_INSTRUCTION = (
    "You are an information digester. Your role is to gather and summarize "
    "relevant context for downstream processing. You have access to two tools: "
    "enhanced_context_retrieval for lazy scoped context access, and "
    "digest_information for producing structured digested output. "
    "Do NOT execute tasks or synthesize final responses."
)


def llm_call(messages: list[dict[str, str]], *, llm_client: Any = None) -> LLMResult:
    """Invoke the LLM client with the given messages.

    This is a thin wrapper that centralizes the LLM call for the
    information digester module, enabling easy mocking in tests.

    Args:
        messages: The message list for the LLM call.
        llm_client: The LLM client callable. If None, returns a default response.

    Returns:
        The LLM response wrapped in LLMResult.
    """
    if llm_client is None:
        return LLMResult(
            content="No LLM client configured.",
            role="assistant",
        )

    raw_response = llm_client(messages)

    if isinstance(raw_response, dict):
        return LLMResult(
            content=raw_response.get("content", ""),
            role=raw_response.get("role", "assistant"),
            tool_calls=raw_response.get("tool_calls", []),
            metadata=raw_response.get("metadata", {}),
        )
    return raw_response  # type: ignore[return-value]


class EnhancedContextRetrieval:
    """Lazily scoped context retrieval with ReAct-style search.

    Manages a scoped context cache file and runs a limited ReAct-style
    search over that cache using grep/search and paginated read tools.

    This is a placeholder implementation. Full implementation is deferred
    to Milestone 4.2.

    Attributes:
        cache_path: Path to the scoped context cache file.
    """

    def __init__(
        self,
        session_context: list[dict],
        *,
        max_sources: int | None = None,
    ) -> None:
        """Initialize retrieval with selected context messages.

        Args:
            session_context: The selected context messages to cache and search.
            max_sources: Maximum number of context sources to process.
        """
        self._session_context = session_context
        self._max_sources = max_sources
        self.cache_path: str | None = None

    def create_cache(self) -> str:
        """Lazily create the scoped context cache file.

        Returns:
            Path to the created cache file.
        """
        import tempfile

        if self.cache_path is None:
            # TODO(M4.2): replace with mkstemp() or NamedTemporaryFile
            self.cache_path = tempfile.mktemp(suffix=".cache")
        return self.cache_path

    def search(self, query: str) -> list[dict]:
        """Search the scoped cache using ReAct-style exploration.

        Args:
            query: Search query to find relevant context.

        Returns:
            Additional context messages found through retrieval, or empty list.
        """
        # Placeholder: returns empty when invoked.
        return []


class TinyCUAInformationDigesterNode(ProcessNode):
    """ProcessNode that gathers and digests context for downstream nodes.

    Creates a fresh session, receives selected input from parent, optionally
    uses enhanced_context_retrieval for lazy context access, produces
    DigestedInformation via digest_information, and propagates digest to
    parent via selected-output propagation.

    Attributes:
        node_id: Always "information_digester" by default.
        parent: Suspended parent node (typically ResponseNode).
    """

    def __init__(
        self,
        node_id: str = "information_digester",
        config: NodeConfigBase | None = None,
        parent: ProcessNode | None = None,
    ) -> None:
        """Initialize InformationDigesterNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses TinyCUAInformationDigesterNodeConfig
                defaults if None.
            parent: Suspended parent node for session adoption and propagation
                targeting.
        """
        from tinycua.config.node_config import (
            NodeToolPolicy,
            TinyCUAInformationDigesterNodeConfig,
        )

        if config is None:
            config = TinyCUAInformationDigesterNodeConfig()
        elif not isinstance(config, TinyCUAInformationDigesterNodeConfig):
            # Wrap plain NodeConfigBase with digester-specific defaults.
            digester_config = TinyCUAInformationDigesterNodeConfig()
            digester_config.custom_instruction_append = config.custom_instruction_append
            digester_config.custom_continuation_append = config.custom_continuation_append
            digester_config.custom_retry_append = config.custom_retry_append
            digester_config.propagation = config.propagation
            digester_config.tool_policy = config.tool_policy
            digester_config.stream_policy = config.stream_policy
            digester_config.retry_policy = config.retry_policy
            digester_config.message_policy = config.message_policy
            digester_config.metadata = config.metadata
            digester_config.llm_client = config.llm_client
            config = digester_config

        # FR-013: Restrict tool scope to digest-specific tools only.
        config.tool_policy = NodeToolPolicy(
            node_tools=[],
            include_agent_tools="none",
        )

        super().__init__(
            node_id=node_id,
            config=config,
            instruction=_DIGESTER_INSTRUCTION,
            is_terminal=False,
        )
        self._parent = parent
        self.parent = parent  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute the context gathering and digestion.

        Lifecycle:
        1. Ensure fresh session (not inherited from parent).
        2. Convert NodeInput to messages for LLM context.
        3. Optionally invoke enhanced_context_retrieval for lazy context.
        4. Invoke digest_information to produce structured DigestedInformation.
        5. Return digest as LLMResult for propagation.

        Args:
            input: NodeInput with selected parent session_context messages
                and optional digest request payload.

        Returns:
            LLMResult containing digested information or fallback continuation.
        """
        from tinycua.models.session import Session

        # FR-002, FR-003: Create a fresh session — do NOT inherit from parent.
        if self.session is None:
            self.session = Session()

        # FR-004: Convert input messages for context.
        from tinycua.models.node_input import convert_node_input_to_messages

        messages = convert_node_input_to_messages(input, source="internal")

        # Extract user query from messages for fallback preservation.
        user_query = self._extract_user_query(messages)

        # FR-006: Optionally invoke enhanced context retrieval.
        additional_context: list[dict] = []
        if self._should_use_enhanced_retrieval():
            additional_context = self._invoke_enhanced_retrieval(messages)

        # Build full context: original messages + retrieved context.
        full_context = list(messages) + additional_context

        # FR-009, FR-010, FR-014: Produce structured digest from gathered context
        # with retry per NodeRetryPolicy before fallback.
        retry_policy = self.config.retry_policy
        max_attempts = max(retry_policy.max_attempts, 1)

        result = None
        for attempt in range(1, max_attempts + 1):
            result = self._produce_digest(full_context)
            if result.content and result.content.strip():
                break
            if attempt < max_attempts:
                logger.info(
                    "node=%s digest empty, retrying (attempt %d/%d)",
                    self.node_id,
                    attempt,
                    max_attempts,
                )
            else:
                # FR-011, FR-013: If digest is empty/missing, produce fallback.
                result = self._produce_fallback(user_query)

        # FR-012: Record only own output (not copied input).
        assert result is not None
        self.record_output(result)
        return result

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:  # type: ignore[override]
        """Post-completion hook for queue mutations.

        Propagates digest output to the suspended parent node's session
        via selected-output propagation rule, then advances the queue
        so the parent resumes.

        Args:
            queue: The node queue (current node is InformationDigesterNode).
            response: The digest output or fallback continuation.
        """
        # FR-005, FR-012: Propagate digest to parent via selected-output rule.
        if self._parent is not None and hasattr(self._parent, "session"):
            parent_session = self._parent.session
            if parent_session is not None:
                parent_session.session_context.append(
                    {
                        "role": response.role,
                        "content": response.content,
                    }
                )
                logger.info(
                    "node=%s propagated digest to parent session=%s",
                    self.node_id,
                    parent_session.session_id,
                )

        # Advance queue so parent resumes as current node.
        queue.advance()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _should_use_enhanced_retrieval(self) -> bool:
        """Check if enhanced_context_retrieval should be invoked.

        FR-006: Returns True if retrieval_enabled is True and context
        is insufficient.

        Returns:
            True if retrieval should be used, False otherwise.
        """
        from tinycua.config.node_config import TinyCUAInformationDigesterNodeConfig

        if isinstance(self.config, TinyCUAInformationDigesterNodeConfig):
            return self.config.retrieval_enabled
        return False

    def _invoke_enhanced_retrieval(self, messages: list[dict]) -> list[dict]:
        """Invoke EnhancedContextRetrieval for lazy scoped context access.

        FR-007, FR-008: Creates a scoped cache and runs ReAct-style
        search over that cache. Search/read operations are limited
        to the cache boundaries.

        Args:
            messages: The selected input messages to search within.

        Returns:
            Additional context messages from the cache, or empty list.
        """
        from tinycua.config.node_config import TinyCUAInformationDigesterNodeConfig

        max_sources = None
        if isinstance(self.config, TinyCUAInformationDigesterNodeConfig):
            max_sources = self.config.max_digest_sources

        try:
            retrieval = EnhancedContextRetrieval(
                session_context=messages,
                max_sources=max_sources,
            )
            retrieval.create_cache()
            return retrieval.search("relevant context")
        except Exception:
            # SC-016: Log error and proceed with available context.
            # TODO(M4.2): Narrow to expected exception types when
            # EnhancedContextRetrieval is fully implemented.
            logger.warning(
                "node=%s enhanced_retrieval failed, proceeding with available context",
                self.node_id,
            )
            return []

    def _produce_digest(self, context: list[dict]) -> LLMResult:
        """Produce structured DigestedInformation from gathered context.

        FR-009, FR-010: Calls digest_information tool to produce
        structured output with context_summary, key_points,
        advisory_instructions, constraints, and known_gaps.

        Args:
            context: The gathered context messages.

        Returns:
            LLMResult containing digested information with parsed
            DigestedInformation in metadata.
        """
        # Build a summary prompt for the LLM.
        context_text = "\n".join(
            f"[{m.get('role', 'unknown')}] {m.get('content', '')}"
            for m in context
            if m.get("content")
        )

        digest_prompt = [
            {
                "role": "user",
                "content": (
                    "Produce a structured digest of the following context. "
                    "Include: context_summary, key_points, advisory_instructions, "
                    "constraints, and known_gaps.\n\n"
                    f"Context:\n{context_text}"
                ),
            }
        ]

        llm_result = llm_call(digest_prompt, llm_client=self.config.llm_client)
        # Parse LLM response into DigestedInformation and attach as metadata.
        digested = self._parse_digest_response(llm_result)
        llm_result.metadata["digested_information"] = json.dumps(
            {
                "context_summary": digested.context_summary,
                "key_points": digested.key_points,
                "advisory_instructions": digested.advisory_instructions,
                "constraints": digested.constraints,
                "known_gaps": digested.known_gaps,
            }
        )
        return llm_result

    def _parse_digest_response(self, llm_result: LLMResult) -> DigestedInformation:
        """Parse LLM response into structured DigestedInformation.

        Attempts to parse the LLM content as JSON containing the five required
        fields. Falls back to using the raw content as context_summary if parsing
        fails.

        Args:
            llm_result: The LLM response containing digest content.

        Returns:
            DigestedInformation with parsed fields.
        """
        try:
            data = json.loads(llm_result.content)
            return DigestedInformation(
                context_summary=data.get("context_summary", ""),
                key_points=data.get("key_points", []),
                advisory_instructions=data.get("advisory_instructions", []),
                constraints=data.get("constraints", []),
                known_gaps=data.get("known_gaps", []),
            )
        except (json.JSONDecodeError, TypeError, AttributeError):
            logger.warning(
                "node=%s failed to parse digest response as JSON, using raw content",
                self.node_id,
            )
            return DigestedInformation(context_summary=llm_result.content)

    def _produce_fallback(self, user_query: str) -> LLMResult:
        """Produce the no-useful-context fallback continuation.

        FR-011, FR-013: Preserves user query and signals downstream
        to proceed with the user request.

        Args:
            user_query: The original user query from the input.

        Returns:
            LLMResult with fallback continuation message.
        """
        fallback_text = _FALLBACK_TEMPLATE.format(user_query=user_query)
        return LLMResult(content=fallback_text, role="assistant")

    def _extract_user_query(self, messages: list[dict]) -> str:
        """Extract the most recent user query from messages.

        Scans messages in reverse order to find the last user-role
        message content. Falls back to an empty string if none found.

        Args:
            messages: The input message list.

        Returns:
            The user query text, or empty string.
        """
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""
