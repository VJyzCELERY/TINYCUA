"""Base Node, ProcessNode, and DecisionNode classes for TinyCUA loops."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tinycua.config.system_prompt import SystemPromptBuilder
from tinycua.config.types import LLMResult, ValidationError, ValidationResult
from tinycua.models.node_input import (
    NodeInputLike,
    convert_node_input_to_messages,
)
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue

logger = logging.getLogger(__name__)


def build_messages_with_dedupe(
    session: Session,
    dedupe_by_origin_record_id: bool = False,
) -> list[dict[str, Any]]:
    """Build messages for LLM call with optional deduplication.

    When dedupe_by_origin_record_id=True, filters session_context entries
    to remove duplicates by origin_record_id (falling back to record_id)
    before assembling LLM-bound messages.

    Args:
        session: The session containing context and history.
        dedupe_by_origin_record_id: Whether to deduplicate by origin_record_id.

    Returns:
        List of message dictionaries for the LLM call.
    """
    messages: list[dict[str, Any]] = []

    # Get session context entries
    context_entries = session.session_context

    if dedupe_by_origin_record_id:
        # Deduplicate by origin_record_id
        seen_origin_ids: dict[str, Any] = {}
        deduped_entries = []

        for entry in context_entries:
            # Use origin_record_id if present, otherwise use record_id
            key = entry.origin_record_id if entry.origin_record_id else entry.record_id

            if key not in seen_origin_ids:
                seen_origin_ids[key] = entry
                deduped_entries.append(entry)

        context_entries = deduped_entries

    # Convert entries to message dicts
    for entry in context_entries:
        messages.append({
            "role": "user",  # Default role for context entries
            "content": str(entry.content),
        })

    return messages


class NodeExecutionError(Exception):
    """Raised when a node execution fails after retry exhaustion."""


@dataclass
class DecisionResult:
    """Return type from DecisionNode.__call__().

    Contains the route label chosen by the classification step and the
    underlying LLM responses for observability and downstream debugging.

    Attributes:
        route_label: The classification label selected by the decision node.
        analysis_response: LLM response from the analysis call.
        classification_response: LLM response from the classification call.
    """

    route_label: str
    analysis_response: LLMResult
    classification_response: LLMResult


class Node(ABC):
    """Base class for all TinyCUA nodes.

    Concrete nodes must implement ``__call__(input: NodeInputLike) -> result``.
    Lifecycle hooks are called automatically by ``ProcessNode.__call__``.

    Attributes:
        node_id: Unique identifier for this node.
        session: Attached session (set via ``ensure_session()``).
        parent: Optional parent node for session adoption.
        config: Node configuration with policies.
        is_terminal: Whether this node is terminal in the execution graph.
    """

    node_id: str
    session: Session | None = None
    parent: Node | None = None
    config: NodeConfigBase
    is_terminal: bool = False

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = "",
        is_terminal: bool = False,
    ) -> None:
        """Initialize the node.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration.
            instruction: Hardcoded instruction string for this node type.
            is_terminal: Whether this node is terminal in the execution graph.
        """
        self.node_id = node_id
        self.config = config
        self.session = None
        self.parent = None
        self.is_terminal = is_terminal
        self._instruction = instruction

    def ensure_session(self, root_or_parent_session: Session) -> Session:
        """Create or adopt a session.

        If ``self.session`` is already set, return it.
        Otherwise, adopt the parent node's session if a parent exists,
        or create a new session from ``root_or_parent_session``.

        Args:
            root_or_parent_session: The root session or a parent's session.

        Returns:
            The attached session.

        Raises:
            ValueError: If ``root_or_parent_session`` is None and no parent exists.
        """
        if self.session is not None:
            return self.session

        if self.parent is not None and hasattr(self.parent, "session"):
            parent_node = self.parent
            if parent_node.session is not None:  # type: ignore[union-attr]
                self.session = parent_node.session  # type: ignore[union-attr]
                return self.session  # type: ignore[return-value]

        if root_or_parent_session is None:
            msg = "No session available: root_or_parent_session is None and no parent"
            raise ValueError(msg)

        self.session = root_or_parent_session
        return self.session

    def build_instruction(
        self, override_instructions: str | None = None
    ) -> str:
        """Build the complete instruction string.

        Merges the hardcoded instruction with configurable append and
        optional override.

        Args:
            override_instructions: Optional override for the instruction.

        Returns:
            The complete instruction string.
        """
        parts: list[str] = []

        if override_instructions:
            parts.append(override_instructions)
        elif self._instruction:
            parts.append(self._instruction)

        if self.config.custom_instruction_append:
            parts.append(self.config.custom_instruction_append)

        return "\n".join(parts) if parts else ""

    def build_messages(
        self, session: Session, input: NodeInputLike
    ) -> list[dict[str, str]]:
        """Build the complete message list for an LLM call.

        Assembles system + conversation + continuation messages.

        Args:
            session: The session containing context and history.
            input: The node input to convert to continuation messages.

        Returns:
            List of message dictionaries for the LLM call.
        """
        messages: list[dict[str, str]] = []

        # Build system message via SystemPromptBuilder
        builder = SystemPromptBuilder()
        instruction = self.build_instruction()
        if instruction:
            builder.add_static(instruction)

        system_msg = builder.build()
        if system_msg["content"]:
            messages.append(system_msg)

        # Add session context if policy says so
        if (
            self.config.message_policy.include_session_context
            and session.session_context
        ):
            for m in session.session_context:
                if isinstance(m, dict):
                    messages.append({
                        "role": m.get("role", "user"),
                        "content": str(m.get("content", "")),
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": str(m.content),
                    })

        # Add chat history if policy says so
        if self.config.message_policy.include_chat_history and session.chat_history:
            messages.extend(
                {
                    "role": m.role,
                    "content": str(m.content),
                }
                for m in session.chat_history
            )

        # Add continuation messages from input
        continuation = convert_node_input_to_messages(input, source="internal")
        messages.extend(continuation)  # type: ignore[arg-type]

        return messages

    def validate_output(self, response: LLMResult) -> ValidationResult:
        """Validate the LLM response against policy constraints.

        Checks ``required_tool_calls`` and ``required_output_schema`` from
        ``NodeRetryPolicy``.

        Args:
            response: The LLM response to validate.

        Returns:
            ValidationResult with is_valid and errors.
        """
        result = ValidationResult()
        result.is_valid = True
        result.errors = []

        retry_policy = self.config.retry_policy

        # Check required tool calls
        if retry_policy.required_tool_calls:
            response_tool_names = {tc.get("function", {}).get("name", "") for tc in response.tool_calls}
            for required in retry_policy.required_tool_calls:
                if required not in response_tool_names:
                    result.is_valid = False
                    result.errors.append(
                        f"Missing required tool call: {required}"
                    )

        # Check required output schema
        if retry_policy.required_output_schema is not None:
            try:
                import json
                json.loads(response.content)
            except (json.JSONDecodeError, TypeError, ValueError):
                result.is_valid = False
                result.errors.append(
                    f"Output does not match required schema: {retry_policy.required_output_schema}"
                )

        # Check custom validation function
        if retry_policy.validation_fn is not None:
            try:
                custom_result = retry_policy.validation_fn(response)
                if custom_result is not None:
                    if hasattr(custom_result, "is_valid") and not custom_result.is_valid:
                        result.is_valid = False
                        if hasattr(custom_result, "errors"):
                            result.errors.extend(custom_result.errors)
            except (ValueError, TypeError, KeyError) as e:
                result.is_valid = False
                result.errors.append(f"Validation function error: {e}")

        return result

    def build_retry_continuation(
        self, error: ValidationError, attempt: int
    ) -> str:
        """Build a retry continuation message.

        Creates an assistant-role retry message with error details
        and attempt count.

        Args:
            error: The validation error that triggered retry.
            attempt: The current attempt number.

        Returns:
            The retry continuation text.
        """
        parts = [
            f"Retry attempt {attempt}: Validation failed.",
            f"Error: {error!s}",
        ]

        if self.config.custom_retry_append:
            parts.append(self.config.custom_retry_append)

        return " ".join(parts)

    def _safe_call(
        self, hook_method: Any, *args: Any, **kwargs: Any
    ) -> str | None:
        """Exception-safe monitor hook caller.

        Wraps a monitor hook call in try/except. Logs exceptions at
        debug level and returns None on failure.

        Args:
            hook_method: The monitor hook method to call.
            *args: Positional arguments for the hook.
            **kwargs: Keyword arguments for the hook.

        Returns:
            The hook's return value, or None on exception.
        """
        if hook_method is None:
            return None
        try:
            return hook_method(*args, **kwargs)
        except Exception:
            logger.debug(
                "node=%s monitor_hook_exception hook=%s",
                self.node_id,
                getattr(hook_method, "__name__", str(hook_method)),
                exc_info=True,
            )
            return None

    def _build_retry_text(self, error: ValidationError, attempt: int) -> str:
        """Build retry continuation text using custom or default builder.

        If ``retry_policy.retry_continuation_builder`` is set, delegates
        to it. Otherwise falls back to ``build_retry_continuation()``.

        Args:
            error: The validation error that triggered retry.
            attempt: The current attempt number.

        Returns:
            The retry continuation text.
        """
        builder = self.config.retry_policy.retry_continuation_builder
        if builder is not None:
            try:
                text = builder(error, attempt)
                if text:
                    return text
            except Exception:
                logger.debug(
                    "node=%s retry_continuation_builder_exception",
                    self.node_id,
                    exc_info=True,
                )
        return self.build_retry_continuation(error, attempt)

    def _handle_exhaustion(
        self,
        validation: ValidationResult,
        max_attempts: int,
    ) -> None:
        """Handle retry exhaustion based on policy.

        Dispatches to the appropriate exhaustion handler:
        - ``raise``: Raises ``NodeExecutionError``
        - ``record_failure``: Records failure state to session
        - ``route_failure``: Calls failure route, falls back to ``record_failure``

        Args:
            validation: The final validation result.
            max_attempts: The maximum attempts that were allowed.

        Raises:
            NodeExecutionError: If policy is ``raise``.
        """
        retry_policy = self.config.retry_policy
        error = ValidationError("; ".join(validation.errors))

        # Fire monitor exhaustion hook before handling
        if self.config.monitor is not None:
            self._safe_call(
                self.config.monitor.on_retry_exhausted,
                self.node_id,
                self.session.session_id if self.session else "",
                error,
                max_attempts,
            )

        if retry_policy.on_retry_exhausted == "raise":
            raise NodeExecutionError(
                f"Retry exhausted after {max_attempts} attempts: "
                + "; ".join(validation.errors)
            )
        elif retry_policy.on_retry_exhausted == "route_failure":
            if self._call_failure_route():
                return
            # No failure route defined — fall back to record_failure
            self._record_failure(validation, max_attempts)
        else:
            # record_failure (default)
            self._record_failure(validation, max_attempts)

    def _record_failure(
        self, validation: ValidationResult, max_attempts: int
    ) -> None:
        """Record failure state to session context.

        Creates a ``SessionContextEntry`` with ``segment="output"``
        containing failure metadata and calls ``propagate()`` if a
        propagation rule exists.

        Args:
            validation: The validation result with error details.
            max_attempts: The maximum attempts that were allowed.
        """
        from tinycua.models.session_context_entry import SessionContextEntry

        error_msg = "; ".join(validation.errors)
        content = (
            f"RETRY_EXHAUSTED node={self.node_id} "
            f"attempts={max_attempts} errors={error_msg}"
        )

        if self.session is not None:
            self.session.session_context.append(
                SessionContextEntry(
                    content=content,
                    segment="output",
                    source_node_id=self.node_id,
                    source_session_id=self.session.session_id,
                )
            )

        logger.warning(
            "node=%s retry_exhausted attempts=%d errors=%s",
            self.node_id,
            max_attempts,
            error_msg,
        )

        # Propagate failure if a propagation rule is configured
        if self.config.propagation is not None:
            self.propagate()

    def _call_failure_route(self) -> bool:
        """Check if on_complete defines a failure route and call it.

        Default implementation — always returns False. Subclasses override
        this method to define failure routes. When False, exhaustion falls
        back to _record_failure().

        Returns:
            True if a failure route was called, False otherwise.
        """
        logger.debug("node=%s _call_failure_route (no route defined)", self.node_id)
        return False

    def record_output(self, response: LLMResult) -> None:
        """Record the node's output to the session.

        Args:
            response: The LLM response to record.
        """
        if self.session is not None:
            from tinycua.models.session_context_entry import SessionContextEntry
            self.session.session_context.append(
                SessionContextEntry(
                    content=response.content,
                    segment="output",
                )
            )
        logger.info(
            "node=%s record_output content_len=%d",
            self.node_id,
            len(response.content),
        )

    def propagate(self) -> None:
        """Post-execution propagation hook.

        Default implementation is a no-op. Subclasses override to
        implement specific propagation behavior.
        """
        logger.debug("node=%s propagate (no-op)", self.node_id)

    def on_complete(self, queue: NodeQueue, response: LLMResult | DecisionResult) -> None:
        """Post-completion hook for queue mutations.

        Args:
            queue: The node queue that can be mutated.
            response: The final LLM response.
        """
        # Safely access .content which only exists on LLMResult
        content = response.content if isinstance(response, LLMResult) else response.route_label
        logger.debug(
            "node=%s on_complete response_len=%d",
            self.node_id,
            len(content),
        )

    @abstractmethod
    def __call__(self, input: NodeInputLike) -> Any:
        """Execute the node with the given input."""


class ProcessNode(Node):
    """Primary node type for non-decision processing.

    ``__call__`` orchestrates: build → validate → call LLM → retry →
    record → propagate → on_complete.
    """

    def _call_llm(self, messages: list[dict[str, str]]) -> LLMResult:
        """Invoke the LLM with built messages.

        Args:
            messages: The message list for the LLM call.

        Returns:
            The LLM response wrapped in LLMResult.

        Raises:
            NodeExecutionError: If no LLM client is configured.
        """
        if self.config.llm_client is None:
            msg = f"No LLM client configured for node {self.node_id}"
            raise NodeExecutionError(msg)

        raw_response = self.config.llm_client(messages)

        # Convert dict response to LLMResult
        if isinstance(raw_response, dict):
            return LLMResult(
                content=raw_response.get("content", ""),
                role=raw_response.get("role", "assistant"),
                tool_calls=raw_response.get("tool_calls", []),
                metadata=raw_response.get("metadata", {}),
            )
        return raw_response  # type: ignore[return-value]

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute the node with the given input.

        Orchestrates: build messages → validate → call LLM → retry loop →
        record → propagate → on_complete.

        Args:
            input: The node input.

        Returns:
            The LLM response.

        Raises:
            NodeExecutionError: If retry is exhausted and policy is "raise".
        """
        if self.session is None:
            msg = f"Node {self.node_id} has no session attached"
            raise NodeExecutionError(msg)

        messages = self.build_messages(self.session, input)
        retry_policy = self.config.retry_policy
        max_attempts = max(retry_policy.max_attempts, 1)

        last_response: LLMResult | None = None
        for attempt in range(1, max_attempts + 1):
            # Fire monitor before-hook
            if self.config.monitor is not None:
                self._safe_call(
                    self.config.monitor.on_before_node_call,
                    self.node_id,
                    self.session.session_id,
                    attempt,
                    messages,
                    [],
                )

            last_response = self._call_llm(messages)

            validation = self.validate_output(last_response)
            if validation.is_valid:
                break

            # Fire monitor after-hook (validation failed)
            if self.config.monitor is not None:
                self._safe_call(
                    self.config.monitor.on_after_node_call,
                    self.node_id,
                    self.session.session_id,
                    attempt,
                    last_response,
                    validation,
                )

            # Validation failed — retry or exhaust
            if attempt < max_attempts:
                error = ValidationError("; ".join(validation.errors))
                retry_text = self._build_retry_text(error, attempt)
                messages.append(
                    {"role": "assistant", "content": retry_text}  # type: ignore[misc]
                )
            else:
                # Exhausted — handle per policy
                self._handle_exhaustion(validation, max_attempts)

        assert last_response is not None  # noqa: S101
        self.record_output(last_response)
        self.propagate()
        # NOTE: on_complete is NOT called here — the orchestrator
        # (TinyCUALoop._execute_node) calls on_complete with the real queue.
        return last_response


class DecisionNode(ProcessNode):
    """Node that performs analysis + classification + route dispatch.

    ``__call__`` orchestrates: analysis → classification → dispatch.

    Classification matching uses **substring containment** (``label in content``),
    not exact match. For example, if ``classification_labels=["test"]`` and the
    LLM returns ``"latest"``, validation passes because ``"test" in "latest"`` is
    True. This is intentional for leniency but means short labels that are
    substrings of common words may produce false positives. Consider label
    specificity when choosing classification labels.

    Attributes:
        classification_labels: Allowed classification labels for routing.
    """

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = "",
        classification_labels: list[str] | None = None,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the decision node.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration.
            instruction: Hardcoded instruction for this node.
            classification_labels: Allowed classification labels.
            is_terminal: Whether this node is terminal.
        """
        super().__init__(
            node_id=node_id,
            config=config,
            instruction=instruction,
            is_terminal=is_terminal,
        )
        self.classification_labels = classification_labels or []

    def _analysis_call(self, messages: list[dict[str, str]]) -> LLMResult:
        """Perform the first LLM call for analysis.

        Args:
            messages: The message list for the analysis call.

        Returns:
            The analysis response.
        """
        return self._call_llm(messages)

    def _classification_call(
        self,
        analysis_messages: list[dict[str, str]],
        analysis_response: LLMResult,
    ) -> LLMResult:
        """Perform the second LLM call for classification.

        Appends the analysis result to the messages and invokes the LLM
        with classification instructions.

        Args:
            analysis_messages: The original analysis messages.
            analysis_response: The response from the analysis call.

        Returns:
            The classification response.
        """
        classification_messages = list(analysis_messages)
        classification_messages.append(
            {"role": "assistant", "content": analysis_response.content}
        )

        # Add classification instruction
        labels_str = ", ".join(self.classification_labels)
        classification_messages.append(
            {
                "role": "user",
                "content": (
                    f"Classify your analysis into one of these categories: "
                    f"{labels_str}. Respond with only the category label."
                ),
            }
        )

        return self._call_llm(classification_messages)

    def _dispatch_route(self, classification_response: LLMResult) -> str:
        """Map classification label to route.

        Args:
            classification_response: The classification LLM response.

        Returns:
            The matched route label, or the first allowed label as fallback.
        """
        content = classification_response.content.strip().lower()

        for label in self.classification_labels:
            if label.lower() in content:
                return label

        # Fallback: return first allowed label
        return self.classification_labels[0] if self.classification_labels else "default"

    def _validate_classification(self, classification_response: LLMResult) -> ValidationResult:
        """Validate that classification response matches an allowed label.

        Args:
            classification_response: The classification LLM response.

        Returns:
            ValidationResult with is_valid and errors.
        """
        content = classification_response.content.strip().lower()
        for label in self.classification_labels:
            if label.lower() in content:
                return ValidationResult(is_valid=True, errors=[])
        return ValidationResult(
            is_valid=False,
            errors=[f"Invalid classification: {classification_response.content!r} "
                    f"not in {self.classification_labels}"],
        )

    def __call__(self, input: NodeInputLike) -> DecisionResult:  # type: ignore[override]
        """Execute the decision node with analysis + classification flow.

        Includes retry loop for classification validation.

        Args:
            input: The node input.

        Returns:
            DecisionResult with route label and LLM responses.

        Raises:
            NodeExecutionError: If no session is attached, LLM fails,
                or classification retry is exhausted.
        """
        if self.session is None:
            msg = f"Node {self.node_id} has no session attached"
            raise NodeExecutionError(msg)

        messages = self.build_messages(self.session, input)
        retry_policy = self.config.retry_policy
        max_attempts = max(retry_policy.max_attempts, 1)

        last_analysis: LLMResult | None = None
        last_classification: LLMResult | None = None
        route_label = "default"

        for attempt in range(1, max_attempts + 1):
            # Fire monitor before-hook
            if self.config.monitor is not None:
                self._safe_call(
                    self.config.monitor.on_before_node_call,
                    self.node_id,
                    self.session.session_id,
                    attempt,
                    messages,
                    [],
                )

            # Step 1: Analysis call
            last_analysis = self._analysis_call(messages)

            # Step 2: Classification call
            last_classification = self._classification_call(messages, last_analysis)

            # Step 3: Validate classification
            validation = self._validate_classification(last_classification)
            if validation.is_valid:
                route_label = self._dispatch_route(last_classification)
                break

            # Fire monitor after-hook (validation failed)
            if self.config.monitor is not None:
                self._safe_call(
                    self.config.monitor.on_after_node_call,
                    self.node_id,
                    self.session.session_id,
                    attempt,
                    last_classification,
                    validation,
                )

            # Classification failed — retry or exhaust
            if attempt < max_attempts:
                error = ValidationError("; ".join(validation.errors))
                retry_text = self._build_retry_text(error, attempt)
                messages.append(
                    {"role": "assistant", "content": retry_text}  # type: ignore[misc]
                )
            else:
                # Exhausted
                self._handle_exhaustion(validation, max_attempts)
                # If not raised, use fallback dispatch
                route_label = self._dispatch_route(last_classification)

        assert last_analysis is not None  # noqa: S101
        assert last_classification is not None  # noqa: S101

        # Record the classification response as output
        record_response = LLMResult(
            content=f"[Analysis] {last_analysis.content}\n[Classification] {route_label}",
            role="assistant",
        )
        self.record_output(record_response)
        self.propagate()

        return DecisionResult(
            route_label=route_label,
            analysis_response=last_analysis,
            classification_response=last_classification,
        )
