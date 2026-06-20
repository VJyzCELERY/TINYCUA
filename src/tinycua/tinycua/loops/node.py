"""Base Node, ProcessNode, and DecisionNode classes for TinyCUA loops."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from tinycua.config.system_prompt import SystemPromptBuilder, build_runtime_context
from tinycua.config.types import LLMResult, ValidationError, ValidationResult
from tinycua.loops.context_rendering import looks_like_planner_prose, render_llm_content
from tinycua.loops.route_classifier import RouteClassifier
from tinycua.models.node_input import (
    NodeInputLike,
    convert_node_input_to_messages,
)
from tinycua.models.session import Session

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.loops.node_queue import NodeQueue

logger = logging.getLogger(__name__)
_UNBOUNDED_RETRY_ATTEMPTS = 1_000_000_000


# Internal bookkeeping messages that should never reach the LLM.
_SKIP_CONTENT_PREFIXES = (
    "Scheduled analysis effort",
    "Analysis effort complete",
)


def _deduplicate_context_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicate assistant messages and internal bookkeeping noise."""
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, str):
            result.append(msg)
            continue
        stripped = content.strip()
        # Skip deterministic controller noise
        if stripped.startswith(_SKIP_CONTENT_PREFIXES):
            continue
        # Skip exact duplicates
        if stripped in seen:
            continue
        seen.add(stripped)
        result.append(msg)
    return result


def build_messages_with_dedupe(
    session: Session,
    dedupe_by_origin_record_id: bool = False,
    skip_record_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Build messages for LLM call with optional deduplication.

    When dedupe_by_origin_record_id=True, filters session_context entries
    to remove duplicates by origin_record_id (falling back to record_id)
    before assembling LLM-bound messages.

    Args:
        session: The session containing context and history.
        dedupe_by_origin_record_id: Whether to deduplicate by origin_record_id.
        skip_record_ids: Record IDs already represented by direct node input.

    Returns:
        List of message dictionaries for the LLM call.
    """
    messages: list[dict[str, Any]] = []
    skip_record_ids = skip_record_ids or set()

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

    # Convert entries to message dicts, dropping blank content at the API boundary.
    for entry in context_entries:
        if entry.record_id in skip_record_ids or (
            entry.origin_record_id is not None
            and entry.origin_record_id in skip_record_ids
        ):
            continue
        content = render_llm_content(entry.content)
        if content.strip():
            messages.append({"role": "assistant", "content": content})

    return _deduplicate_context_messages(messages)


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


@dataclass(frozen=True)
class NodeRunContext:
    """Runtime services a node uses to execute inside an orchestrator.

    The loop owns queue orchestration. Nodes own the execution entrypoint and
    call these injected services to perform provider/tool/runtime-specific work.
    """

    sync_executor: Callable[[Any, NodeInputLike], Awaitable[tuple[str, list[dict[str, Any]]]]]
    stream_executor: Callable[[Any, NodeInputLike], AsyncIterator[dict[str, Any]]]


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
        continuation: str = "",
        is_terminal: bool = False,
    ) -> None:
        """Initialize the node.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration.
            instruction: Hardcoded instruction string for this node type.
            continuation: Hardcoded continuation string for this node type.
            is_terminal: Whether this node is terminal in the execution graph.
        """
        self.node_id = node_id
        self.config = config
        self.session = None
        self.parent = None
        self.is_terminal = is_terminal
        self._instruction = instruction
        self._continuation = continuation
        self._last_retry_exhaustion: dict[str, Any] | None = None
        # ponytail: cache the assembled system message per (node, tools) so
        # repeated calls in a retry loop replay identical system bytes — keeps
        # the prompt-cache prefix stable (llama.cpp KV reuse, OpenAI prefix
        # caching). Invalidated only when the resolved tools list changes.
        self._cached_system_message: dict[str, str] | None = None
        self._cached_system_key: tuple[int, ...] | None = None

    def ensure_session(self, root_or_parent_session: Session) -> Session:
        """Create or return an isolated node session.

        If ``self.session`` is already set, return it.
        Otherwise, create a fresh scoped session from ``root_or_parent_session``.

        Args:
            root_or_parent_session: The root session or a parent's session.

        Returns:
            The attached session.

        Raises:
            ValueError: If ``root_or_parent_session`` is None and no parent exists.
        """
        if self.session is not None:
            return self.session

        if root_or_parent_session is None:
            msg = "No session available: root_or_parent_session is None and no parent"
            raise ValueError(msg)

        self.session = Session(parent_id=root_or_parent_session.session_id)
        self.session.session_config = root_or_parent_session.session_config
        self.session.input_context = list(root_or_parent_session.input_context)
        self.session.task = root_or_parent_session.task
        self.session.task_store = root_or_parent_session.task_store
        return self.session

    def build_instruction(self, override_instructions: str | None = None) -> str:
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

    def build_continuation(self, session: Session | None = None) -> str:
        """Build the assistant-role continuation prompt for this node.

        Args:
            session: Optional node/root session for dynamic continuation context.

        Returns:
            The complete continuation prompt, or an empty string.
        """
        del session
        parts: list[str] = []
        if self._continuation:
            parts.append(self._continuation)
        if self.config.custom_continuation_append:
            parts.append(self.config.custom_continuation_append)
        return "\n".join(parts)

    def build_tool_system_prompt(self, resolved_tools: list[Any] | None = None) -> str:
        """Build node-level tool instructions for the single system prompt.

        The SDK already sends native function schemas to the provider
        (``tools=...``, ``tool_choice="auto"``) and the ToolExecutor runs the
        returned tool calls, so the prompt must NOT re-list tools as prose or
        instruct the LLM how to call them — that's the SDK/provider's job and
        only duplicates the native schemas (and invites hallucinated JSON
        protocol). Returns empty; node instructions own the "use tools" guard.
        """
        del resolved_tools  # SDK exposes tools natively; no prose needed.
        return ""

    def build_system_message(
        self,
        resolved_tools: list[Any] | None = None,
    ) -> dict[str, str]:
        """Build one system message from node sections and tool guidance.

        Cached per (node, tools-signature) so repeated calls in a session's
        retry loop replay the SAME system bytes — essential for prompt-cache
        prefix stability (llama.cpp KV reuse, OpenAI prefix caching). The
        cache key is the id() tuple of the resolved tools list so identical
        tool objects reuse the cached message.
        """
        cache_key = tuple(id(t) for t in (resolved_tools or []))
        if (
            self._cached_system_message is not None
            and self._cached_system_key == cache_key
        ):
            return self._cached_system_message
        builder = SystemPromptBuilder()
        instruction = self.build_instruction()
        if instruction:
            builder.add_static(instruction)
        builder.add_dynamic_context(build_runtime_context())
        tool_prompt = self.build_tool_system_prompt(resolved_tools)
        if tool_prompt:
            builder.add_dynamic_context(tool_prompt)
        message = builder.build()
        self._cached_system_message = message
        self._cached_system_key = cache_key
        return message

    def build_messages(
        self,
        session: Session,
        input: NodeInputLike,
        resolved_tools: list[Any] | None = None,
    ) -> list[dict[str, str]]:
        """Build the complete message list for an LLM call.

        Assembles system + conversation + continuation messages.

        Args:
            session: The session containing context and history.
            input: The node input to convert to continuation messages.
            resolved_tools: Tools available to this node for prompt exposure.

        Returns:
            List of message dictionaries for the LLM call.
        """
        messages: list[dict[str, str]] = []

        system_msg = self.build_system_message(resolved_tools)
        if system_msg["content"]:
            messages.append(system_msg)

        # Add continuation messages from input
        continuation = convert_node_input_to_messages(input, source="internal")
        for message in continuation:
            content = str(message.get("content", ""))
            if not content.strip():
                continue
            role = message.get("role", "assistant")
            if role == "user" and not self.config.message_policy.include_input_context:
                role = "assistant"
            messages.append({"role": role, "content": content})

        # Current date/time as a small USER message in the volatile suffix —
        # NOT in the system prompt, so the system prefix stays byte-stable for
        # prompt caching (FR-015). Placed right before the node continuation so
        # the model still sees the time when it responds.
        now = datetime.now().astimezone()
        messages.append(
            {
                "role": "user",
                "content": (
                    f"<context>Current date/time: "
                    f"{now:%Y-%m-%d %H:%M:%S %z}, timezone: "
                    f"{now.tzname() or 'local'}</context>"
                ),
            }
        )

        node_continuation = self.build_continuation(session)
        if node_continuation.strip():
            messages.append({"role": "assistant", "content": node_continuation})

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
            response_tool_names = {
                tc.get("function", {}).get("name", "") for tc in response.tool_calls
            }
            for required in retry_policy.required_tool_calls:
                if required not in response_tool_names:
                    result.is_valid = False
                    result.errors.append(f"Missing required tool call: {required}")

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
                    if (
                        hasattr(custom_result, "is_valid")
                        and not custom_result.is_valid
                    ):
                        result.is_valid = False
                        if hasattr(custom_result, "errors"):
                            result.errors.extend(custom_result.errors)
            except (ValueError, TypeError, KeyError) as e:
                result.is_valid = False
                result.errors.append(f"Validation function error: {e}")

        return result

    def build_retry_continuation(self, error: ValidationError, attempt: int) -> str:
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

    def _safe_call(self, hook_method: Any, *args: Any, **kwargs: Any) -> str | None:
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

    def _record_failure(self, validation: ValidationResult, max_attempts: int) -> None:
        """Record retry exhaustion as internal diagnostics.

        Stores failure metadata on session diagnostics, not on
        ``session_context``. Retry exhaustion is debug/trace state and must
        not become reusable downstream LLM context.

        Args:
            validation: The validation result with error details.
            max_attempts: The maximum attempts that were allowed.
        """
        error_msg = "; ".join(validation.errors)
        diagnostic = {
            "type": "retry_exhausted",
            "node_id": self.node_id,
            "attempts": max_attempts,
            "errors": list(validation.errors),
            "message": (
                f"RETRY_EXHAUSTED node={self.node_id} "
                f"attempts={max_attempts} errors={error_msg}"
            ),
        }
        self._last_retry_exhaustion = diagnostic

        if self.session is not None:
            self.session.diagnostics.append(diagnostic)
            from tinycua.models.chat_record import ChatRecord

            self.session.chat_history.append(
                ChatRecord(
                    role="assistant",
                    record_type="retry",
                    content=diagnostic["message"],
                    visibility="internal",
                    source_node_id=self.node_id,
                    source_session_id=self.session.session_id,
                    created_seq=len(self.session.chat_history),
                    metadata=diagnostic,
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
        if self.session is not None and (
            self.is_terminal or not looks_like_planner_prose(response.content)
        ):
            from tinycua.models.session_context_entry import SessionContextEntry

            self.session.session_context.append(
                SessionContextEntry(
                    content=response.content,
                    segment="output",
                    source_node_id=self.node_id,
                    source_session_id=self.session.session_id,
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

    def on_complete(
        self, queue: NodeQueue, response: LLMResult | DecisionResult
    ) -> None:
        """Post-completion hook for queue mutations.

        Args:
            queue: The node queue that can be mutated.
            response: The final LLM response.
        """
        # Safely access .content which only exists on LLMResult
        content = (
            response.content
            if isinstance(response, LLMResult)
            else response.route_label
        )
        logger.debug(
            "node=%s on_complete response_len=%d",
            self.node_id,
            len(content),
        )

    @abstractmethod
    def __call__(self, input: NodeInputLike) -> Any:
        """Execute the node with the given input."""

    async def run(
        self,
        context: NodeRunContext,
        input: NodeInputLike,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Run this node through an injected runtime context."""
        return await context.sync_executor(self, input)

    async def stream(
        self,
        context: NodeRunContext,
        input: NodeInputLike,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream this node through an injected runtime context."""
        async for event in context.stream_executor(self, input):
            yield event


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
        max_attempts = (
            _UNBOUNDED_RETRY_ATTEMPTS
            if retry_policy.max_attempts is None
            else max(retry_policy.max_attempts, 1)
        )

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

    Classification matching uses RouteClassifier exact normalized labels,
    optional route JSON fields, and unambiguous punctuation trimming.

    Attributes:
        classification_labels: Allowed classification labels for routing.
    """

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = "",
        continuation: str = "",
        classification_labels: list[str] | None = None,
        is_terminal: bool = False,
    ) -> None:
        """Initialize the decision node.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration.
            instruction: Hardcoded instruction for this node.
            continuation: Hardcoded continuation for this node.
            classification_labels: Allowed classification labels.
            is_terminal: Whether this node is terminal.
        """
        super().__init__(
            node_id=node_id,
            config=config,
            instruction=instruction,
            continuation=continuation,
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
                "role": "assistant",
                "content": (
                    "Internal continuation: classify the prior analysis into "
                    f"one of these categories: {labels_str}. Respond with "
                    "only the category label."
                ),
            }
        )

        return self._call_llm(classification_messages)

    def _dispatch_route(self, classification_response: LLMResult) -> str:
        """Map classification label to a validated route.

        Args:
            classification_response: The classification LLM response.

        Returns:
            The matched route label.
        """
        classifier = RouteClassifier(self.classification_labels)
        return classifier.classify(classification_response.content)

    def _validate_classification(
        self, classification_response: LLMResult
    ) -> ValidationResult:
        """Validate that classification response matches an allowed label.

        Args:
            classification_response: The classification LLM response.

        Returns:
            ValidationResult with is_valid and errors.
        """
        classifier = RouteClassifier(self.classification_labels)
        if classifier.validate(classification_response.content):
            return ValidationResult(is_valid=True, errors=[])
        return ValidationResult(
            is_valid=False,
            errors=[
                f"Invalid classification: {classification_response.content!r} "
                f"not in {self.classification_labels}"
            ],
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
        max_attempts = (
            _UNBOUNDED_RETRY_ATTEMPTS
            if retry_policy.max_attempts is None
            else max(retry_policy.max_attempts, 1)
        )

        last_analysis: LLMResult | None = None
        last_classification: LLMResult | None = None
        route_label = ""

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
                route_label = ""

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
