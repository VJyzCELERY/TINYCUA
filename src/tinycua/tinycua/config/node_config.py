"""Node configuration dataclasses for TinyCUA nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from tinycua.config.types import StateObject, Tool


@dataclass
class NodeMessagePolicy:
    """Controls message selection and formatting for node LLM calls.

    Attributes:
        include_chat_history: Whether to include chat history in messages.
        include_session_context: Whether to include session context.
        max_context_messages: Maximum number of context messages (None = unlimited).
        dedupe_by_origin_record_id: Deduplicate messages by origin record ID.
        continuation_role: Role for internal node handoff messages.
    """

    include_chat_history: bool = False
    include_session_context: bool = True
    max_context_messages: int | None = None
    dedupe_by_origin_record_id: bool = True
    continuation_role: str = "assistant"


@dataclass
class NodeToolPolicy:
    """Controls tool scope resolution for node LLM calls.

    Resolution order:
    1. Start with node_tools.
    2. If include_agent_tools="none", include no outer tools.
    3. If "selected", include outer tools whose names are in allowed_agent_tool_names.
    4. If "all", include all outer tools except those in denied_agent_tool_names.
    5. Deny wins over allow when a tool name appears in both lists.

    Attributes:
        node_tools: Tools specific to this node.
        include_agent_tools: Policy for including outer agent tools.
        allowed_agent_tool_names: Tool names allowed when include_agent_tools="selected".
        denied_agent_tool_names: Tool names denied (deny wins over allow).
    """

    node_tools: list[Tool] = field(default_factory=list)
    include_agent_tools: Literal["none", "selected", "all"] = "none"
    allowed_agent_tool_names: list[str] = field(default_factory=list)
    denied_agent_tool_names: list[str] = field(default_factory=list)

    def resolve_tools(
        self,
        outer_agent_tools: list[Tool] | None = None,
    ) -> list[Tool]:
        """Resolve allowed tools according to policy.

        Args:
            outer_agent_tools: Tools from the outer agent to filter.

        Returns:
            List of resolved tools.
        """
        if outer_agent_tools is None:
            outer_agent_tools = []

        result = list(self.node_tools)

        if self.include_agent_tools == "none":
            return result

        # Build deny set for O(1) lookup
        deny_set = set(self.denied_agent_tool_names)

        if self.include_agent_tools == "selected":
            # Include only allowed outer tools
            allow_set = set(self.allowed_agent_tool_names)
            for tool in outer_agent_tools:
                if tool.name in allow_set and tool.name not in deny_set:
                    result.append(tool)
        elif self.include_agent_tools == "all":
            # Include all outer tools except denied
            for tool in outer_agent_tools:
                if tool.name not in deny_set:
                    result.append(tool)

        return result


@dataclass
class NodeStreamPolicy:
    """Controls streaming behavior for node LLM calls.

    Attributes:
        visible_to_user: Whether stream is visible to user.
        emit_internal_events: Whether to emit internal events.
        include_node_metadata: Whether to include node metadata in stream.
        final_response_only: Whether to stream only the final response.
    """

    visible_to_user: bool = True
    emit_internal_events: bool = True
    include_node_metadata: bool = True
    final_response_only: bool = False


@dataclass
class NodeRetryPolicy:
    """Controls retry behavior, validation, and exhaustion handling.

    Attributes:
        max_attempts: Maximum number of attempts (0 = no retries).
        required_tool_calls: Tool calls required for validation.
        required_output_schema: Schema or type for output validation.
        validation_fn: Custom validation function.
        retry_continuation_builder: Builder for retry continuation messages.
        on_retry_exhausted: Behavior when retries exhausted.
    """

    max_attempts: int = 3
    required_tool_calls: list[str] = field(default_factory=list)
    required_output_schema: dict | type[StateObject] | None = None
    validation_fn: Any | None = None  # Callable[[LLMResult], ValidationResult]
    retry_continuation_builder: Any | None = None  # Callable[[ValidationError, int], str]
    on_retry_exhausted: Literal["raise", "record_failure", "route_failure"] = "record_failure"

    def __post_init__(self) -> None:
        """Validate max_attempts is non-negative."""
        if self.max_attempts < 0:
            raise ValueError("max_attempts must be >= 0")


@dataclass
class NodeConfigBase:
    """Base configuration for all TinyCUA nodes.

    Provides append-only customization fields and policy objects.

    Attributes:
        custom_instruction_append: Custom text appended to system instruction.
        custom_continuation_append: Custom text appended to continuation.
        custom_retry_append: Custom text appended to retry messages.
        propagation: Propagation rule (placeholder for future implementation).
        tool_policy: Tool scope resolution policy.
        stream_policy: Streaming behavior policy.
        retry_policy: Retry behavior policy.
        message_policy: Message selection policy.
        metadata: Arbitrary metadata.
    """

    custom_instruction_append: str | None = None
    custom_continuation_append: str | None = None
    custom_retry_append: str | None = None
    propagation: Any = None  # PropagationRule placeholder
    tool_policy: NodeToolPolicy = field(default_factory=NodeToolPolicy)
    stream_policy: NodeStreamPolicy = field(default_factory=NodeStreamPolicy)
    retry_policy: NodeRetryPolicy = field(default_factory=NodeRetryPolicy)
    message_policy: NodeMessagePolicy = field(default_factory=NodeMessagePolicy)
    metadata: dict[str, Any] = field(default_factory=dict)
