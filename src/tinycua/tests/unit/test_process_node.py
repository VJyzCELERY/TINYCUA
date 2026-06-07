"""Unit tests for ProcessNode."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import NodeConfigBase, NodeRetryPolicy
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node import NodeExecutionError, ProcessNode
from tinycua.models.node_input import NodeInput, NodePayload
from tinycua.models.session import Session


class MockLLM:
    """Mock LLM client for testing."""

    def __init__(self, response: str = "mock response") -> None:
        self.response = response
        self.call_count = 0
        self.last_messages: list[dict] | None = None

    def __call__(self, messages: list[dict], **kwargs: object) -> dict:  # noqa: ARG002
        self.call_count += 1
        self.last_messages = messages
        return {"role": "assistant", "content": self.response}


class TestProcessNodeInit:
    """Tests for ProcessNode initialization."""

    def test_inherits_from_node(self) -> None:
        """ProcessNode inherits from Node."""
        config = NodeConfigBase(llm_client=MockLLM())
        node = ProcessNode(node_id="test", config=config, instruction="Instruction")
        assert node.node_id == "test"
        assert node._instruction == "Instruction"


class TestProcessNodeCall:
    """Tests for ProcessNode.__call__."""

    def test_string_input(self) -> None:
        """ProcessNode handles string input."""
        mock_llm = MockLLM(response="result")
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        node.session = Session()

        result = node("Hello")

        assert result.content == "result"
        assert mock_llm.call_count == 1

    def test_node_input(self) -> None:
        """ProcessNode handles NodeInput."""
        mock_llm = MockLLM(response="node result")
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        node.session = Session()

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Classify this"}],
        )
        result = node(input_data)

        assert result.content == "node result"

    def test_node_payload(self) -> None:
        """ProcessNode handles NodePayload."""
        mock_llm = MockLLM(response="payload result")
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        node.session = Session()

        payload = NodePayload(payload_type="test", content="data")
        result = node(payload)

        assert result.content == "payload result"

    def test_message_list_input(self) -> None:
        """ProcessNode handles list[dict] input."""
        mock_llm = MockLLM(response="list result")
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        node.session = Session()

        messages = [{"role": "user", "content": "hello"}]
        result = node(messages)

        assert result.content == "list result"

    def test_no_session_raises(self) -> None:
        """ProcessNode raises NodeExecutionError without session."""
        mock_llm = MockLLM()
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")

        with pytest.raises(NodeExecutionError, match="no session"):
            node("Hello")

    def test_no_llm_client_raises(self) -> None:
        """ProcessNode raises NodeExecutionError without LLM client."""
        config = NodeConfigBase(llm_client=None)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        node.session = Session()

        with pytest.raises(NodeExecutionError, match="No LLM client"):
            node("Hello")


class TestProcessNodeCallLLM:
    """Tests for ProcessNode._call_llm."""

    def test_calls_llm_with_messages(self) -> None:
        """_call_llm invokes the LLM client with messages."""
        mock_llm = MockLLM(response="called")
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")

        messages = [{"role": "system", "content": "You are helpful."}]
        result = node._call_llm(messages)

        assert mock_llm.call_count == 1
        assert mock_llm.last_messages == messages
        assert result.content == "called"

    def test_returns_llm_result(self) -> None:
        """_call_llm returns LLMResult from dict response."""
        mock_llm = MockLLM(response="test")
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")

        result = node._call_llm([{"role": "user", "content": "hi"}])

        assert isinstance(result, LLMResult)
        assert result.content == "test"
        assert result.role == "assistant"


class TestProcessNodeRetry:
    """Tests for ProcessNode retry behavior."""

    def test_retries_on_validation_failure(self) -> None:
        """ProcessNode retries when validation fails."""
        mock_llm = MockLLM(response="retry result")
        config = NodeConfigBase(
            llm_client=mock_llm,
            retry_policy=NodeRetryPolicy(max_attempts=3),
        )
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        node.session = Session()

        call_count = 0
        original_validate = node.validate_output

        def patched_validate(response: LLMResult) -> ValidationResult:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            result = ValidationResult()
            if call_count < 3:
                result.is_valid = False
                result.errors = ["fail"]
            else:
                result.is_valid = True
            return result

        node.validate_output = patched_validate  # type: ignore[method-assign]
        node("Trigger retry")

        assert mock_llm.call_count == 3

    def test_raises_on_exhaustion(self) -> None:
        """ProcessNode raises when retry exhausted with policy='raise'."""
        mock_llm = MockLLM(response="fail")
        config = NodeConfigBase(
            llm_client=mock_llm,
            retry_policy=NodeRetryPolicy(
                max_attempts=2, on_retry_exhausted="raise"
            ),
        )
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        node.session = Session()

        def always_invalid(response: LLMResult) -> ValidationResult:  # noqa: ARG001
            r = ValidationResult()
            r.is_valid = False
            r.errors = ["always fail"]
            return r

        node.validate_output = always_invalid  # type: ignore[method-assign]

        with pytest.raises(NodeExecutionError, match="Retry exhausted"):
            node("Fail")


class TestProcessNodeBuildMessages:
    """Tests for ProcessNode.build_messages."""

    def test_includes_system_prompt(self) -> None:
        """build_messages includes system prompt from instruction."""
        mock_llm = MockLLM()
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(
            node_id="test", config=config, instruction="You are helpful."
        )
        session = Session()

        messages = node.build_messages(session, "Hello")

        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert "You are helpful." in system_msgs[0]["content"]

    def test_includes_session_context(self) -> None:
        """build_messages includes session context when enabled."""
        mock_llm = MockLLM()
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        session = Session()
        session.session_context = [{"role": "assistant", "content": "Context"}]

        messages = node.build_messages(session, "Hello")

        context_msgs = [m for m in messages if m.get("content") == "Context"]
        assert len(context_msgs) == 1

    def test_excludes_session_context_when_disabled(self) -> None:
        """build_messages excludes session context when disabled."""
        from tinycua.config.node_config import NodeMessagePolicy

        mock_llm = MockLLM()
        config = NodeConfigBase(
            llm_client=mock_llm,
            message_policy=NodeMessagePolicy(include_session_context=False),
        )
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        session = Session()
        session.session_context = [{"role": "assistant", "content": "Context"}]

        messages = node.build_messages(session, "Hello")

        context_msgs = [m for m in messages if m.get("content") == "Context"]
        assert len(context_msgs) == 0

    def test_includes_continuation_from_input(self) -> None:
        """build_messages includes continuation messages from input."""
        mock_llm = MockLLM()
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(node_id="test", config=config, instruction="Inst")
        session = Session()

        messages = node.build_messages(session, "Internal continuation")

        continuation_msgs = [
            m for m in messages if m.get("content") == "Internal continuation"
        ]
        assert len(continuation_msgs) == 1
        assert continuation_msgs[0]["role"] == "assistant"
