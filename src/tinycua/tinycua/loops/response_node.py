"""TinyCUAResponseNode — terminal ProcessNode with three-phase execution.

Replaces the previous minimal ResponseNode stub.  Provides context sufficiency
analysis, digester suspension, tool fallback, continuation routing, terminal
output normalisation, and retry compliance.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tinycua.config.types import LLMResult
from tinycua.loops.node import NodeExecutionError, ProcessNode

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.result_aggregation import AggregatedResult
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)

_DEFAULT_FALLBACK = "I encountered an error generating the final response."


@dataclass
class ResponseContext:
    """Aggregated context fed into TinyCUAResponseNode.

    Attributes:
        aggregated_result: Result from the ResultAggregationNode, or None
            if no aggregation has been performed.
        session_context: Propagated session context (list of message dicts).
        latest_output: The most recent node output, if any.
        continuation_payload: Any continuation data (e.g. MandatoryPassthrough
            payload).
    """

    aggregated_result: AggregatedResult | None
    session_context: list[dict[str, Any]]
    latest_output: str | None
    continuation_payload: Any  # MandatoryPassthrough | None


class TinyCUAResponseNode(ProcessNode):
    """Terminal ProcessNode that produces the final user-facing response.

    Three-phase execution:
    1. Build ``ResponseContext`` from available input & session data.
    2. Check context sufficiency.
       - Sufficient -> synthesise directly via LLM.
       - Insufficient + digester enabled -> set ``_needs_digestion`` flag;
         actual queue suspension happens in ``on_complete``.
       - Insufficient + no digester -> gather context via tools.
    3. Normalise terminal output to a string, record, and propagate.

    Attributes:
        node_id: ``"response"`` by default.
        config: Node configuration (default ``NodeConfigBase()``).
        is_terminal: Always ``True``.
        _continuation_payload: Stored MandatoryPassthrough for consolidated
            continuation.
        _needs_digestion: Set during ``__call__`` when context is insufficient
            and digester is enabled; checked in ``on_complete``.
        _digest_attempts: Counter to prevent infinite digest loops.
    """

    def __init__(
        self,
        node_id: str = "response",
        config: NodeConfigBase | None = None,
    ) -> None:
        """Initialise the response node.

        Args:
            node_id: Unique identifier (default ``"response"``).
            config: Node configuration.  Uses ``NodeConfigBase()`` if ``None``.
        """
        from tinycua.config.node_config import NodeConfigBase

        super().__init__(
            node_id=node_id,
            config=config or NodeConfigBase(),
            instruction=(
                "You are the final response node.  Synthesise the final "
                "user-facing answer from all available context."
            ),
            is_terminal=True,
        )
        self._continuation_payload: Any = None
        self._needs_digestion: bool = False
        self._digest_attempts: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __call__(self, input: NodeInputLike) -> LLMResult:  # type: ignore[override]
        """Execute three-phase response generation.

        Phase 1 — Build ``ResponseContext`` from session + input.
        Phase 2 — Check context sufficiency & decide path.
        Phase 3 — Normalise output & return.

        Args:
            input: The node input (continuation messages, payloads, …).

        Returns:
            ``LLMResult`` with the final response content as a string.
        """
        # Phase 1: build context
        context = self._build_response_context(input)

        # Phase 2: decide execution path
        if self._continuation_payload is not None:
            # Consolidated continuation — deliver directly without LLM rerouting
            logger.info(
                "node=%s continuation_payload present, delivering direct response",
                self.node_id,
            )
            return self._handle_continuation(context)

        if self._check_context_sufficiency(context):
            # Sufficient context — synthesise directly
            logger.info("node=%s context sufficient, synthesising directly", self.node_id)
            return self._synthesize_response(context)

        # Insufficient context
        digester_enabled = self.config.metadata.get("digester_enabled", True)
        if digester_enabled:
            logger.info(
                "node=%s context insufficient + digester enabled, deferring to on_complete",
                self.node_id,
            )
            self._needs_digestion = True
            # Return a placeholder — on_complete will suspend the queue
            return LLMResult(
                content="",
                role="assistant",
                metadata={"needs_digestion": True},
            )

        # Digester not available — gather context via tools
        logger.info(
            "node=%s context insufficient, gathering context via tools",
            self.node_id,
        )
        enriched = self._gather_context_via_tools(context)
        return self._synthesize_response(enriched)

    def on_complete(self, queue: NodeQueue, response: LLMResult | Any) -> None:
        """Post-completion hook for queue mutations.

        When ``_needs_digestion`` is ``True``, suspends the current node via
        ``queue.suspend_current_and_prepend(...)`` and prepends an
        ``InformationDigesterNode``.

        Args:
            queue: The node queue that can be mutated.
            response: The final LLM result or decision result.
        """
        if self._needs_digestion and self.config.metadata.get("digester_enabled", True):
            logger.info(
                "node=%s on_complete triggering digester suspension",
                self.node_id,
            )
            context = self._build_response_context(None)
            self._suspend_for_digestion(context, queue)
            self._needs_digestion = False
        else:
            logger.debug(
                "node=%s on_complete no action (needs_digestion=%s)",
                self.node_id,
                self._needs_digestion,
            )

    # ------------------------------------------------------------------
    # Phase 1: context building
    # ------------------------------------------------------------------

    def _build_response_context(
        self,
        input: NodeInputLike | None,
    ) -> ResponseContext:
        """Build a ``ResponseContext`` from the session and optional input.

        Gathers the aggregated result from the session context, the latest
        session messages, and any pending continuation payload.

        Args:
            input: The node input (may be ``None`` during ``on_complete``).

        Returns:
            A populated ``ResponseContext``.
        """
        from tinycua.loops.result_aggregation import AggregatedResult

        aggregated_result: AggregatedResult | None = None
        session_context: list[dict[str, Any]] = []
        latest_output: str | None = None

        # Extract aggregated result from session context
        if self.session is not None:
            session_context = list(self.session.session_context or [])
            # Look for aggregated result in session context entries.
            # Prefer structured metadata (set by ResultAggregatedNode) over
            # string marker parsing to avoid fragile format coupling.
            found_marker = False
            for entry in reversed(session_context):
                if "aggregated_result" in entry:
                    aggregated_result = entry["aggregated_result"]
                    latest_output = aggregated_result.final_context
                    found_marker = True
                    break
            if session_context and not found_marker:
                logger.warning(
                    "node=%s session_context has %d entries but no [AggregatedResult] marker found",
                    self.node_id,
                    len(session_context),
                )

        return ResponseContext(
            aggregated_result=aggregated_result,
            session_context=session_context,
            latest_output=latest_output,
            continuation_payload=deepcopy(self._continuation_payload),
        )

    # ------------------------------------------------------------------
    # Phase 2: context sufficiency check
    # ------------------------------------------------------------------

    def _check_context_sufficiency(
        self,
        context: ResponseContext,
    ) -> bool:
        """Analyse whether the available context is sufficient for synthesis.

        Returns ``True`` if:
        - An ``AggregatedResult`` is present (primary indicator).
        - The number of session context messages meets the configurable
          ``sufficiency_threshold`` (secondary heuristic).

        Args:
            context: The response context to evaluate.

        Returns:
            ``True`` if context is sufficient for direct synthesis.
        """
        # Primary check: aggregated result present
        if context.aggregated_result is not None:
            return True

        # Secondary check: session context size meets threshold
        threshold = self.config.metadata.get("sufficiency_threshold")
        if threshold is not None and isinstance(threshold, int):
            if len(context.session_context) >= threshold:
                logger.debug(
                    "node=%s context sufficiency: session context size=%d >= threshold=%d",
                    self.node_id,
                    len(context.session_context),
                    threshold,
                )
                return True

        logger.debug(
            "node=%s context insufficient (aggregated=%s, session_ctx=%d)",
            self.node_id,
            context.aggregated_result is not None,
            len(context.session_context),
        )
        return False

    # ------------------------------------------------------------------
    # Phase 2: continuation handling
    # ------------------------------------------------------------------

    def _handle_continuation(self, context: ResponseContext) -> LLMResult:
        """Handle a consolidated continuation (MandatoryPassthrough).

        Delivers a synthetic response acknowledging the continuation
        without an LLM rerouting call.

        Args:
            context: The response context (unused for now).

        Returns:
            An ``LLMResult`` with a simple acknowledgement.
        """
        # Simply return an acknowledgement result.
        # The continuation payload is consumed here.
        content = (
            "Continuation received.  Processing existing context "
            "to produce the final response."
        )
        self._continuation_payload = None  # consumed
        return LLMResult(content=content, role="assistant")

    # ------------------------------------------------------------------
    # Phase 2: digester suspension
    # ------------------------------------------------------------------

    def _suspend_for_digestion(
        self,
        context: ResponseContext,  # noqa: ARG002
        queue: NodeQueue,
    ) -> None:
        """Suspend the current node and prepend an ``InformationDigesterNode``.

        Checks ``max_digest_attempts`` to prevent infinite loops.

        Args:
            context: The current response context (unused directly).
            queue: The node queue to mutate.
        """
        max_attempts = self.config.metadata.get("max_digest_attempts", 3)
        if self._digest_attempts >= max_attempts:
            logger.warning(
                "node=%s max digest attempts (%d) reached, skipping suspension",
                self.node_id,
                max_attempts,
            )
            return

        # Local import to avoid circular dependency
        from tinycua.loops.information_digester import (
            TinyCUAInformationDigesterNode,
        )

        digester = TinyCUAInformationDigesterNode(parent=self)
        queue.suspend_current_and_prepend([digester])
        self._digest_attempts += 1

        logger.info(
            "node=%s suspended for digestion (attempt %d/%d)",
            self.node_id,
            self._digest_attempts,
            max_attempts,
        )

    # ------------------------------------------------------------------
    # Phase 2: tool-based context gathering
    # ------------------------------------------------------------------

    def _gather_context_via_tools(
        self,
        context: ResponseContext,
    ) -> ResponseContext:
        """Use available tools to gather additional context.

        Currently a placeholder that returns the context unchanged.
        Full implementation will use ``NodeToolPolicy(include_agent_tools="all")``
        to invoke agent tools for context gathering.

        Args:
            context: The current response context.

        Returns:
            The (possibly enriched) response context.
        """
        logger.warning(
            "node=%s _gather_context_via_tools called — placeholder implementation, "
            "no tools invoked. Full implementation planned for M3.6.",
            self.node_id,
        )
        # Placeholder: just returns the context as-is.
        # In the full implementation, this would invoke tools to gather
        # additional information from external sources.
        return context

    # ------------------------------------------------------------------
    # Phase 2: response synthesis
    # ------------------------------------------------------------------

    def _synthesize_response(self, context: ResponseContext) -> LLMResult:
        """Build the final response using the aggregated context.

        Delegates to the inherited ``ProcessNode.__call__`` machinery to
        call the LLM, validate output, and handle retries.  Falls back
        to a configurable message when no LLM client is available or
        retries are exhausted.

        Args:
            context: The enriched response context.

        Returns:
            An ``LLMResult`` with the final response content as a string.
        """
        if self.config.llm_client is None and self.session is not None:
            # No LLM client — return fallback message
            fallback = self.config.metadata.get(
                "fallback_message",
                _DEFAULT_FALLBACK,
            )
            logger.warning(
                "node=%s no LLM client configured, returning fallback message",
                self.node_id,
            )
            return LLMResult(content=fallback, role="assistant")

        try:
            # Build a simple input from the context and delegate to the
            # inherited ProcessNode.__call__ for LLM invocation, validation,
            # and retry handling.
            from tinycua.models.node_input import NodeInput

            # Format context into messages for the LLM
            messages: list[dict[str, str]] = []
            if context.aggregated_result is not None:
                messages.append({
                    "role": "system",
                    "content": (
                        f"Aggregated result:\n"
                        f"{context.aggregated_result.final_context}"
                    ),
                })
            if context.session_context:
                for entry in context.session_context:
                    messages.append({
                        "role": str(entry.get("role", "assistant")),
                        "content": str(entry.get("content", "")),
                    })

            input_data = NodeInput(
                input_type="continuation",
                messages=messages or [{"role": "user", "content": "Generate final response."}],
            )

            # Ensure we have a session for ProcessNode.__call__
            if self.session is None:
                from tinycua.models.session import Session

                self.session = Session()

            result = super().__call__(input_data)
            # Ensure content is a string
            if not isinstance(result.content, str):
                result.content = str(result.content)
            return result

        except NodeExecutionError as exc:
            logger.error(
                "node=%s synthesis failed with NodeExecutionError: %s",
                self.node_id,
                exc,
            )
            fallback = self.config.metadata.get(
                "fallback_message",
                _DEFAULT_FALLBACK,
            )
            return LLMResult(content=fallback, role="assistant")

        except Exception as exc:  # noqa: BLE001
            if self.config.metadata.get("strict_mode", False):
                raise
            logger.error(
                "node=%s unexpected error during synthesis: %s",
                self.node_id,
                exc,
                exc_info=True,
            )
            fallback = self.config.metadata.get(
                "fallback_message",
                _DEFAULT_FALLBACK,
            )
            return LLMResult(content=fallback, role="assistant")

    # ------------------------------------------------------------------
    # Phase 3: terminal normalisation (built into __call__ return)
    # ------------------------------------------------------------------
    # Normalisation happens naturally: __call__ always returns LLMResult
    # with string content.  The _synthesize_response method ensures the
    # content attribute is a string via str() conversion.

