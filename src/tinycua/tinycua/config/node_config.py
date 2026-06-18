"""Node configuration dataclasses for TinyCUA nodes."""

from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass, replace
from typing import TYPE_CHECKING, Any, Callable, Literal

from tinycua.config.types import StateObject, Tool

if TYPE_CHECKING:
    from tinycua.config.types import NodeMonitor
    from tinycua.loops.propagation import PropagationRule


@dataclass
class NodeMessagePolicy:
    """Controls message selection and formatting for node LLM calls.

    Attributes:
        include_chat_history: Whether to include chat history in messages.
        include_session_context: Whether to include session context.
        include_input_context: Whether to include SDK/root input context.
        max_context_messages: Maximum number of context messages (None = unlimited).
        dedupe_by_origin_record_id: Deduplicate messages by origin record ID.
        continuation_role: Role for internal node handoff messages.
    """

    include_chat_history: bool = False
    include_session_context: bool = True
    include_input_context: bool = False
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

    def __post_init__(self) -> None:
        """Validate include_agent_tools value."""
        valid_values = {"none", "selected", "all"}
        if self.include_agent_tools not in valid_values:
            raise ValueError(
                f"Invalid include_agent_tools value: {self.include_agent_tools!r}. "
                f"Must be one of {valid_values}"
            )

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

        # Build deny set and existing names for O(1) lookup and dedup
        deny_set = set(self.denied_agent_tool_names)
        node_tool_names = {t.name for t in self.node_tools}

        if self.include_agent_tools == "selected":
            # Include only allowed outer tools
            allow_set = set(self.allowed_agent_tool_names)
            for tool in outer_agent_tools:
                if (
                    tool.name in allow_set
                    and tool.name not in deny_set
                    and tool.name not in node_tool_names
                ):
                    result.append(tool)
        elif self.include_agent_tools == "all":
            # Include all outer tools except denied and duplicates
            for tool in outer_agent_tools:
                if tool.name not in deny_set and tool.name not in node_tool_names:
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
        max_attempts: Maximum number of attempts (0 = no retries, None = unbounded).
        required_tool_calls: Tool calls required for validation.
        required_output_schema: Schema or type for output validation.
        validation_fn: Custom validation function.
        retry_continuation_builder: Builder for retry continuation messages.
        on_retry_exhausted: Behavior when retries exhausted.
    """

    max_attempts: int | None = 3
    required_tool_calls: list[str] = field(default_factory=list)
    required_output_schema: dict | type[StateObject] | None = None
    validation_fn: Any | None = None  # Callable[[LLMResult], ValidationResult]
    retry_continuation_builder: Any | None = (
        None  # Callable[[ValidationError, int], str]
    )
    on_retry_exhausted: Literal["raise", "record_failure", "route_failure"] = (
        "record_failure"
    )

    def __post_init__(self) -> None:
        """Validate max_attempts is non-negative."""
        if self.max_attempts is not None and self.max_attempts < 0:
            raise ValueError("max_attempts must be >= 0")


@dataclass
class NodeConfigBase:
    """Base configuration for all TinyCUA nodes.

    Provides append-only customization fields and policy objects.

    Attributes:
        custom_instruction_append: Custom text appended to system instruction.
        custom_continuation_append: Custom text appended to continuation.
        custom_retry_append: Custom text appended to retry messages.
        propagation: Propagation rule for session/root context transfer.
        tool_policy: Tool scope resolution policy.
        stream_policy: Streaming behavior policy.
        retry_policy: Retry behavior policy.
        message_policy: Message selection policy.
        metadata: Arbitrary metadata.
        llm_client: LLM client callable for node LLM invocations.
        monitor: Optional monitor hook for observing node execution.
    """

    custom_instruction_append: str | None = None
    custom_continuation_append: str | None = None
    custom_retry_append: str | None = None
    propagation: PropagationRule | None = None
    tool_policy: NodeToolPolicy = field(default_factory=NodeToolPolicy)
    stream_policy: NodeStreamPolicy = field(default_factory=NodeStreamPolicy)
    retry_policy: NodeRetryPolicy = field(default_factory=NodeRetryPolicy)
    message_policy: NodeMessagePolicy = field(default_factory=NodeMessagePolicy)
    metadata: dict[str, Any] = field(default_factory=dict)
    llm_client: Callable | None = None
    monitor: NodeMonitor | None = None


def create_node_config(
    node_kind: str,
    base_config: NodeConfigBase | None = None,
    *,
    mode: str | None = None,
) -> NodeConfigBase:
    """Create a node config with the correct least-privilege tool scope.

    Args:
        node_kind: Logical node kind such as ``query_analyst`` or ``worker``.
        base_config: Optional config whose non-tool policies are preserved.
        mode: Optional mode used by mode-dependent nodes.

    Returns:
        NodeConfigBase with node-specific ``tool_policy``.
    """
    from tinycua.config import tool_scopes

    normalized = node_kind.lower().replace("-", "_")
    policy_factories = {
        "query_analyst": tool_scopes.query_analyst_tool_scope,
        "digester": tool_scopes.information_digester_tool_scope,
        "information_digester": tool_scopes.information_digester_tool_scope,
        "worker": tool_scopes.worker_tool_scope,
        "task_create": tool_scopes.task_create_tool_scope,
        "task_creation": tool_scopes.task_create_tool_scope,
        "task_assessor": tool_scopes.task_assessor_tool_scope,
        "task_executor": tool_scopes.task_executor_tool_scope,
        "result_reviewer": tool_scopes.result_reviewer_tool_scope,
        "result_aggregation": tool_scopes.result_aggregation_tool_scope,
        "analysis_effort": tool_scopes.deterministic_controller_tool_scope,
        "response": tool_scopes.response_tool_scope,
    }

    config = base_config if is_dataclass(base_config) else NodeConfigBase()
    if normalized == "task_analyzer":
        tool_policy = tool_scopes.task_analyzer_tool_scope(mode or "task_creation")
    else:
        factory = policy_factories.get(normalized)
        tool_policy = factory() if factory is not None else config.tool_policy
    retry_policy = config.retry_policy
    if normalized == "query_analyst":
        retry_policy = replace(
            retry_policy,
            required_tool_calls=["select_query_route"],
        )
    elif normalized == "worker":
        retry_policy = replace(
            retry_policy,
            required_tool_calls=["select_worker_route"],
        )
    else:
        retry_policy = replace(retry_policy, required_tool_calls=[])
    metadata = dict(config.metadata)
    metadata["node_kind"] = normalized
    if normalized == "task_assessor":
        metadata["task_assessor_mode"] = mode or metadata.get(
            "task_assessor_mode",
            "upfront_decomposition",
        )
    if normalized == "task_analyzer":
        metadata["task_analyzer_mode"] = mode or metadata.get(
            "task_analyzer_mode",
            "task_creation",
        )
    if normalized in {"task_executor", "result_reviewer"}:
        retry_policy = replace(retry_policy, max_attempts=25)
    retry_guidance = {
        "digester": (
            "If prior context is available, consider using "
            "enhanced_context_retrieval to inspect it before calling "
            "digest_information. Do not force retrieval when the provided "
            "context is already sufficient."
        ),
        "information_digester": (
            "If prior context is available, consider using "
            "enhanced_context_retrieval to inspect it before calling "
            "digest_information. Do not force retrieval when the provided "
            "context is already sufficient."
        ),
        "query_analyst": (
            "Use select_query_route with exactly one route. Do not answer with "
            "the route in text only."
        ),
        "worker": (
            "Use select_worker_route with exactly one currently allowed route. "
            "Do not answer with the route in text only."
        ),
        "task_create": (
            "Call task_init with a root title derived from the actual request. "
            "Do not describe task creation only in prose."
        ),
        "task_analyzer": (
            "Use task_inspect plus task_decompose or task_update when task "
            "analysis changes or confirms the task tree."
        ),
        "task_assessor": (
            "Use task_inspect for read-only assessment and node_handoff to "
            "instruct TaskAnalyzer instead of mutating task state."
        ),
        "task_executor": (
            "Use action/research tools as needed and then call "
            "task_result_update with the observed result."
        ),
        "result_reviewer": (
            "Call task_review_decision with approved, needs_revision, "
            "rejected, or replan."
        ),
    }.get(normalized)
    custom_retry_append = config.custom_retry_append
    if retry_guidance:
        custom_retry_append = " ".join(
            part for part in (custom_retry_append, retry_guidance) if part
        )
    message_policy = replace(
        config.message_policy,
        include_chat_history=False,
        include_session_context=normalized
        not in {"task_executor", "result_reviewer"},
        include_input_context=normalized == "query_analyst",
    )
    return replace(
        config,
        tool_policy=tool_policy,
        retry_policy=retry_policy,
        message_policy=message_policy,
        metadata=metadata,
        custom_retry_append=custom_retry_append,
    )
