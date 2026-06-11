"""Integration tests for TinyCUAResponseNode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult
from tinycua.loops.result_aggregation import AggregatedResult
from tinycua.models.session import Session


@pytest.fixture
def sufficient_context_aggregated() -> AggregatedResult:
    """Build an AggregatedResult with sufficient context."""
    return AggregatedResult(
        root_task_id="root",
        task_summaries=["Root: Completed successfully"],
        final_context="Root: Completed successfully",
    )


@pytest.fixture
def empty_aggregated() -> AggregatedResult | None:
    """No aggregated result — insufficient context."""
    return None


def _make_session_with_context(
    context_str: str,
    *,
    aggregated_result: AggregatedResult | None = None,
) -> Session:
    session = Session()
    entry: dict = {"role": "assistant", "content": context_str}
    if aggregated_result is not None:
        entry["aggregated_result"] = aggregated_result
    session.session_context.append(entry)
    return session


class TestTinyCUAResponseNodeDirectSynthesis:
    """Given a ResponseNode with sufficient context, it produces a final
    string response without invoking tools or the digester."""

    def test_direct_synthesis(self, sufficient_context_aggregated):
        """Produce final string response when context is sufficient."""
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        node = TinyCUAResponseNode(config=config)
        session = _make_session_with_context(
            "Root: Done",
            aggregated_result=AggregatedResult(
                root_task_id="root",
                task_summaries=["Root: Done"],
                final_context="Root: Done",
            ),
        )
        node.ensure_session(session)

        # Wire in a mock LLM client so ProcessNode.__call__ works
        node.config.llm_client = MagicMock(
            return_value=LLMResult(content="This is the final response.")
        )

        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "test"}],
        )
        result = node(input_data)

        assert isinstance(result, LLMResult)
        assert isinstance(result.content, str)
        assert len(result.content) > 0


class TestTinyCUAResponseNodeIsTerminal:
    """TinyCUAResponseNode should be marked as terminal."""

    def test_is_terminal_true(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        node = TinyCUAResponseNode()
        assert node.is_terminal is True
        assert node.node_id == "response"


class TestContextSufficiencyCheck:
    """Context sufficiency check correctly identifies sufficient vs. insufficient
    context."""

    def test_sufficient_context(self, sufficient_context_aggregated):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        config = NodeConfigBase()
        node = TinyCUAResponseNode(config=config)

        context = ResponseContext(
            aggregated_result=sufficient_context_aggregated,
            session_context=[{"role": "assistant", "content": "Some context"}],
            latest_output="intermediate output",
            continuation_payload=None,
        )
        assert node._check_context_sufficiency(context) is True

    def test_insufficient_context(self, empty_aggregated):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        config = NodeConfigBase()
        node = TinyCUAResponseNode(config=config)

        context = ResponseContext(
            aggregated_result=None,
            session_context=[],
            latest_output=None,
            continuation_payload=None,
        )
        assert node._check_context_sufficiency(context) is False


class TestResponseNodeContinuationRouting:
    """Consolidated continuation routing via MandatoryPassthrough."""

    def test_continuation_routing(self):
        from tinycua.loops.response_node import TinyCUAResponseNode
        from tinycua.models.classification import MandatoryPassthrough

        config = NodeConfigBase()
        node = TinyCUAResponseNode(config=config)
        session = Session()
        node.ensure_session(session)

        # Simulate a MandatoryPassthrough targeting this node
        passthrough = MandatoryPassthrough(
            target_node_id=node.node_id,
            target_session_id=session.session_id,
            reason="continuation",
        )
        node._continuation_payload = passthrough

        # Wire in a mock LLM client
        node.config.llm_client = MagicMock(
            return_value=LLMResult(content="Continuation response.")
        )

        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "continue"}],
        )
        result = node(input_data)

        assert isinstance(result, LLMResult)
        # Should produce content directly without LLM rerouting


class TestResponseNodeRetryBehavior:
    """Retry policy is respected and fallback message returned on exhaustion."""

    def test_retry_exhaustion_fallback(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        config.retry_policy = NodeRetryPolicy(
            max_attempts=3,
            on_retry_exhausted="record_failure",
        )
        config.metadata["fallback_message"] = (
            "I encountered an error generating the final response."
        )

        node = TinyCUAResponseNode(config=config)
        session = _make_session_with_context(
            "Test",
            aggregated_result=AggregatedResult(
                root_task_id="root",
                task_summaries=["Test"],
                final_context="Test",
            ),
        )
        node.ensure_session(session)

        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "test"}],
        )

        # No LLM client configured — will raise NodeExecutionError because
        # ProcessNode.__call__ requires one. The TinyCUAResponseNode should
        # catch this and return the fallback message.
        result = node(input_data)

        assert isinstance(result, LLMResult)
        assert result.content == config.metadata["fallback_message"]


class TestResponseNodeTerminalNormalization:
    """Terminal output is always normalized to a string."""

    def test_normalization(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        node = TinyCUAResponseNode(config=config)
        session = Session()
        node.ensure_session(session)

        # Wire in a mock LLM client that returns a valid response
        node.config.llm_client = MagicMock(
            return_value=LLMResult(content="Normalized string output.")
        )

        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "test"}],
        )
        result = node(input_data)

        assert isinstance(result.content, str)


class TestResponseNodeAggregationIntegration:
    """Integration with TinyCUALoop — produces final string response."""

    def test_aggregation_integration(self):
        from tinycua.loops.response_node import TinyCUAResponseNode

        config = NodeConfigBase()
        config.metadata["digester_enabled"] = False
        node = TinyCUAResponseNode(config=config)
        node.ensure_session(Session())

        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "test"}],
        )

        with patch.object(
            node,
            "_synthesize_response",
            return_value=LLMResult(content="Final response"),
        ):
            result = node(input_data)

        assert isinstance(result, LLMResult)
        assert isinstance(result.content, str)
        assert len(result.content) > 0
        assert result.content == "Final response"


class TestResponseNodeDigesterIntegration:
    """Digester suspension — verifies _suspend_for_digestion is called when
    context is insufficient and digester is enabled, then resumes with
    enriched context."""

    def test_digester_suspension(self):
        from tinycua.loops.response_node import (
            ResponseContext,
            TinyCUAResponseNode,
        )

        config = NodeConfigBase()
        config.metadata["digester_enabled"] = True
        response_node = TinyCUAResponseNode(config=config)
        session = Session()
        response_node.ensure_session(session)

        # Build ResponseContext for internal precondition check
        response_context = ResponseContext(
            aggregated_result=None,
            session_context=[],
            latest_output=None,
            continuation_payload=None,
        )

        # Verify precondition: context is insufficient
        assert response_node._check_context_sufficiency(response_context) is False

        # Build a proper NodeInput
        from tinycua.models.node_input import NodeInput

        input_data = NodeInput(
            input_type="continuation",
            messages=[{
                "role": "system",
                "content": "Insufficient context: no aggregated result",
            }],
        )

        # Mock the queue to capture suspension behavior
        from tinycua.loops.node_queue import NodeQueue

        mock_queue = MagicMock(spec=NodeQueue)
        mock_queue.current = response_node

        # Phase 1: __call__ with insufficient context + digester enabled
        # Per design: __call__ sets _needs_digestion flag and returns a placeholder.
        # Actual suspension (suspend_for_digestion) is deferred to on_complete.
        with patch.object(response_node, "_suspend_for_digestion") as mock_suspend:
            result = response_node(input_data)

            # Verify the flag is set — suspension defers to on_complete
            assert response_node._needs_digestion is True
            # _suspend_for_digestion should NOT be called during __call__
            mock_suspend.assert_not_called()

        # Phase 2: on_complete triggers suspension
        with patch.object(response_node, "_suspend_for_digestion") as mock_suspend:
            response_node.on_complete(mock_queue, result)
            mock_suspend.assert_called_once()
            # Verify the queue was passed for suspension operation
            call_args = mock_suspend.call_args
            assert call_args[0][1] is mock_queue  # second positional arg is the queue

        # Phase 3: Simulate resume after digestion with enriched context
        # Reset the flag for the resumed call
        response_node._needs_digestion = False

        # Mock the resume path: context is sufficient, synthesize directly
        with patch.object(
            response_node,
            "_synthesize_response",
            return_value=LLMResult(content="Final response after digestion"),
        ):
            with patch.object(
                response_node,
                "_check_context_sufficiency",
                return_value=True,
            ):
                resume_input = NodeInput(
                    input_type="continuation",
                    messages=[{
                        "role": "system",
                        "content": "Sufficient context: Enriched after digestion",
                    }],
                )
                resume_result = response_node(resume_input)

                # Verify the final synthesized result
                assert isinstance(resume_result, LLMResult)
                assert isinstance(resume_result.content, str)
                assert len(resume_result.content) > 0
                assert (
                    resume_result.content == "Final response after digestion"
                )
