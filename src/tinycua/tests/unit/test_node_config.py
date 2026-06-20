"""Unit tests for node configuration dataclasses."""

import pytest

from tinycua.config.node_config import (
    NodeConfigBase,
    NodeMessagePolicy,
    NodeRetryPolicy,
    NodeStreamPolicy,
    NodeToolPolicy,
)
from tinycua.config.types import Tool


class TestNodeMessagePolicy:
    """Tests for NodeMessagePolicy dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        policy = NodeMessagePolicy()
        assert policy.include_chat_history is False
        assert policy.include_session_context is True
        assert policy.max_context_messages is None
        assert policy.dedupe_by_origin_record_id is True
        assert policy.continuation_role == "user"

    def test_custom_values(self) -> None:
        """Test custom values."""
        policy = NodeMessagePolicy(
            include_chat_history=True,
            include_session_context=False,
            max_context_messages=50,
            dedupe_by_origin_record_id=False,
            continuation_role="user",
        )
        assert policy.include_chat_history is True
        assert policy.include_session_context is False
        assert policy.max_context_messages == 50
        assert policy.dedupe_by_origin_record_id is False
        assert policy.continuation_role == "user"


class TestNodeToolPolicy:
    """Tests for NodeToolPolicy dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        policy = NodeToolPolicy()
        assert policy.node_tools == []
        assert policy.include_agent_tools == "none"
        assert policy.allowed_agent_tool_names == []
        assert policy.denied_agent_tool_names == []

    def test_resolve_tools_no_outer(self) -> None:
        """Test tool resolution with no outer tools."""
        policy = NodeToolPolicy(
            node_tools=[Tool(name="node_tool")],
            include_agent_tools="all",
        )
        result = policy.resolve_tools()
        assert len(result) == 1
        assert result[0].name == "node_tool"

    def test_resolve_tools_none_includes(self) -> None:
        """Test tool resolution with include_agent_tools='none'."""
        policy = NodeToolPolicy(
            include_agent_tools="none",
        )
        outer = [Tool(name="web_search")]
        result = policy.resolve_tools(outer_agent_tools=outer)
        assert len(result) == 0

    def test_resolve_tools_selected(self) -> None:
        """Test tool resolution with include_agent_tools='selected'."""
        policy = NodeToolPolicy(
            include_agent_tools="selected",
            allowed_agent_tool_names=["web_search", "calculator"],
        )
        outer = [
            Tool(name="web_search"),
            Tool(name="calculator"),
            Tool(name="other"),
        ]
        result = policy.resolve_tools(outer_agent_tools=outer)
        names = [t.name for t in result]
        assert "web_search" in names
        assert "calculator" in names
        assert "other" not in names

    def test_resolve_tools_all(self) -> None:
        """Test tool resolution with include_agent_tools='all'."""
        policy = NodeToolPolicy(
            include_agent_tools="all",
        )
        outer = [
            Tool(name="web_search"),
            Tool(name="calculator"),
            Tool(name="other"),
        ]
        result = policy.resolve_tools(outer_agent_tools=outer)
        names = [t.name for t in result]
        assert len(names) == 3

    def test_resolve_tools_deny_wins(self) -> None:
        """Test that deny wins over allow."""
        policy = NodeToolPolicy(
            include_agent_tools="selected",
            allowed_agent_tool_names=["web_search", "calculator"],
            denied_agent_tool_names=["web_search"],
        )
        outer = [
            Tool(name="web_search"),
            Tool(name="calculator"),
        ]
        result = policy.resolve_tools(outer_agent_tools=outer)
        names = [t.name for t in result]
        assert "web_search" not in names
        assert "calculator" in names

    def test_resolve_tools_deny_wins_over_all(self) -> None:
        """Test that deny wins over include_agent_tools='all'."""
        policy = NodeToolPolicy(
            include_agent_tools="all",
            denied_agent_tool_names=["web_search"],
        )
        outer = [
            Tool(name="web_search"),
            Tool(name="calculator"),
        ]
        result = policy.resolve_tools(outer_agent_tools=outer)
        names = [t.name for t in result]
        assert "web_search" not in names
        assert "calculator" in names

    def test_resolve_tools_node_tools_included(self) -> None:
        """Test that node tools are always included."""
        policy = NodeToolPolicy(
            node_tools=[Tool(name="node_tool")],
            include_agent_tools="none",
        )
        outer = [Tool(name="web_search")]
        result = policy.resolve_tools(outer_agent_tools=outer)
        names = [t.name for t in result]
        assert "node_tool" in names
        assert "web_search" not in names


class TestNodeStreamPolicy:
    """Tests for NodeStreamPolicy dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        policy = NodeStreamPolicy()
        assert policy.visible_to_user is True
        assert policy.emit_internal_events is True
        assert policy.include_node_metadata is True
        assert policy.final_response_only is False

    def test_custom_values(self) -> None:
        """Test custom values."""
        policy = NodeStreamPolicy(
            visible_to_user=False,
            emit_internal_events=False,
            include_node_metadata=False,
            final_response_only=True,
        )
        assert policy.visible_to_user is False
        assert policy.emit_internal_events is False
        assert policy.include_node_metadata is False
        assert policy.final_response_only is True


class TestNodeRetryPolicy:
    """Tests for NodeRetryPolicy dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        policy = NodeRetryPolicy()
        assert policy.max_attempts == 3
        assert policy.required_tool_calls == []
        assert policy.required_output_schema is None
        assert policy.validation_fn is None
        assert policy.retry_continuation_builder is None
        assert policy.on_retry_exhausted == "record_failure"

    def test_custom_values(self) -> None:
        """Test custom values."""
        policy = NodeRetryPolicy(
            max_attempts=5,
            required_tool_calls=["tool1", "tool2"],
            on_retry_exhausted="raise",
        )
        assert policy.max_attempts == 5
        assert policy.required_tool_calls == ["tool1", "tool2"]
        assert policy.on_retry_exhausted == "raise"

    def test_max_attempts_zero(self) -> None:
        """Test max_attempts=0 (no retries)."""
        policy = NodeRetryPolicy(max_attempts=0)
        assert policy.max_attempts == 0

    def test_max_attempts_negative_raises(self) -> None:
        """Test max_attempts < 0 raises ValueError."""
        with pytest.raises(ValueError, match="max_attempts must be >= 0"):
            NodeRetryPolicy(max_attempts=-1)


class TestNodeConfigBase:
    """Tests for NodeConfigBase dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        config = NodeConfigBase()
        assert config.custom_instruction_append is None
        assert config.custom_continuation_append is None
        assert config.custom_retry_append is None
        assert config.propagation is None
        assert isinstance(config.tool_policy, NodeToolPolicy)
        assert isinstance(config.stream_policy, NodeStreamPolicy)
        assert isinstance(config.retry_policy, NodeRetryPolicy)
        assert isinstance(config.message_policy, NodeMessagePolicy)
        assert config.metadata == {}

    def test_custom_policies(self) -> None:
        """Test custom policies."""
        config = NodeConfigBase(
            tool_policy=NodeToolPolicy(include_agent_tools="selected"),
            stream_policy=NodeStreamPolicy(visible_to_user=False),
            retry_policy=NodeRetryPolicy(max_attempts=5),
            message_policy=NodeMessagePolicy(include_chat_history=True),
        )
        assert config.tool_policy.include_agent_tools == "selected"
        assert config.stream_policy.visible_to_user is False
        assert config.retry_policy.max_attempts == 5
        assert config.message_policy.include_chat_history is True

    def test_append_only_customization(self) -> None:
        """Test append-only customization fields."""
        config = NodeConfigBase(
            custom_instruction_append="Custom instruction",
            custom_continuation_append="Custom continuation",
            custom_retry_append="Custom retry",
        )
        assert config.custom_instruction_append == "Custom instruction"
        assert config.custom_continuation_append == "Custom continuation"
        assert config.custom_retry_append == "Custom retry"
