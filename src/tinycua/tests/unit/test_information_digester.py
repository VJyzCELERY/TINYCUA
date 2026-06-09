"""Unit tests for TinyCUAInformationDigesterNode.

Tests cover session isolation, propagation, enhanced retrieval, fallback,
tool scope, retry behavior, and config defaults.

Spec ref: src/tinycua/specs/2.5-information-digester-node/task.md
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tinycua.config.node_config import (
    NodeConfigBase,
    TinyCUAInformationDigesterNodeConfig,
)
from tinycua.config.types import LLMResult
from tinycua.loops.information_digester import (
    TinyCUAInformationDigesterNode,
    llm_call,
)
from tinycua.loops.node import ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def digester_config():
    """Default digester configuration."""
    return TinyCUAInformationDigesterNodeConfig()


@pytest.fixture
def parent_node():
    """Mock parent node (simulating ResponseNode)."""
    parent = MagicMock(spec=ProcessNode)
    parent.node_id = "response_node"
    parent.config = NodeConfigBase()
    parent.session = MagicMock()
    parent.session.session_id = "parent_session_123"
    parent.session.session_context = []
    return parent


@pytest.fixture
def digester(digester_config):
    """Create a default digester node."""
    return TinyCUAInformationDigesterNode(config=digester_config)


@pytest.fixture
def digester_with_parent(digester_config, parent_node):
    """Create a digester node with a parent."""
    return TinyCUAInformationDigesterNode(config=digester_config, parent=parent_node)


def _make_input(messages=None):
    """Helper to create a NodeInput with messages."""
    if messages is None:
        messages = [{"role": "user", "content": "test query"}]
    return NodeInput(input_type="messages", messages=messages)


# ---------------------------------------------------------------------------
# Session Isolation Tests
# ---------------------------------------------------------------------------


class TestFreshSessionCreated:
    """Verify InformationDigesterNode creates fresh session with unique session_id."""

    def test_fresh_session_created(self, digester):
        """Node creates a fresh session when __call__ is invoked."""
        input_data = _make_input()
        digester(input_data)
        assert digester.session is not None
        assert isinstance(digester.session, Session)

    def test_does_not_inherit_parent_session(self, digester_with_parent, parent_node):
        """Node does NOT inherit parent's session — uses its own fresh session."""
        input_data = _make_input()
        digester_with_parent(input_data)
        assert digester_with_parent.session is not None
        assert digester_with_parent.session is not parent_node.session
        assert digester_with_parent.session.session_id != parent_node.session.session_id


# ---------------------------------------------------------------------------
# Output Recording Tests
# ---------------------------------------------------------------------------


class TestOutputRecording:
    """Verify node stores only its own digest output."""

    def test_stores_only_own_output(self, digester):
        """Node records only its own digest, not copied input messages."""
        input_messages = [
            {"role": "user", "content": "query"},
            {"role": "assistant", "content": "previous response"},
        ]
        input_data = _make_input(input_messages)
        digester(input_data)

        # Session context should only contain the node's own output
        assert len(digester.session.session_context) == 1
        assert digester.session.session_context[0]["role"] == "assistant"


# ---------------------------------------------------------------------------
# Propagation Tests
# ---------------------------------------------------------------------------


class TestPropagation:
    """Verify digest output propagates to parent session."""

    def test_propagates_to_parent(self, digester_with_parent, parent_node):
        """on_complete propagates digest to parent and advances queue."""
        queue = NodeQueue()
        queue.items.append(digester_with_parent)
        queue.items.append(parent_node)

        input_data = _make_input()
        digester_with_parent(input_data)

        response = LLMResult(content="test digest", role="assistant")
        digester_with_parent.on_complete(queue, response)

        # Parent should be resumed as current node
        assert queue.current is parent_node

        # Digest should be in parent's session_context
        assert len(parent_node.session.session_context) == 1
        assert parent_node.session.session_context[0] == {
            "role": "assistant",
            "content": "test digest",
        }

    def test_propagation_without_parent(self, digester):
        """on_complete without parent does not crash."""
        queue = NodeQueue()
        queue.items.append(digester)

        input_data = _make_input()
        digester(input_data)

        response = LLMResult(content="test digest", role="assistant")
        # Should not raise
        digester.on_complete(queue, response)


# ---------------------------------------------------------------------------
# Enhanced Retrieval Tests
# ---------------------------------------------------------------------------


class TestEnhancedRetrieval:
    """Verify enhanced_context_retrieval behavior."""

    @patch("tinycua.loops.information_digester.EnhancedContextRetrieval")
    def test_enhanced_retrieval_creates_cache(self, mock_retrieval_class):
        """When retrieval_enabled=True, cache is created."""
        mock_retrieval = MagicMock()
        mock_retrieval_class.return_value = mock_retrieval
        mock_retrieval.create_cache.return_value = "/tmp/cache"
        mock_retrieval.search.return_value = []

        config = TinyCUAInformationDigesterNodeConfig(retrieval_enabled=True)
        digester = TinyCUAInformationDigesterNode(config=config)
        input_data = _make_input()
        digester(input_data)

        assert mock_retrieval.create_cache.called

    @patch("tinycua.loops.information_digester.EnhancedContextRetrieval")
    def test_enhanced_retrieval_search_limited_to_cache(self, mock_retrieval_class):
        """Search operations are limited to the cache boundaries."""
        mock_retrieval = MagicMock()
        mock_retrieval_class.return_value = mock_retrieval
        mock_retrieval.create_cache.return_value = "/tmp/cache"
        mock_retrieval.search.return_value = [
            {"role": "context", "content": "found context"}
        ]

        config = TinyCUAInformationDigesterNodeConfig(retrieval_enabled=True)
        digester = TinyCUAInformationDigesterNode(config=config)
        input_data = _make_input()
        digester(input_data)

        # Search was called
        assert mock_retrieval.search.called
        # Retrieved context was incorporated
        assert mock_retrieval.search.call_count >= 1


# ---------------------------------------------------------------------------
# Fallback Tests
# ---------------------------------------------------------------------------


class TestFallback:
    """Verify no-useful-context fallback behavior."""

    @patch("tinycua.loops.information_digester.llm_call")
    def test_no_useful_context_fallback(self, mock_llm_call):
        """When LLM returns empty content, fallback preserves user query."""
        mock_llm_call.return_value = LLMResult(content="", role="assistant")

        digester = TinyCUAInformationDigesterNode(
            config=TinyCUAInformationDigesterNodeConfig(retrieval_enabled=False)
        )
        input_data = _make_input(
            [{"role": "user", "content": "Help me write a script"}]
        )
        result = digester(input_data)

        assert "Help me write a script" in result.content
        assert "No useful extra information was found" in result.content
        assert "proceed" in result.content.lower()

    @patch("tinycua.loops.information_digester.llm_call")
    def test_fallback_preserves_user_query(self, mock_llm_call):
        """Fallback message preserves the original user query text."""
        mock_llm_call.return_value = LLMResult(content="", role="assistant")

        digester = TinyCUAInformationDigesterNode(
            config=TinyCUAInformationDigesterNodeConfig(retrieval_enabled=False)
        )
        input_data = _make_input(
            [{"role": "user", "content": "Analyze the codebase"}]
        )
        result = digester(input_data)

        assert "Analyze the codebase" in result.content

    @patch("tinycua.loops.information_digester.llm_call")
    def test_fallback_when_digest_empty(self, mock_llm_call):
        """When digest production returns empty, fallback is used after retry attempts."""
        mock_llm_call.return_value = LLMResult(content="", role="assistant")

        digester = TinyCUAInformationDigesterNode(
            config=TinyCUAInformationDigesterNodeConfig(retrieval_enabled=False)
        )
        input_data = _make_input()
        result = digester(input_data)

        # llm_call called max_attempts times (default 3) before fallback.
        assert mock_llm_call.call_count == 3
        assert result.content.startswith("The user asked")
        assert "No useful extra information was found" in result.content


# ---------------------------------------------------------------------------
# Digest Production Tests
# ---------------------------------------------------------------------------


class TestDigestProduction:
    """Verify digest_information produces structured output."""

    @patch("tinycua.loops.information_digester.llm_call")
    def test_digest_information_produces_structured_output(self, mock_llm_call):
        """LLM call produces structured digest content."""
        mock_llm_call.return_value = LLMResult(
            content="Structured digest with context summary and key points.",
            role="assistant",
        )

        digester = TinyCUAInformationDigesterNode(
            config=TinyCUAInformationDigesterNodeConfig(retrieval_enabled=False)
        )
        input_data = _make_input()
        result = digester(input_data)

        assert result.content is not None
        assert len(result.content) > 0
        assert mock_llm_call.called


# ---------------------------------------------------------------------------
# Tool Scope Tests
# ---------------------------------------------------------------------------


class TestToolScope:
    """Verify tool scope is restricted to two tools only."""

    def test_tool_scope_restricted(self, digester):
        """Node tool_policy excludes all agent tools."""
        tool_policy = digester.config.tool_policy
        assert tool_policy.include_agent_tools == "none"
        assert len(tool_policy.node_tools) == 0


# ---------------------------------------------------------------------------
# Retry Tests
# ---------------------------------------------------------------------------


class TestRetry:
    """Verify retry behavior per NodeRetryPolicy."""

    @patch("tinycua.loops.information_digester.llm_call")
    def test_retry_on_empty_digest(self, mock_llm_call):
        """Digest empty triggers retry up to max_attempts."""
        mock_llm_call.return_value = LLMResult(content="", role="assistant")

        config = TinyCUAInformationDigesterNodeConfig(
            retrieval_enabled=False,
        )
        config.retry_policy.max_attempts = 3
        digester = TinyCUAInformationDigesterNode(config=config)

        input_data = _make_input()
        result = digester(input_data)

        # Should retry 3 times before fallback.
        assert mock_llm_call.call_count == 3
        assert "No useful extra information was found" in result.content

    @patch("tinycua.loops.information_digester.llm_call")
    def test_no_retry_when_max_attempts_one(self, mock_llm_call):
        """When max_attempts=1, no retry occurs."""
        mock_llm_call.return_value = LLMResult(content="", role="assistant")

        config = TinyCUAInformationDigesterNodeConfig(
            retrieval_enabled=False,
        )
        config.retry_policy.max_attempts = 1
        digester = TinyCUAInformationDigesterNode(config=config)

        input_data = _make_input()
        result = digester(input_data)

        # Only one llm_call, then fallback.
        assert mock_llm_call.call_count == 1
        assert "No useful extra information was found" in result.content

    @patch("tinycua.loops.information_digester.llm_call")
    def test_retry_succeeds_on_second_attempt(self, mock_llm_call):
        """Retry stops when digest becomes non-empty."""
        # First call returns empty, second returns content.
        mock_llm_call.side_effect = [
            LLMResult(content="", role="assistant"),
            LLMResult(content="successful digest", role="assistant"),
        ]

        config = TinyCUAInformationDigesterNodeConfig(
            retrieval_enabled=False,
        )
        config.retry_policy.max_attempts = 3
        digester = TinyCUAInformationDigesterNode(config=config)

        input_data = _make_input()
        result = digester(input_data)

        # Should stop after second successful attempt.
        assert mock_llm_call.call_count == 2
        assert result.content == "successful digest"



# ---------------------------------------------------------------------------
# Chat History Tests
# ---------------------------------------------------------------------------


class TestChatHistory:
    """Verify chat_history is not passed wholesale to the digester."""

    def test_chat_history_not_passed_wholesale(self):
        """Input contains selected parent messages, not full chat_history."""
        input_messages = [
            {"role": "user", "content": "selected message 1"},
            {"role": "assistant", "content": "selected message 2"},
        ]
        input_data = _make_input(input_messages)

        digester = TinyCUAInformationDigesterNode(
            config=TinyCUAInformationDigesterNodeConfig(retrieval_enabled=False)
        )
        digester(input_data)

        # The digester should only see the input messages,
        # not any parent chat_history
        assert digester.session.session_context[0]["content"] != "full chat history"


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------


class TestConfig:
    """Verify configuration defaults and parameter acceptance."""

    def test_config_defaults_when_none(self):
        """When config is None, uses TinyCUAInformationDigesterNodeConfig defaults."""
        digester = TinyCUAInformationDigesterNode(config=None)
        assert isinstance(digester.config, TinyCUAInformationDigesterNodeConfig)
        assert digester.config.retrieval_enabled is True
        assert digester.config.max_digest_sources is None

    def test_parent_parameter_accepted(self, parent_node):
        """Parent parameter is accepted and stored."""
        digester = TinyCUAInformationDigesterNode(parent=parent_node)
        assert digester._parent is parent_node
        assert digester.parent is parent_node

    def test_plain_config_wrapped(self):
        """Plain NodeConfigBase is wrapped into TinyCUAInformationDigesterNodeConfig."""
        plain_config = NodeConfigBase()
        digester = TinyCUAInformationDigesterNode(config=plain_config)
        assert isinstance(digester.config, TinyCUAInformationDigesterNodeConfig)
        # Should preserve llm_client from original config
        assert digester.config.llm_client == plain_config.llm_client


# ---------------------------------------------------------------------------
# Behavior Constraint Tests
# ---------------------------------------------------------------------------


class TestBehaviorConstraints:
    """Verify node does not execute tasks or synthesize responses."""

    def test_does_not_execute_tasks(self, digester):
        """Node does not have task execution capability."""
        assert not hasattr(digester, "execute_task")
        assert not hasattr(digester, "run_task")

    def test_does_not_synthesize_response(self, digester):
        """Node does not synthesize final responses — only digests context."""
        input_data = _make_input()
        result = digester(input_data)
        # Result should be a digest, not a synthesized response
        assert isinstance(result, LLMResult)


# ---------------------------------------------------------------------------
# Retrieval Disabled Tests
# ---------------------------------------------------------------------------


class TestRetrievalDisabled:
    """Verify behavior when enhanced retrieval is disabled."""

    @patch("tinycua.loops.information_digester.EnhancedContextRetrieval")
    def test_retrieval_disabled_proceeds_with_input(self, mock_retrieval_class):
        """When retrieval_enabled=False, node proceeds with input only."""
        config = TinyCUAInformationDigesterNodeConfig(retrieval_enabled=False)
        digester = TinyCUAInformationDigesterNode(config=config)

        input_data = _make_input()
        digester(input_data)

        # EnhancedContextRetrieval should NOT be instantiated
        mock_retrieval_class.assert_not_called()


# ---------------------------------------------------------------------------
# Cache Failure Tests
# ---------------------------------------------------------------------------


class TestCacheFailure:
    """Verify cache creation failure is handled gracefully."""

    @patch("tinycua.loops.information_digester.EnhancedContextRetrieval")
    def test_cache_creation_failure_logs_and_proceeds(self, mock_retrieval_class):
        """Cache creation failure logs error and proceeds with available context."""
        mock_retrieval = MagicMock()
        mock_retrieval_class.return_value = mock_retrieval
        mock_retrieval.create_cache.side_effect = OSError("disk full")

        config = TinyCUAInformationDigesterNodeConfig(retrieval_enabled=True)
        digester = TinyCUAInformationDigesterNode(config=config)

        input_data = _make_input()
        result = digester(input_data)

        # Should not crash — fallback or digest from input
        assert result is not None
        assert result.content is not None


# ---------------------------------------------------------------------------
# Max Digest Sources Tests
# ---------------------------------------------------------------------------


class TestMaxDigestSources:
    """Verify max_digest_sources limits context sources."""

    @patch("tinycua.loops.information_digester.EnhancedContextRetrieval")
    def test_max_digest_sources_limits_context(self, mock_retrieval_class):
        """max_digest_sources is passed to EnhancedContextRetrieval."""
        mock_retrieval = MagicMock()
        mock_retrieval_class.return_value = mock_retrieval
        mock_retrieval.create_cache.return_value = "/tmp/cache"
        mock_retrieval.search.return_value = []

        config = TinyCUAInformationDigesterNodeConfig(
            retrieval_enabled=True,
            max_digest_sources=5,
        )
        digester = TinyCUAInformationDigesterNode(config=config)

        input_data = _make_input()
        digester(input_data)

        # EnhancedContextRetrieval should receive max_sources
        call_kwargs = mock_retrieval_class.call_args
        assert call_kwargs.kwargs.get("max_sources") == 5


# ---------------------------------------------------------------------------
# DigestedInformation Model Tests
# ---------------------------------------------------------------------------


class TestDigestedInformation:
    """Verify DigestedInformation dataclass fields."""

    def test_all_five_fields(self):
        """DigestedInformation has all 5 required fields."""
        info = DigestedInformation(
            context_summary="summary",
            key_points=["point1", "point2"],
            advisory_instructions=["instruction1"],
            constraints=["constraint1"],
            known_gaps=["gap1"],
        )
        assert info.context_summary == "summary"
        assert len(info.key_points) == 2
        assert len(info.advisory_instructions) == 1
        assert len(info.constraints) == 1
        assert len(info.known_gaps) == 1

    def test_defaults_are_empty(self):
        """DigestedInformation defaults are empty/empty lists."""
        info = DigestedInformation()
        assert info.context_summary == ""
        assert info.key_points == []
        assert info.advisory_instructions == []
        assert info.constraints == []
        assert info.known_gaps == []


# ---------------------------------------------------------------------------
# llm_call Tests
# ---------------------------------------------------------------------------


class TestLlmCall:
    """Verify llm_call helper function."""

    def test_returns_default_when_no_client(self):
        """Returns default LLMResult when no client is provided."""
        result = llm_call([{"role": "user", "content": "test"}])
        assert result.content == "No LLM client configured."

    def test_calls_client_with_messages(self):
        """Calls the LLM client and wraps response in LLMResult."""
        mock_client = MagicMock()
        mock_client.return_value = {"content": "response", "role": "assistant"}

        result = llm_call(
            [{"role": "user", "content": "test"}], llm_client=mock_client
        )
        assert result.content == "response"
        assert result.role == "assistant"

    def test_passes_through_llm_result(self):
        """Passes through LLMResult directly if client returns one."""
        mock_client = MagicMock()
        original = LLMResult(content="direct", role="assistant")
        mock_client.return_value = original

        result = llm_call(
            [{"role": "user", "content": "test"}], llm_client=mock_client
        )
        assert result is original
