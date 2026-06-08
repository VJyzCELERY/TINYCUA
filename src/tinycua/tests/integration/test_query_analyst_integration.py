"""Integration tests for RouteMap and TinyCUAQueryAnalystNode."""

from __future__ import annotations

import pytest

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import DecisionResult, ProcessNode

from tinycua.loops.route_map import RouteMap
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.models.classification import MandatoryPassthrough


class MultiResponseMockLLM:
    """Mock LLM that returns responses sequentially from a list.

    Usage:
        mock = MultiResponseMockLLM(["analysis", "worker"])
        mock(messages)  # returns "analysis"
        mock(messages)  # returns "worker"

    If more calls are made than responses provided, returns the last response.

    Notes on response ordering:
    - The two-step decision process calls the LLM twice per input:
      first for analysis, then for classification.
    - Classification responses MUST exactly match RouteMap labels
      (exact string match, not fuzzy).
    - For multi-call scenarios, provide responses in order:
      [analysis_response, classification_response].

    Determining mock responses for test cases:
    - First response: Any string (the analysis step ignores the content)
    - Second response: Must exactly match a registered RouteMap label
      (e.g., "worker", "manager", "researcher")

    Handling edge cases:
    - If the LLM returns a label that doesn't match any RouteMap entry,
      the dispatch will raise a KeyError or return an error result.
    - Tests should use exact label strings, not natural language variations
      like "I think this should be classified as a worker".
    """

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.call_count = 0
        self.last_messages: list[dict] | None = None

    def __call__(self, messages: list[dict], **kwargs: object) -> dict:  # noqa: ARG002
        self.call_count += 1
        self.last_messages = messages
        idx = min(self.call_count - 1, len(self.responses) - 1)
        return {"role": "assistant", "content": self.responses[idx]}


def test_route_map_dispatches_to_handler():
    """RouteMap dispatches labels to correct handlers."""
    # Arrange
    route_map = RouteMap()
    handler_called = []

    def mock_handler(queue: NodeQueue, result: DecisionResult) -> None:
        handler_called.append(result.route_label)

    route_map.register("worker", mock_handler)
    result = DecisionResult(
        route_label="worker",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="worker", role="assistant"),
    )
    queue = NodeQueue()
    # Act
    route_map.dispatch("worker", queue, result)
    # Assert
    assert handler_called == ["worker"]


def test_query_analyst_classifies_worker():
    """QueryAnalyst classifies input as worker."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["I need to write a script", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    session = Session()
    query_analyst.ensure_session(session)
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )
    # Act
    result = query_analyst(input_data)
    # Assert
    assert result.route_label == "worker"


def test_query_analyst_e2e_worker_route():
    """End-to-end: QueryAnalyst classifies worker and spawns WorkerNode into queue.

    Starts with queue [query_analyst, response_node] (NO worker_node).
    After on_complete, verify worker_node was SPAWNED into the queue.
    This proves the routing logic works, not that a pre-existing node persists.
    """
    # Arrange
    mock_llm = MultiResponseMockLLM(["I need to write a script", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[query_analyst, response_node])
    session = Session()
    # Act - execute query_analyst
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )
    query_analyst.ensure_session(session)
    result = query_analyst(input_data)
    # Assert - queue should have query_analyst at current before on_complete
    assert queue.current == query_analyst
    # After on_complete, worker_node should be SPAWNED into queue
    query_analyst.on_complete(queue, result)
    # Worker node should now be in queue (spawned, not pre-existing)
    node_ids = [node.node_id for node in queue.items]
    assert "worker" in node_ids, f"Expected worker spawned in queue, got {node_ids}"
    # Worker should appear before response_node (terminal)
    worker_idx = node_ids.index("worker")
    response_idx = node_ids.index("response")
    assert worker_idx < response_idx, "Worker must appear before ResponseNode"


def test_query_analyst_e2e_uncertain():
    """End-to-end: QueryAnalyst classifies as uncertain and remains active.

    When classification is uncertain, QueryAnalyst stays active and
    waits for more user input. Queue does not advance.
    """
    # Arrange
    mock_llm = MultiResponseMockLLM(["unclear request", "uncertain"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[query_analyst, response_node])
    session = Session()
    # Act
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "um maybe something"}],
    )
    query_analyst.ensure_session(session)
    result = query_analyst(input_data)
    # Assert - route_label should be uncertain
    assert result.route_label == "uncertain"
    # on_complete should NOT remove query_analyst from queue
    query_analyst.on_complete(queue, result)
    assert queue.current == query_analyst, "QueryAnalyst must remain active for uncertain"
    # Queue should still have only query_analyst + response_node (no spawn)
    node_ids = [node.node_id for node in queue.items]
    assert node_ids == ["query_analyst", "response"], f"Unexpected queue: {node_ids}"


def test_query_analyst_e2e_passthrough():
    """End-to-end: QueryAnalyst routes via passthrough to target node.

    When MandatoryPassthrough is present, QueryAnalyst forwards input
    directly to the target node/session without LLM classification.
    """
    # Arrange
    mock_llm = MultiResponseMockLLM(["ignored analysis", "ignored classification"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    _queue = NodeQueue(items=[query_analyst, response_node])
    session = Session()
    mandatory = MandatoryPassthrough(
        target_node_id="response",
        target_session_id=session.session_id,
        reason="continuation",
        payload=None,
    )
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "Continue previous task"}],
        metadata={"mandatory_passthrough": mandatory},
    )
    # Act
    query_analyst.ensure_session(session)
    result = query_analyst(input_data)
    # Assert - mandatory_passthrough should override, routing to passthrough
    assert result.route_label == "passthrough"
    # LLM should NOT have been called (precheck short-circuits)
    assert mock_llm.call_count == 0, "LLM should not be called when mandatory_passthrough is present"


def test_query_analyst_queue_bootstrap():
    """Queue has QueryAnalyst at front and ResponseNode at end.

    Verifies the bootstrap invariant: QueryAnalyst is always the first
    node and the queue ends with a terminal ResponseNode.
    """
    # Arrange
    mock_llm = MultiResponseMockLLM(["analysis", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[query_analyst, response_node])
    # Assert - QueryAnalyst at front
    assert queue.current == query_analyst, "QueryAnalyst must be at queue front"
    # Assert - ResponseNode at end and is terminal
    assert queue.items[-1] == response_node, "ResponseNode must be at queue end"
    assert queue.items[-1].is_terminal, "Last node must be terminal"
    # Assert - queue has exactly 2 items initially
    assert len(queue.items) == 2, f"Expected 2 items, got {len(queue.items)}"
    # Assert - QueryAnalyst node_id matches expected
    assert queue.items[0].node_id == "query_analyst"


def test_query_analyst_mandatory_passthrough_precheck():
    """MandatoryPassthrough overrides LLM classification."""
    # Arrange
    mock_llm = MultiResponseMockLLM(["This should be ignored", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    session = Session()
    query_analyst.ensure_session(session)
    mandatory = MandatoryPassthrough(
        target_node_id="target_node",
        target_session_id=session.session_id,
        reason="continuation",
        payload=None,
    )
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "Continue previous task"}],
        metadata={"mandatory_passthrough": mandatory},
    )
    # Act
    result = query_analyst(input_data)
    # Assert - should route to passthrough, not worker
    assert result.route_label == "passthrough"


def test_query_analyst_e2e_worker_reuse():
    """End-to-end: QueryAnalyst reuses existing WorkerNode instead of spawning a new one.

    When queue already contains a WorkerNode, QueryAnalyst should reuse it
    rather than spawning a duplicate. Verifies worker reuse logic.
    """
    # Arrange
    mock_llm = MultiResponseMockLLM(["I need to write a script", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    existing_worker = ProcessNode(node_id="worker", config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[query_analyst, existing_worker, response_node])
    session = Session()
    # Act
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "Help me write another script"}],
    )
    query_analyst.ensure_session(session)
    result = query_analyst(input_data)
    # Assert - classification should be worker
    assert result.route_label == "worker"
    # on_complete should NOT spawn a new worker (existing one reused)
    query_analyst.on_complete(queue, result)
    worker_nodes = [n for n in queue.items if n.node_id == "worker"]
    assert len(worker_nodes) == 1, f"Expected exactly 1 worker, got {len(worker_nodes)}"
    # The existing worker should still be in the queue
    assert existing_worker in queue.items, "Existing worker must remain in queue"


def test_query_analyst_e2e_invalid_label_retry():
    """End-to-end: QueryAnalyst retries when LLM returns an invalid classification label.

    When the LLM returns a label not registered in RouteMap, NodeRetryPolicy
    should trigger a retry. After max retries, falls back to uncertain.

    NOTE: Default NodeRetryPolicy.max_attempts=3, so 3 retry cycles = 6 LLM calls max.
    The implementation MUST set retry_policy.on_retry_exhausted to trigger fallback
    to 'uncertain' (default is 'record_failure').
    """
    # Arrange - responses: analysis, bad_label for each retry cycle
    # Default NodeRetryPolicy.max_attempts=3, so 3 retry cycles = 6 LLM calls max
    # Each cycle: 1 analysis call + 1 classification call = 2 calls
    # We provide exactly 2 responses which will be reused for all 3 cycles
    responses = ["analysis", "bad_label"]
    mock_llm = MultiResponseMockLLM(responses)
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    _queue = NodeQueue(items=[query_analyst, response_node])
    session = Session()
    # Act
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "Do something weird"}],
    )
    query_analyst.ensure_session(session)
    result = query_analyst(input_data)
    # Assert - after retries exhausted, should fall back to uncertain
    assert result.route_label == "uncertain", (
        f"Expected uncertain fallback after invalid labels, got {result.route_label}"
    )


def test_query_analyst_e2e_deduplication():
    """End-to-end: QueryAnalyst prevents duplicate spawn when already active.

    When QueryAnalyst is already at the front of the queue and tries to
    classify again, it should not spawn a second QueryAnalyst.
    """
    # Arrange
    mock_llm = MultiResponseMockLLM(["I need to write a script", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[query_analyst, response_node])
    session = Session()
    # Act - first classification
    input_data = NodeInput(
        input_type="user_query",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )
    query_analyst.ensure_session(session)
    result = query_analyst(input_data)
    # on_complete should dispatch worker
    query_analyst.on_complete(queue, result)
    # Assert - only one query_analyst should exist in queue
    qa_nodes = [n for n in queue.items if n.node_id == "query_analyst"]
    assert len(qa_nodes) == 1, f"Expected exactly 1 query_analyst, got {len(qa_nodes)}"
    # Also test that a SECOND spawn attempt is rejected
    second_qa = TinyCUAQueryAnalystNode(node_id="query_analyst", config=config)
    with pytest.raises(RuntimeError, match="Node already in queue"):
        queue.add_front(second_qa)
