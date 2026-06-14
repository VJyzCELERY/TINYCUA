"""Unit tests for DecisionNode classification validation and retry."""

import pytest

from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionNode, NodeExecutionError
from tinycua.models.session import Session


class MockLLM:
    """Mock LLM returning a sequence of LLMResult responses."""

    def __init__(self, responses):
        self._responses = [
            LLMResult(content=r["content"]) if isinstance(r, dict) else r
            for r in responses
        ]
        self.call_count = 0

    def __call__(self, messages, **kwargs):
        idx = min(self.call_count, len(self._responses) - 1)
        self.call_count += 1
        return self._responses[idx]


def _make_decision_node(classification_labels=None, **config_overrides):
    """Create a DecisionNode with mock LLM for testing."""
    defaults = {
        "llm_client": MockLLM(
            [
                LLMResult(content="analysis"),
                LLMResult(content="valid_label"),
            ]
        ),
        "retry_policy": NodeRetryPolicy(max_attempts=1),
    }
    defaults.update(config_overrides)
    config = NodeConfigBase(**defaults)
    node = DecisionNode(
        node_id="test-decision",
        config=config,
        instruction="Analyze and classify",
        classification_labels=classification_labels or ["valid_label", "other"],
    )
    node.session = Session()
    return node


class TestClassificationValidation:
    """Tests for DecisionNode._validate_classification()."""

    def test_valid_label_accepted(self):
        """Classification matching an allowed label passes."""
        node = _make_decision_node()
        response = LLMResult(content="valid_label")
        result = node._validate_classification(response)
        assert result.is_valid is True

    def test_valid_label_case_insensitive(self):
        """Classification is matched case-insensitively."""
        node = _make_decision_node()
        response = LLMResult(content="VALID_LABEL")
        result = node._validate_classification(response)
        assert result.is_valid is True

    def test_valid_label_partial_match(self):
        """Classification containing a label passes."""
        node = _make_decision_node()
        response = LLMResult(content="I think this is valid_label")
        result = node._validate_classification(response)
        assert result.is_valid is True

    def test_invalid_label_rejected(self):
        """Classification not matching any allowed label fails."""
        node = _make_decision_node()
        response = LLMResult(content="invalid_choice")
        result = node._validate_classification(response)
        assert result.is_valid is False
        assert any("invalid_choice" in e for e in result.errors)

    def test_empty_labels_list(self):
        """Empty classification_labels means nothing is valid."""
        node = _make_decision_node(classification_labels=[])
        response = LLMResult(content="anything")
        result = node._validate_classification(response)
        assert result.is_valid is False


class TestDecisionNodeRetry:
    """Tests for DecisionNode classification retry loop."""

    def test_valid_on_first_attempt(self):
        """Valid classification accepted on first attempt."""
        node = _make_decision_node(
            classification_labels=["correct"],
            llm_client=MockLLM(
                [
                    LLMResult(content="analysis"),
                    LLMResult(content="correct"),
                ]
            ),
        )
        result = node("input")
        assert result.route_label == "correct"

    def test_invalid_triggers_retry(self):
        """Invalid classification triggers retry."""
        node = _make_decision_node(
            classification_labels=["correct"],
            llm_client=MockLLM(
                [
                    LLMResult(content="analysis"),
                    LLMResult(content="wrong"),
                    LLMResult(content="analysis 2"),
                    LLMResult(content="correct"),
                ]
            ),
            retry_policy=NodeRetryPolicy(max_attempts=2),
        )
        result = node("input")
        assert result.route_label == "correct"

    def test_exhaustion_raises_error(self):
        """Classification retry exhaustion raises NodeExecutionError."""
        node = _make_decision_node(
            classification_labels=["correct"],
            llm_client=MockLLM(
                [
                    LLMResult(content="analysis"),
                    LLMResult(content="wrong"),
                    LLMResult(content="analysis 2"),
                    LLMResult(content="still wrong"),
                ]
            ),
            retry_policy=NodeRetryPolicy(
                max_attempts=2,
                on_retry_exhausted="raise",
            ),
        )
        with pytest.raises(NodeExecutionError, match="Retry exhausted"):
            node("input")

    def test_exhaustion_records_failure(self):
        """Classification retry exhaustion records failure to session."""
        node = _make_decision_node(
            classification_labels=["correct"],
            llm_client=MockLLM(
                [
                    LLMResult(content="analysis"),
                    LLMResult(content="wrong"),
                    LLMResult(content="analysis 2"),
                    LLMResult(content="still wrong"),
                ]
            ),
            retry_policy=NodeRetryPolicy(
                max_attempts=2,
                on_retry_exhausted="record_failure",
            ),
        )
        node("input")
        contents = [e.content for e in node.session.session_context]
        assert any("RETRY_EXHAUSTED" in c for c in contents)
