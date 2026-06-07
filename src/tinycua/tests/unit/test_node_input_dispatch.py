"""Unit tests for NodeInputLike dispatch in ProcessNode."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import NodeConfigBase
from tinycua.loops.node import ProcessNode
from tinycua.models.node_input import NodeInput, NodePayload
from tinycua.models.session import Session


class MockLLM:
    """Mock LLM client that records inputs."""

    def __init__(self) -> None:
        self.call_count = 0
        self.all_messages: list[list[dict]] = []

    def __call__(self, messages: list[dict], **kwargs: object) -> dict:  # noqa: ARG002
        self.call_count += 1
        self.all_messages.append(messages)
        return {"role": "assistant", "content": "ok"}


class TestInputDispatchString:
    """Tests for string input dispatch."""

    def test_empty_string_raises_value_error(self) -> None:
        """Empty string raises ValueError."""
        from tinycua.models.node_input import convert_node_input_to_messages

        with pytest.raises(ValueError, match="Empty input"):
            convert_node_input_to_messages("")

    def test_whitespace_only_string_raises_value_error(self) -> None:
        """Whitespace-only string raises ValueError."""
        from tinycua.models.node_input import convert_node_input_to_messages

        with pytest.raises(ValueError, match="Empty input"):
            convert_node_input_to_messages("   ")

    def test_external_string_becomes_user_role(self) -> None:
        """String with source='external' becomes user-role message."""
        from tinycua.models.node_input import convert_node_input_to_messages

        result = convert_node_input_to_messages("Hello", source="external")
        assert result == [{"role": "user", "content": "Hello"}]

    def test_internal_string_becomes_assistant_role(self) -> None:
        """String with source='internal' becomes assistant-role message."""
        from tinycua.models.node_input import convert_node_input_to_messages

        result = convert_node_input_to_messages("Internal handoff")
        assert result == [{"role": "assistant", "content": "Internal handoff"}]


class TestInputDispatchNodeInput:
    """Tests for NodeInput dispatch."""

    def test_node_input_messages(self) -> None:
        """NodeInput dispatches to to_messages()."""
        node_input = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "hello"}],
        )
        from tinycua.models.node_input import convert_node_input_to_messages

        result = convert_node_input_to_messages(node_input)
        assert result == [{"role": "user", "content": "hello"}]

    def test_node_input_with_payloads(self) -> None:
        """NodeInput dispatches payloads and messages."""
        payload = NodePayload(payload_type="test", content="data")
        node_input = NodeInput(
            input_type="continuation",
            payloads=[payload],
            messages=[{"role": "user", "content": "next"}],
        )
        from tinycua.models.node_input import convert_node_input_to_messages

        result = convert_node_input_to_messages(node_input)
        assert len(result) == 2
        assert result[0]["role"] == "assistant"  # payload
        assert result[1]["role"] == "user"  # continuation


class TestInputDispatchNodePayload:
    """Tests for NodePayload dispatch."""

    def test_node_payload_dispatches(self) -> None:
        """NodePayload dispatches to to_messages()."""
        payload = NodePayload(payload_type="test", content="data")
        from tinycua.models.node_input import convert_node_input_to_messages

        result = convert_node_input_to_messages(payload)
        assert result == [{"role": "assistant", "content": "data"}]


class TestInputDispatchMessageList:
    """Tests for list[dict] dispatch."""

    def test_list_passthrough(self) -> None:
        """list[dict] passes through directly."""
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        from tinycua.models.node_input import convert_node_input_to_messages

        result = convert_node_input_to_messages(messages)
        assert result is messages

    def test_empty_list(self) -> None:
        """Empty list passes through."""
        from tinycua.models.node_input import convert_node_input_to_messages

        result = convert_node_input_to_messages([])
        assert result == []


class TestProcessNodeInputIntegration:
    """Integration tests for ProcessNode with various input types."""

    def _make_node(self, mock_llm: MockLLM) -> ProcessNode:
        """Create a ProcessNode with mock LLM."""
        config = NodeConfigBase(llm_client=mock_llm)
        node = ProcessNode(
            node_id="test",
            config=config,
            instruction="Test node",
        )
        node.session = Session()
        return node

    def test_string_input_calls_llm(self) -> None:
        """ProcessNode with string input calls LLM."""
        mock_llm = MockLLM()
        node = self._make_node(mock_llm)

        result = node("Hello")

        assert mock_llm.call_count == 1
        assert result.content == "ok"

    def test_node_input_calls_llm(self) -> None:
        """ProcessNode with NodeInput calls LLM."""
        mock_llm = MockLLM()
        node = self._make_node(mock_llm)

        input_data = NodeInput(
            input_type="analysis",
            messages=[{"role": "user", "content": "Classify this"}],
        )
        node(input_data)

        assert mock_llm.call_count == 1

    def test_payload_calls_llm(self) -> None:
        """ProcessNode with NodePayload calls LLM."""
        mock_llm = MockLLM()
        node = self._make_node(mock_llm)

        payload = NodePayload(payload_type="test", content="data")
        node(payload)

        assert mock_llm.call_count == 1

    def test_list_calls_llm(self) -> None:
        """ProcessNode with list[dict] calls LLM."""
        mock_llm = MockLLM()
        node = self._make_node(mock_llm)

        messages = [{"role": "user", "content": "hello"}]
        node(messages)

        assert mock_llm.call_count == 1
