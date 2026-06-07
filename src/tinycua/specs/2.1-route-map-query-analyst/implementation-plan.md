# Implementation: RouteMap and Top-Level QueryAnalyst

This implementation adds a deterministic entry-point classification and routing system for TinyCUA. It introduces RouteMap as a lightweight dispatch table and TinyCUAQueryAnalystNode as the top-level entry DecisionNode that classifies user input into passthrough/worker/uncertain and routes the queue accordingly.

## Context

- **Spec Reference**: [spec.md](./spec.md)
- **Design Reference**: [design.md](./design.md)
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| [ ] **None** — no external services needed | | | |

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python 3.11+
- [ ] **Package manager**: uv
- [ ] **None** — no special tooling required

> **Note**: Environment prerequisites verified — the development environment already meets these requirements.

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/integration/test_query_analyst_integration.py
"""Integration tests for RouteMap and TinyCUAQueryAnalystNode."""

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import DecisionResult, ProcessNode

# NOTE: The following imports will resolve after implementation:
# from tinycua.loops.route_map import RouteMap
# from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
# from tinycua.models.classification import MandatoryPassthrough


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

    def mock_handler(queue, result):
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
    queue = NodeQueue(items=[query_analyst, response_node])
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
    """
    # Arrange - responses: analysis, bad_label, analysis2, bad_label2, ... (exceeds retries)
    responses = ["analysis"] * 10 + ["bad_label"] * 10  # more than enough for retries
    mock_llm = MultiResponseMockLLM(responses)
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[query_analyst, response_node])
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
```

### Key Test Scenarios

- [ ] **Scenario 1**: RouteMap dispatches labels to correct handlers — primary routing mechanism
- [ ] **Scenario 2**: QueryAnalyst classifies input into passthrough/worker/uncertain — core classification
- [ ] **Scenario 3**: MandatoryPassthrough precheck overrides LLM classification — deterministic continuation
- [ ] **Scenario 4**: Worker reuse — existing WorkerNode in queue is reused, not duplicated
- [ ] **Scenario 5**: Invalid label retry — unrecognized classification triggers retry, falls back to uncertain
- [ ] **Scenario 6**: QueryAnalyst deduplication — second spawn attempt is rejected
- [ ] **Edge case**: Invalid classification labels retry per NodeRetryPolicy — error handling

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for RouteMap, QueryAnalyst, MandatoryPassthrough — test error handling, edge cases, fallbacks
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify QueryAnalyst routing in a local environment with mock LLM endpoint
- [ ] Test queue bootstrap with QueryAnalyst at front

### Performance Considerations

- [ ] QueryAnalyst makes 2 LLM calls per input — acceptable for prototype

## Proposed Changes

### New Modules

#### [NEW] tinycua/loops/route_map.py

- **[Description]**: RouteMap class with register() and dispatch() methods
- **[Dependencies]**: None (standalone utility)

#### [NEW] tinycua/loops/query_analyst.py

- **[Description]**: TinyCUAQueryAnalystNode concrete DecisionNode
- **[Dependencies]**: DecisionNode, RouteMap, MandatoryPassthrough

#### [NEW] tinycua/models/classification.py

- **[Description]**: Classification labels, MandatoryPassthrough dataclass, QueryAnalystResponse
- **[Dependencies]**: None (data models)

### Modified Modules

#### [MODIFY] tinycua/loops/node.py

- **[Description]**: DecisionNode gains optional route_map attribute
- **[Breaking changes]**: None (additive change)

#### [MODIFY] tinycua/loops/tinycua_loop.py

- **[Description]**: Queue bootstrap uses QueryAnalyst at front instead of StubNode
- **[Breaking changes]**: Queue initialization changes

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| tinycua.loops.route_map | New | RouteMap dispatch table class |
| tinycua.loops.query_analyst | New | TinyCUAQueryAnalystNode concrete DecisionNode |
| tinycua.models.classification | New | Classification labels and data models |
| tinycua.loops.node | Modified | DecisionNode gains route_map attribute |
| tinycua.loops.tinycua_loop | Modified | Queue bootstrap uses QueryAnalyst at front |

## Data Model Changes

```python
# New types
RouteMap:
    routes: dict[str, Route]

Route:
    label: str
    handler: Callable[[NodeQueue, DecisionResult], None]

MandatoryPassthrough:
    target_node_id: str
    target_session_id: str | None
    reason: str
    payload: NodeInput | NodePayload | None
    allow_query_analyst_restart: bool = True

QueryAnalystResponse:
    user_query: str
    classification: str  # passthrough | worker | uncertain
    rationale: str | None
```

## API Changes

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| N/A | | No API changes — internal routing system |

### Modified Endpoints

| Method | Path | Change |
|--------|------|--------|
| N/A | | No API changes |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| None | | No new dependencies |

### Internal Dependencies

- [ ] Depends on existing DecisionNode, NodeQueue, TinyCUALoop infrastructure
- [ ] Blocks Milestone 2.2 (WorkerNode integration)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| QueryAnalyst two-step process makes 2 LLM calls per input | High | Acceptable for prototype; optimize later with classification tool |
| Worker reuse detection may miss edge cases | Medium | Simple linear scan of queue; test with various queue states |
| LLM may not reliably classify into exact labels | Medium | NodeRetryPolicy handles retries; fallback to uncertain |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-08 (ISSUE-002 fixed — integration test stubs added for worker reuse, retry, dedup)*