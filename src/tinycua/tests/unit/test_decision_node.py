"""Unit tests for DecisionNode."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionNode, DecisionResult, NodeExecutionError
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


class MockLLM:
    """Mock LLM client that returns configurable responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = responses or ["analysis", "worker"]
        self.call_count = 0
        self.all_messages: list[list[dict]] = []

    def __call__(self, messages: list[dict], **kwargs: object) -> dict:  # noqa: ARG002
        idx = min(self.call_count, len(self.responses) - 1)
        self.call_count += 1
        self.all_messages.append(messages)
        return {"role": "assistant", "content": self.responses[idx]}


class TestDecisionNodeInit:
    """Tests for DecisionNode initialization."""

    def test_inherits_from_process_node(self) -> None:
        """DecisionNode inherits from ProcessNode."""
        from tinycua.loops.node import ProcessNode

        config = NodeConfigBase(llm_client=MockLLM())
        node = DecisionNode(
            node_id="test",
            config=config,
            instruction="Instruction",
            classification_labels=["a", "b"],
        )
        assert isinstance(node, ProcessNode)
        assert node.classification_labels == ["a", "b"]

    def test_default_labels(self) -> None:
        """DecisionNode defaults to empty classification labels."""
        config = NodeConfigBase(llm_client=MockLLM())
        node = DecisionNode(node_id="test", config=config)
        assert node.classification_labels == []


class TestDecisionNodeCall:
    """Tests for DecisionNode.__call__."""

    def test_returns_decision_result(self) -> None:
        """DecisionNode returns DecisionResult with route label."""
        mock_llm = MockLLM(responses=["analysis text", "worker"])
        config = NodeConfigBase(llm_client=mock_llm)
        node = DecisionNode(
            node_id="test",
            config=config,
            instruction="Classify",
            classification_labels=["passthrough", "worker"],
        )
        node.session = Session()

        result = node("Classify this input")

        assert isinstance(result, DecisionResult)
        assert result.route_label == "worker"
        assert result.analysis_response.content == "analysis text"
        assert result.classification_response.content == "worker"

    def test_two_llm_calls(self) -> None:
        """DecisionNode makes exactly two LLM calls."""
        mock_llm = MockLLM(responses=["analysis", "passthrough"])
        config = NodeConfigBase(llm_client=mock_llm)
        node = DecisionNode(
            node_id="test",
            config=config,
            instruction="Classify",
            classification_labels=["passthrough", "worker"],
        )
        node.session = Session()

        node("Input")

        assert mock_llm.call_count == 2

    def test_no_session_raises(self) -> None:
        """DecisionNode raises without session."""
        config = NodeConfigBase(llm_client=MockLLM())
        node = DecisionNode(
            node_id="test",
            config=config,
            classification_labels=["a"],
        )

        with pytest.raises(NodeExecutionError, match="no session"):
            node("Input")

    def test_node_input(self) -> None:
        """DecisionNode handles NodeInput."""
        mock_llm = MockLLM(responses=["analysis", "worker"])
        config = NodeConfigBase(llm_client=mock_llm)
        node = DecisionNode(
            node_id="test",
            config=config,
            instruction="Classify",
            classification_labels=["passthrough", "worker"],
        )
        node.session = Session()

        input_data = NodeInput(
            input_type="analysis",
            messages=[{"role": "user", "content": "Classify this"}],
        )
        result = node(input_data)

        assert isinstance(result, DecisionResult)
        assert result.route_label == "worker"


class TestDecisionNodeDispatchRoute:
    """Tests for DecisionNode._dispatch_route."""

    def test_exact_match(self) -> None:
        """_dispatch_route returns exact match."""
        config = NodeConfigBase(llm_client=MockLLM())
        node = DecisionNode(
            node_id="test",
            config=config,
            classification_labels=["passthrough", "worker"],
        )
        response = LLMResult(content="worker")
        assert node._dispatch_route(response) == "worker"

    def test_case_insensitive(self) -> None:
        """_dispatch_route is case-insensitive."""
        config = NodeConfigBase(llm_client=MockLLM())
        node = DecisionNode(
            node_id="test",
            config=config,
            classification_labels=["passthrough", "worker"],
        )
        response = LLMResult(content="Worker")
        assert node._dispatch_route(response) == "worker"

    def test_fallback_to_first(self) -> None:
        """_dispatch_route raises ValueError for unrecognized labels."""
        config = NodeConfigBase(llm_client=MockLLM())
        node = DecisionNode(
            node_id="test",
            config=config,
            classification_labels=["passthrough", "worker"],
        )
        response = LLMResult(content="unknown label")
        with pytest.raises(ValueError, match="Classification label not recognized"):
            node._dispatch_route(response)

    def test_empty_labels(self) -> None:
        """_dispatch_route raises ValueError with no labels."""
        config = NodeConfigBase(llm_client=MockLLM())
        node = DecisionNode(node_id="test", config=config)
        response = LLMResult(content="anything")
        with pytest.raises(ValueError, match="Classification label not recognized"):
            node._dispatch_route(response)


class TestDecisionNodeClassificationCall:
    """Tests for DecisionNode._classification_call."""

    def test_appends_analysis_and_classification_prompt(self) -> None:
        """_classification_call appends analysis result and classification prompt."""
        # MockLLM returns first response for each call; _classification_call makes 1 call
        mock_llm = MockLLM(responses=["worker"])
        config = NodeConfigBase(llm_client=mock_llm)
        node = DecisionNode(
            node_id="test",
            config=config,
            classification_labels=["passthrough", "worker"],
        )

        analysis_response = LLMResult(content="My analysis")
        messages = [{"role": "system", "content": "Classify"}]
        result = node._classification_call(messages, analysis_response)

        assert result.content == "worker"
        # Should have made one LLM call
        assert mock_llm.call_count == 1
        # Messages should include analysis and classification prompt
        last_messages = mock_llm.all_messages[0]
        assert any("My analysis" in m.get("content", "") for m in last_messages)
        assert any("Classify" in m.get("content", "") for m in last_messages)
