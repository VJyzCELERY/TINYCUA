"""Unit tests for TinyCUAResponseNode components."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult
from tinycua.loops.result_aggregation import AggregatedResult


class TestResponseContext:
    """ResponseContext helper — context aggregation from NodeInput."""

    def test_response_context_fields(self):
        from tinycua.loops.response_node import ResponseContext

        context = ResponseContext(
            aggregated_result=None,
            session_context=[{"role": "assistant", "content": "hello"}],
            latest_output="output",
            continuation_payload={"key": "value"},
        )
        assert context.aggregated_result is None
        assert context.session_context == [{"role": "assistant", "content": "hello"}]
        assert context.latest_output == "output"
        assert context.continuation_payload == {"key": "value"}


class TestTinyCUAResponseNodeInit:
    """TinyCUAResponseNode initialization."""

    def test_default_init(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        node = TinyCUAResponseNode()
        assert node.node_id == "response"
        assert node.is_terminal is True
        assert node.config is not None
        assert node._continuation_payload is None
        assert node._needs_digestion is False
        assert hasattr(node, "_digest_attempts")

    def test_custom_node_id(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        node = TinyCUAResponseNode(node_id="custom-response")
        assert node.node_id == "custom-response"

    def test_custom_config(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        config.metadata["digester_enabled"] = False
        config.metadata["sufficiency_threshold"] = 5
        node = TinyCUAResponseNode(config=config)
        assert node.config.metadata["digester_enabled"] is False
        assert node.config.metadata["sufficiency_threshold"] == 5


class TestCheckContextSufficiency:
    """_check_context_sufficiency method."""

    def test_sufficient_with_aggregated_result(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        node = TinyCUAResponseNode()
        context = ResponseContext(
            aggregated_result=AggregatedResult(
                root_task_id="root",
                task_summaries=["Done"],
                final_context="Done",
            ),
            session_context=[],
            latest_output=None,
            continuation_payload=None,
        )
        assert node._check_context_sufficiency(context) is True

    def test_insufficient_no_aggregated_result(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        node = TinyCUAResponseNode()
        context = ResponseContext(
            aggregated_result=None,
            session_context=[],
            latest_output=None,
            continuation_payload=None,
        )
        assert node._check_context_sufficiency(context) is False

    def test_sufficient_with_session_context_fallback(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        node = TinyCUAResponseNode()
        context = ResponseContext(
            aggregated_result=None,
            session_context=[{"role": "assistant", "content": "Lots of context here"}],
            latest_output=None,
            continuation_payload=None,
        )
        # Without aggregated result but with session context, still insufficient
        assert node._check_context_sufficiency(context) is False

    def test_sufficient_with_latest_output(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        node = TinyCUAResponseNode()
        context = ResponseContext(
            aggregated_result=None,
            session_context=[],
            latest_output="intermediate output",
            continuation_payload=None,
        )
        assert node._check_context_sufficiency(context) is False

    def test_with_threshold_config(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        config = NodeConfigBase()
        config.metadata["sufficiency_threshold"] = 5
        node = TinyCUAResponseNode(config=config)

        # Context with fewer messages than threshold — insufficient
        context = ResponseContext(
            aggregated_result=None,
            session_context=[{"role": "assistant", "content": "only one"}],
            latest_output=None,
            continuation_payload=None,
        )
        assert node._check_context_sufficiency(context) is False

    def test_sufficient_with_high_threshold_met(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        config = NodeConfigBase()
        config.metadata["sufficiency_threshold"] = 2
        node = TinyCUAResponseNode(config=config)

        context = ResponseContext(
            aggregated_result=AggregatedResult(
                root_task_id="root",
                task_summaries=["A", "B"],
                final_context="A: done\nB: done",
            ),
            session_context=[
                {"role": "assistant", "content": "ctx1"},
                {"role": "assistant", "content": "ctx2"},
            ],
            latest_output="something",
            continuation_payload=None,
        )
        # Aggregated result present → sufficient regardless of threshold
        assert node._check_context_sufficiency(context) is True


class TestSynthesizeResponse:
    """_synthesize_response produces a final LLMResult."""

    def test_synthesize_with_context(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        config = NodeConfigBase()
        config.llm_client = MagicMock(
            return_value=LLMResult(
                content="Synthesized final response.",
                role="assistant",
            )
        )
        node = TinyCUAResponseNode(config=config)
        session = MagicMock()
        node.ensure_session(session)

        context = ResponseContext(
            aggregated_result=AggregatedResult(
                root_task_id="root",
                task_summaries=["Done"],
                final_context="Done",
            ),
            session_context=[{"role": "assistant", "content": "ctx"}],
            latest_output="prev output",
            continuation_payload=None,
        )
        result = node._synthesize_response(context)
        assert isinstance(result, LLMResult)
        assert result.content == "Synthesized final response."

    def test_synthesize_no_llm_client(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        config = NodeConfigBase()
        node = TinyCUAResponseNode(config=config)
        session = MagicMock()
        node.ensure_session(session)

        context = ResponseContext(
            aggregated_result=AggregatedResult(
                root_task_id="root",
                task_summaries=["Done"],
                final_context="Done",
            ),
            session_context=[],
            latest_output=None,
            continuation_payload=None,
        )
        result = node._synthesize_response(context)
        assert isinstance(result, LLMResult)
        # Should still return an LLMResult, possibly with empty content
        # since the node calls inherited ProcessNode.__call__ which raises
        # NodeExecutionError. Our implementation should catch this and
        # provide a fallback.
        assert result.content is not None


class TestSuspendForDigestion:
    """_suspend_for_digestion method."""

    def test_suspend_calls_queue_prepend(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        node = TinyCUAResponseNode()
        mock_queue = MagicMock()
        mock_context = MagicMock()

        node._suspend_for_digestion(mock_context, mock_queue)
        mock_queue.suspend_current_and_prepend.assert_called_once()

        # Check that the prepended node is an InformationDigesterNode
        args, _kwargs = mock_queue.suspend_current_and_prepend.call_args
        prepended = args[0]
        from tinycua.loops.information_digester import (
            TinyCUAInformationDigesterNode,
        )

        assert len(prepended) == 1
        assert isinstance(prepended[0], TinyCUAInformationDigesterNode)
        assert prepended[0].parent is node

    def test_suspend_increments_digest_attempts(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        node = TinyCUAResponseNode()
        assert node._digest_attempts == 0

        mock_queue = MagicMock()
        mock_context = MagicMock()
        node._suspend_for_digestion(mock_context, mock_queue)
        assert node._digest_attempts == 1

    def test_max_digest_attempts_prevents_infinite_loop(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        config.metadata["digester_enabled"] = True
        config.metadata["max_digest_attempts"] = 2

        node = TinyCUAResponseNode(config=config)
        node._digest_attempts = 2  # Already at max

        mock_queue = MagicMock()
        mock_context = MagicMock()
        node._suspend_for_digestion(mock_context, mock_queue)
        # Should NOT call suspend since max reached
        mock_queue.suspend_current_and_prepend.assert_not_called()


class TestGatherContextViaTools:
    """_gather_context_via_tools method."""

    def test_gather_context_returns_updated_context(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        config = NodeConfigBase()
        node = TinyCUAResponseNode(config=config)
        session = MagicMock()
        node.ensure_session(session)

        context = ResponseContext(
            aggregated_result=None,
            session_context=[],
            latest_output=None,
            continuation_payload=None,
        )
        result = node._gather_context_via_tools(context)
        assert isinstance(result, ResponseContext)
        # Should at minimum preserve the original context shape
        assert result.aggregated_result is None


class TestRetryCompliance:
    """Retry compliance via inherited ProcessNode retry loop."""

    def test_retry_exhaustion_returns_fallback(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        config.retry_policy = NodeRetryPolicy(
            max_attempts=3,
            on_retry_exhausted="record_failure",
        )
        config.metadata["fallback_message"] = "Fallback response."
        config.metadata["digester_enabled"] = False

        node = TinyCUAResponseNode(config=config)
        session = MagicMock()
        node.ensure_session(session)

        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "test"}],
        )
        # No LLM client — should trigger fallback
        result = node(input_data)

        assert isinstance(result, LLMResult)
        assert result.content == "Fallback response."

    def test_retry_success_with_client(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        config.retry_policy = NodeRetryPolicy(
            max_attempts=3,
            on_retry_exhausted="record_failure",
        )
        config.llm_client = MagicMock(
            return_value=LLMResult(content="Successful response.")
        )
        # Disable digester so insufficient context goes to tool fallback → synthesis
        config.metadata["digester_enabled"] = False

        node = TinyCUAResponseNode(config=config)
        session = MagicMock()
        node.ensure_session(session)

        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "test"}],
        )
        result = node(input_data)

        assert isinstance(result, LLMResult)
        assert result.content == "Successful response."


class TestContinuationRouting:
    """Consolidated continuation routing."""

    def test_continuation_payload_stored(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        node = TinyCUAResponseNode()
        assert node._continuation_payload is None

    def test_continuation_builds_synthesize_response(self):
        from tinycua.loops.response_node import TinyCUAResponseNode
        from tinycua.models.classification import MandatoryPassthrough

        config = NodeConfigBase()
        config.llm_client = MagicMock(
            return_value=LLMResult(content="Continuation response.")
        )

        node = TinyCUAResponseNode(config=config)
        session = MagicMock()
        node.ensure_session(session)

        passthrough = MandatoryPassthrough(
            target_node_id=node.node_id,
            target_session_id="session-id",
            reason="continuation",
        )
        node._continuation_payload = passthrough

        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "continue"}],
        )
        result = node(input_data)

        assert isinstance(result, LLMResult)


class TestOnComplete:
    """on_complete queue mutation hook."""

    def test_on_complete_with_digestion_flag(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        config.metadata["digester_enabled"] = True
        node = TinyCUAResponseNode(config=config)
        node._needs_digestion = True

        mock_queue = MagicMock()
        mock_response = LLMResult(content="placeholder")

        with patch.object(node, "_suspend_for_digestion") as mock_suspend:
            node.on_complete(mock_queue, mock_response)
            mock_suspend.assert_called_once()

    def test_on_complete_without_digestion_flag(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        config.metadata["digester_enabled"] = True
        node = TinyCUAResponseNode(config=config)
        node._needs_digestion = False

        mock_queue = MagicMock()
        mock_response = LLMResult(content="final")

        with patch.object(node, "_suspend_for_digestion") as mock_suspend:
            node.on_complete(mock_queue, mock_response)
            mock_suspend.assert_not_called()


class TestToolPolicyCompliance:
    """Tool policy compliance (FR-009)."""

    def test_response_node_same_toolset_as_task_executor(self):
        """ResponseNode uses same base toolset as TaskExecutor (FR-009)."""
        from tinycua.loops.response_node import TinyCUAResponseNode
        from tinycua.loops.task_executor import TinyCUATaskExecutorNode

        config = NodeConfigBase()
        response_node = TinyCUAResponseNode(config=config)
        executor_node = TinyCUATaskExecutorNode(config=config)

        assert response_node.config.tool_policy.include_agent_tools == \
               executor_node.config.tool_policy.include_agent_tools


class TestTerminalNormalization:
    """Terminal output normalization to string."""

    def test_normalize_string_content(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        config.llm_client = MagicMock(
            return_value=LLMResult(content="string content")
        )
        node = TinyCUAResponseNode(config=config)
        session = MagicMock()
        node.ensure_session(session)

        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "test"}],
        )
        result = node(input_data)
        assert isinstance(result, LLMResult)
        assert isinstance(result.content, str)
