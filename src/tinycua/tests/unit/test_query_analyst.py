"""Unit tests for TinyCUAQueryAnalystNode."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionResult, ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.route_map import RouteMap
from tinycua.models.classification import MandatoryPassthrough
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


class MockLLM:
    """Simple mock LLM that returns a fixed response."""

    def __init__(self, content: str = "response") -> None:
        self.content = content
        self.call_count = 0

    def __call__(self, messages: list[dict], **kwargs: object) -> dict:  # noqa: ARG002
        self.call_count += 1
        return {"role": "assistant", "content": self.content}


class MultiResponseMockLLM:
    """Mock LLM that returns responses sequentially."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.call_count = 0

    def __call__(self, messages: list[dict], **kwargs: object) -> dict:  # noqa: ARG002
        self.call_count += 1
        idx = min(self.call_count - 1, len(self.responses) - 1)
        return {"role": "assistant", "content": self.responses[idx]}


def test_query_analyst_init():
    """TinyCUAQueryAnalystNode initializes with default labels and route_map."""
    # Arrange & Act
    config = NodeConfigBase(llm_client=MockLLM())
    qa = TinyCUAQueryAnalystNode(config=config)

    # Assert
    assert qa.node_id == "query_analyst"
    assert qa.classification_labels == ["passthrough", "worker", "uncertain"]
    assert qa.route_map is not None
    assert qa.route_map.has_route("passthrough")
    assert qa.route_map.has_route("worker")
    assert qa.route_map.has_route("uncertain")


def test_query_analyst_classifies_passthrough():
    """QueryAnalyst classifies passthrough when MandatoryPassthrough is present."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["analysis", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    qa = TinyCUAQueryAnalystNode(config=config)
    session = Session()
    qa.ensure_session(session)
    mandatory = MandatoryPassthrough(
        target_node_id="target",
        target_session_id=session.session_id,
        reason="test",
        payload=None,
    )
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "test"}],
        metadata={"mandatory_passthrough": mandatory},
    )

    # Act
    result = qa(input_data)

    # Assert
    assert result.route_label == "passthrough"
    assert mock_llm.call_count == 0, "LLM should not be called"


def test_query_analyst_classifies_uncertain():
    """QueryAnalyst classifies uncertain when LLM returns uncertain."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["analysis", "uncertain"])
    config = NodeConfigBase(llm_client=mock_llm)
    qa = TinyCUAQueryAnalystNode(config=config)
    session = Session()
    qa.ensure_session(session)
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "test"}],
    )

    # Act
    result = qa(input_data)

    # Assert
    assert result.route_label == "uncertain"


def test_query_analyst_stale_passthrough():
    """QueryAnalyst drops stale MandatoryPassthrough with allow_restart=True."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["analysis", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    qa = TinyCUAQueryAnalystNode(config=config)
    session = Session()
    qa.ensure_session(session)
    mandatory = MandatoryPassthrough(
        target_node_id="target",
        target_session_id="wrong_session_id",
        reason="test",
        payload=None,
        allow_query_analyst_restart=True,
    )
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "test"}],
        metadata={"mandatory_passthrough": mandatory},
    )

    # Act
    result = qa(input_data)

    # Assert - stale passthrough is dropped, LLM is called
    assert result.route_label == "worker"
    assert mock_llm.call_count == 2


def test_query_analyst_worker_reuse():
    """QueryAnalyst reuses existing WorkerNode in queue."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["analysis", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    qa = TinyCUAQueryAnalystNode(config=config)
    existing_worker = ProcessNode(node_id="worker", config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[qa, existing_worker, response_node])
    session = Session()
    qa.ensure_session(session)
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "test"}],
    )

    # Act
    result = qa(input_data)
    qa.on_complete(queue, result)

    # Assert
    worker_nodes = [n for n in queue.items if n.node_id == "worker"]
    assert len(worker_nodes) == 1
    assert existing_worker in queue.items


def test_query_analyst_worker_spawn():
    """QueryAnalyst spawns new WorkerNode when none exists."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["analysis", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    qa = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[qa, response_node])
    session = Session()
    qa.ensure_session(session)
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "test"}],
    )

    # Act
    result = qa(input_data)
    qa.on_complete(queue, result)

    # Assert
    node_ids = [n.node_id for n in queue.items]
    assert "worker" in node_ids


def test_query_analyst_invalid_label_retry():
    """QueryAnalyst retries on invalid classification label, falls back to uncertain."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["analysis", "bad_label"])
    config = NodeConfigBase(llm_client=mock_llm)
    qa = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[qa, response_node])
    session = Session()
    qa.ensure_session(session)
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "test"}],
    )

    # Act
    result = qa(input_data)

    # Assert
    assert result.route_label == "uncertain"


def test_query_analyst_deduplication():
    """QueryAnalyst raises RuntimeError when added to queue with duplicate node_id."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["analysis", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    qa = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[qa, response_node])

    # Act & Assert
    second_qa = TinyCUAQueryAnalystNode(node_id="query_analyst", config=config)
    with pytest.raises(RuntimeError, match="QueryAnalyst already active"):
        queue.add_front(second_qa)


def test_query_analyst_preserves_input_query():
    """QueryAnalyst preserves the original user query in session context."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["analysis", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    qa = TinyCUAQueryAnalystNode(config=config)
    session = Session()
    qa.ensure_session(session)
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Act
    qa(input_data)

    # Assert - session context should contain the classification record
    assert len(session.session_context) > 0
    last_entry = session.session_context[-1]
    assert last_entry["role"] == "assistant"
    assert "[Classification]" in last_entry["content"]


def test_query_analyst_check_mandatory_passthrough():
    """check_mandatory_passthrough returns MandatoryPassthrough when present."""
    # Arrange
    config = NodeConfigBase(llm_client=MockLLM())
    qa = TinyCUAQueryAnalystNode(config=config)
    session = Session()
    qa.ensure_session(session)
    mandatory = MandatoryPassthrough(
        target_node_id="target",
        target_session_id=session.session_id,
        reason="test",
        payload=None,
    )
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "test"}],
        metadata={"mandatory_passthrough": mandatory},
    )

    # Act
    result = qa.check_mandatory_passthrough(input_data)

    # Assert
    assert result is mandatory


def test_query_analyst_check_mandatory_passthrough_none():
    """check_mandatory_passthrough returns None when not present."""
    # Arrange
    config = NodeConfigBase(llm_client=MockLLM())
    qa = TinyCUAQueryAnalystNode(config=config)
    session = Session()
    qa.ensure_session(session)
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "test"}],
    )

    # Act
    result = qa.check_mandatory_passthrough(input_data)

    # Assert
    assert result is None


def test_query_analyst_find_existing_worker():
    """find_existing_worker returns WorkerNode when present."""
    # Arrange
    config = NodeConfigBase(llm_client=MockLLM())
    qa = TinyCUAQueryAnalystNode(config=config)
    existing_worker = ProcessNode(node_id="worker", config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[qa, existing_worker, response_node])

    # Act
    result = qa.find_existing_worker(queue)

    # Assert
    assert result is existing_worker


def test_query_analyst_find_existing_worker_none():
    """find_existing_worker returns None when no WorkerNode present."""
    # Arrange
    config = NodeConfigBase(llm_client=MockLLM())
    qa = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[qa, response_node])

    # Act
    result = qa.find_existing_worker(queue)

    # Assert
    assert result is None


def test_query_analyst_route_passthrough():
    """route_passthrough is a no-op (does not mutate queue)."""
    # Arrange
    config = NodeConfigBase(llm_client=MockLLM())
    qa = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[qa, response_node])
    result = DecisionResult(
        route_label="passthrough",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="passthrough", role="assistant"),
    )

    # Act
    qa.route_passthrough(queue, result)

    # Assert
    assert len(queue.items) == 2
    assert queue.items[0] is qa


def test_query_analyst_route_worker():
    """route_worker spawns a new WorkerNode when none exists."""
    # Arrange
    config = NodeConfigBase(llm_client=MockLLM())
    qa = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[qa, response_node])
    result = DecisionResult(
        route_label="worker",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="worker", role="assistant"),
    )

    # Act
    qa.route_worker(queue, result)

    # Assert
    node_ids = [n.node_id for n in queue.items]
    assert "worker" in node_ids


def test_query_analyst_route_uncertain():
    """route_uncertain is a no-op (QueryAnalyst stays active)."""
    # Arrange
    config = NodeConfigBase(llm_client=MockLLM())
    qa = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[qa, response_node])
    result = DecisionResult(
        route_label="uncertain",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="uncertain", role="assistant"),
    )

    # Act
    qa.route_uncertain(queue, result)

    # Assert
    assert len(queue.items) == 2
    assert queue.items[0] is qa


def test_query_analyst_custom_route_map():
    """TinyCUAQueryAnalystNode accepts a custom RouteMap."""
    # Arrange
    config = NodeConfigBase(llm_client=MockLLM())
    custom_map = RouteMap()
    custom_handler_called = []

    def custom_handler(queue: NodeQueue, result: DecisionResult) -> None:
        custom_handler_called.append(result.route_label)

    custom_map.register("custom_label", custom_handler)
    qa = TinyCUAQueryAnalystNode(config=config, route_map=custom_map)

    # Assert
    assert qa.route_map is custom_map
    assert qa.route_map.has_route("custom_label")
