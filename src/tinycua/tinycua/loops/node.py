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
            messages.extend(
                {  # type: ignore[misc]
                    "role": m["role"],
                    "content": m["content"],
                }
                for m in session.session_context
            )

        # Add chat history if policy says so
        if self.config.message_policy.include_chat_history and session.chat_history:
            messages.extend(
                {  # type: ignore[misc]
                    "role": m["role"],
                    "content": m["content"],
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

    def record_output(self, response: LLMResult) -> None:
        """Record the node's output to the session.

        Args:
            response: The LLM response to record.
        """
        if self.session is not None:
            self.session.session_context.append(
                {
                    "role": response.role,
                    "content": response.content,
                }
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

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Post-completion hook for queue mutations.

        Args:
            queue: The node queue that can be mutated.
            response: The final LLM response.
        """
        logger.debug(
            "node=%s on_complete response_len=%d",
            self.node_id,
            len(response.content),
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
            last_response = self._call_llm(messages)

            validation = self.validate_output(last_response)
            if validation.is_valid:
                break

            # Validation failed — retry or exhaust
            if attempt < max_attempts:
                error = ValidationError("; ".join(validation.errors))
                retry_text = self.build_retry_continuation(error, attempt)
                messages.append(
                    {"role": "assistant", "content": retry_text}  # type: ignore[misc]
                )
            else:
                # Exhausted — handle per policy
                if retry_policy.on_retry_exhausted == "raise":
                    raise NodeExecutionError(
                        f"Retry exhausted after {max_attempts} attempts: "
                        + "; ".join(validation.errors)
                    )
                # For record_failure / route_failure, continue with last response

        assert last_response is not None  # noqa: S101
        self.record_output(last_response)
        self.propagate()
        self.on_complete(
            queue=object(),  # type: ignore[arg-type]  # placeholder — orchestrator passes real queue
            response=last_response,
        )
        return last_response


class DecisionNode(ProcessNode):
    """Node that performs analysis + classification + route dispatch.

    ``__call__`` orchestrates: analysis → classification → dispatch.

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
            The matched route label.

        Raises:
            ValueError: If no registered label matches the classification.
        """
        content = classification_response.content.strip().lower()

        for label in self.classification_labels:
            if label.lower() in content:
                return label

        msg = (
            f"Classification label not recognized: {classification_response.content!r}. "
            f"Registered labels: {self.classification_labels}"
        )
        raise ValueError(msg)

    def __call__(self, input: NodeInputLike) -> DecisionResult:  # type: ignore[override]
        """Execute the decision node with analysis + classification flow.

        Includes retry logic: if classification returns an unrecognized label,
        retries per NodeRetryPolicy. After retries exhausted, falls back to
        the first classification label.

        Args:
            input: The node input.

        Returns:
            DecisionResult with route label and LLM responses.

        Raises:
            NodeExecutionError: If no session is attached or LLM fails
                after retry exhaustion with on_retry_exhausted="raise".
        """
        if self.session is None:
            msg = f"Node {self.node_id} has no session attached"
            raise NodeExecutionError(msg)

        messages = self.build_messages(self.session, input)
        retry_policy = self.config.retry_policy
        max_attempts = max(retry_policy.max_attempts, 1)

        last_analysis: LLMResult | None = None
        last_classification: LLMResult | None = None
        route_label = self.classification_labels[0] if self.classification_labels else "default"

        for attempt in range(1, max_attempts + 1):
            # Step 1: Analysis call
            analysis_response = self._analysis_call(messages)

            # Step 2: Classification call
            classification_response = self._classification_call(messages, analysis_response)

            # Step 3: Dispatch route (may raise ValueError)
            try:
                route_label = self._dispatch_route(classification_response)
                last_analysis = analysis_response
                last_classification = classification_response
                break
            except ValueError:
                last_analysis = analysis_response
                last_classification = classification_response

                if attempt < max_attempts:
                    # Retry: append retry instruction to messages
                    retry_text = (
                        f"Retry attempt {attempt}: "
                        f"Classification label '{classification_response.content.strip()}' "
                        f"is not recognized. Valid labels: {self.classification_labels}. "
                        f"Please respond with exactly one of the valid labels."
                    )
                    messages.append(
                        {"role": "assistant", "content": analysis_response.content}
                    )
                    messages.append(
                        {"role": "user", "content": retry_text}
                    )
                else:
                    # Exhausted — handle per policy
                    if retry_policy.on_retry_exhausted == "raise":
                        raise NodeExecutionError(
                            f"Classification retry exhausted after {max_attempts} attempts: "
                            f"last label was {classification_response.content!r}"
                        )
                    # Fallback to "uncertain" when retries exhausted
                    route_label = "uncertain"

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
