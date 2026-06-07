# Implementation: RouteMap and Top-Level QueryAnalyst

This implementation adds a deterministic entry-point classification and routing system for TinyCUA. It introduces RouteMap as a lightweight dispatch table and TinyCUAQueryAnalystNode as the top-level entry DecisionNode that classifies user input into passthrough/worker/uncertain and routes the queue accordingly.

## Context

- **Spec Reference**: [spec.md](./spec.md)
- **Design Reference**: [design.md](./design.md)
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| [x] **None** — no external services needed | | | |

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/integration/test_query_analyst_integration.py
"""Integration tests for RouteMap and TinyCUAQueryAnalystNode."""


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
    mock_llm = MockLLM(responses=["I need to write a script", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    session = Session()
    query_analyst.ensure_session(session)
    input_data = NodeInput(user_query="Help me write a script")
    # Act
    result = query_analyst(input_data)
    # Assert
    assert result.route_label == "worker"


def test_query_analyst_e2e_worker_route():
    """End-to-end: QueryAnalyst → WorkerNode → ResponseNode."""
    # Arrange
    mock_llm = MockLLM(responses=["I need to write a script", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    query_analyst = TinyCUAQueryAnalystNode(config=config)
    worker_node = ProcessNode(node_id="worker", config=config)
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue = NodeQueue(items=[query_analyst, worker_node, response_node])
    session = Session()
    # Act - execute query_analyst
    input_data = NodeInput(user_query="Help me write a script")
    query_analyst.ensure_session(session)
    result = query_analyst(input_data)
    # Assert - queue should have worker node ready
    assert queue.current == query_analyst
    # After on_complete, queue should be mutated
    query_analyst.on_complete(queue, result)
    # Worker node should be in queue
    assert any(node.node_id == "worker" for node in queue.items)


def test_query_analyst_mandatory_passthrough_precheck():
    """MandatoryPassthrough overrides LLM classification."""
    # Arrange
    mock_llm = MockLLM(responses=["This should be ignored", "worker"])
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
        user_query="Continue previous task",
        mandatory_passthrough=mandatory,
    )
    # Act
    result = query_analyst(input_data)
    # Assert - should route to passthrough, not worker
    assert result.route_label == "passthrough"
```

### Key Test Scenarios

- [x] **Scenario 1**: RouteMap dispatches labels to correct handlers — primary routing mechanism
- [x] **Scenario 2**: QueryAnalyst classifies input into passthrough/worker/uncertain — core classification
- [x] **Scenario 3**: MandatoryPassthrough precheck overrides LLM classification — deterministic continuation
- [x] **Edge case**: Invalid classification labels retry per NodeRetryPolicy — error handling

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [x] Unit tests for RouteMap, QueryAnalyst, MandatoryPassthrough — test error handling, edge cases, fallbacks
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] Verify QueryAnalyst routing in a local environment with mock LLM endpoint
- [x] Test queue bootstrap with QueryAnalyst at front

### Performance Considerations

- [x] QueryAnalyst makes 2 LLM calls per input — acceptable for prototype

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

- [x] Depends on existing DecisionNode, NodeQueue, TinyCUALoop infrastructure
- [x] Blocks Milestone 2.2 (WorkerNode integration)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| QueryAnalyst two-step process makes 2 LLM calls per input | High | Acceptable for prototype; optimize later with classification tool |
| Worker reuse detection may miss edge cases | Medium | Simple linear scan of queue; test with various queue states |
| LLM may not reliably classify into exact labels | Medium | NodeRetryPolicy handles retries; fallback to uncertain |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-08*