# Implementation: TinyCUAWorkerNode Optional LLM Decision

Implement optional LLM-based decision-making for TinyCUAWorkerNode. When a task already exists, the worker performs the two-step DecisionNode process (analysis → classification → validated RouteMap dispatch) to classify and dispatch to one of four route handlers: task_recreation, task_reanalysis, passthrough, or proceed_execution. Dynamic classification label adjustment includes `passthrough` only when worker-spawned nodes exist.

## Context

- **Spec Reference**: `./spec.md` — TinyCUAWorkerNode Optional LLM Decision (Milestone 2.3)
- **Design Reference**: `./design.md` — Two-step decision process, dynamic labels, route handlers
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies

### Running Services

- [ ] **None** — no external services needed

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python 3.11+, uv
- [ ] **Package manager**: uv
- [ ] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_worker_node_llm_decision_integration.py
"""Integration tests for TinyCUAWorkerNode LLM decision when task exists."""


async def test_worker_node_llm_decision_with_task_exists():
    """WorkerNode performs two-step LLM decision (analysis → classification) when task exists."""
    # Arrange
    session = _make_session(task="Write a sorting script")
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(config=config)
    worker.attach_session(session)
    queue = NodeQueue()
    queue.enqueue(worker)

    # Act
    result = worker("Help me write a script")

    # Assert — classification should be one of the dynamic labels
    assert result.route_label in [
        "task_recreation", "task_reanalysis", "passthrough", "proceed_execution"
    ]
    assert result.analysis_response is not None
    assert result.classification_response is not None


async def test_worker_node_dynamic_labels_with_worker_spawned():
    """Classification labels include passthrough when worker-spawned nodes exist."""
    # Arrange
    session = _make_session(task="Write a sorting script")
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(config=config)
    worker.attach_session(session)
    queue = NodeQueue()
    queue.enqueue(worker)
    # Simulate worker-spawned node
    spawned = _make_mock_node("spawned_task")
    queue.spawn_after_current([spawned])

    # Act
    labels = worker._get_classification_labels()

    # Assert
    assert "passthrough" in labels
    assert "task_recreation" in labels
    assert "task_reanalysis" in labels
    assert "proceed_execution" in labels


async def test_worker_node_dynamic_labels_without_worker_spawned():
    """Classification labels exclude passthrough when no worker-spawned nodes exist."""
    # Arrange
    session = _make_session(task="Write a sorting script")
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(config=config)
    worker.attach_session(session)
    queue = NodeQueue()
    queue.enqueue(worker)

    # Act
    labels = worker._get_classification_labels()

    # Assert
    assert "passthrough" not in labels
    assert "task_recreation" in labels
    assert "task_reanalysis" in labels
    assert "proceed_execution" in labels


async def test_worker_node_route_task_recreation():
    """task_recreation route handler clears worker-spawned nodes and spawns TaskAnalyzerNode with TaskInit/TaskCreate tools."""
    # Arrange
    session = _make_session(task="Write a sorting script")
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(config=config)
    worker.attach_session(session)
    queue = NodeQueue()
    queue.enqueue(worker)
    spawned = _make_mock_node("old_spawned")
    queue.spawn_after_current([spawned])

    result = DecisionResult(route_label="task_recreation", ...)

    # Act
    worker._route_task_recreation(queue, result)

    # Assert — old spawned node cleared, TaskAnalyzerNode spawned
    node_ids = [n.node_id for n in queue.items]
    assert "old_spawned" not in node_ids
    assert "task_analyzer" in node_ids


async def test_worker_node_route_task_reanalysis():
    """task_reanalysis route handler clears worker-spawned nodes and spawns TaskAnalyzerNode without TaskInit/TaskCreate."""
    # Arrange
    session = _make_session(task="Write a sorting script")
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(config=config)
    worker.attach_session(session)
    queue = NodeQueue()
    queue.enqueue(worker)
    spawned = _make_mock_node("old_spawned")
    queue.spawn_after_current([spawned])

    result = DecisionResult(route_label="task_reanalysis", ...)

    # Act
    worker._route_task_reanalysis(queue, result)

    # Assert — TaskAnalyzerNode spawned without task_init/task_create tools
    task_analyzer = [n for n in queue.items if n.node_id == "task_analyzer"][0]
    assert task_analyzer.mode == "reanalysis"  # or equivalent no-tools mode


async def test_worker_node_route_passthrough():
    """passthrough route handler advances queue and forwards input to next worker-spawned node."""
    # Arrange
    session = _make_session(task="Write a sorting script")
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(config=config)
    worker.attach_session(session)
    queue = NodeQueue()
    queue.enqueue(worker)
    spawned = _make_mock_node("next_node")
    queue.spawn_after_current([spawned])

    result = DecisionResult(route_label="passthrough", ...)

    # Act
    worker._route_passthrough(queue, result)

    # Assert — worker removed, next_node is now current
    assert queue.items[0].node_id == "next_node"


async def test_worker_node_route_proceed_execution():
    """proceed_execution route handler spawns TaskExecutor and ResultReviewer path."""
    # Arrange
    session = _make_session(task="Write a sorting script")
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(config=config)
    worker.attach_session(session)
    queue = NodeQueue()
    queue.enqueue(worker)

    result = DecisionResult(route_label="proceed_execution", ...)

    # Act
    worker._route_proceed_execution(queue, result)

    # Assert — execution path nodes spawned
    node_ids = [n.node_id for n in queue.items]
    assert "task_executor" in node_ids  # or equivalent


async def test_worker_node_invalid_label_retry():
    """Invalid classification labels trigger retry per NodeRetryPolicy."""
    # Arrange
    session = _make_session(task="Write a sorting script")
    config = NodeConfigBase(retry_policy=NodeRetryPolicy(max_attempts=3))
    worker = TinyCUAWorkerNode(config=config)
    worker.attach_session(session)

    # Mock LLM to return invalid label
    worker._call_llm = MagicMock(return_value=LLMResult(content="invalid_label", role="assistant"))

    # Act + Assert — should raise NodeExecutionError after retries
    with pytest.raises(NodeExecutionError):
        worker("Help me write a script")


async def test_worker_node_route_clear_ensures_terminal():
    """Route handlers calling clear_after_current() ensure terminal response path exists."""
    # Arrange
    session = _make_session(task="Write a sorting script")
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(config=config)
    worker.attach_session(session)
    queue = NodeQueue()
    queue.enqueue(worker)

    result = DecisionResult(route_label="task_recreation", ...)

    # Act
    worker._route_task_recreation(queue, result)

    # Assert — terminal node exists
    last_node = queue.items[-1]
    assert last_node.is_terminal
```

### Key Test Scenarios

- [ ] **Scenario 1**: WorkerNode performs two-step LLM decision when task exists — primary success criterion
- [ ] **Scenario 2**: Dynamic label adjustment includes/excludes passthrough based on worker-spawned nodes
- [ ] **Scenario 3**: Each route handler (task_recreation, task_reanalysis, passthrough, proceed_execution) executes correctly
- [ ] **Edge case**: Invalid classification labels retry per NodeRetryPolicy and raise after exhaustion

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for each new method (_has_worker_spawned_nodes, _get_classification_labels, route handlers)
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify WorkerNode LLM decision routing in a local environment with mock LLM endpoint
- [ ] Verify dynamic label adjustment with and without worker-spawned nodes
- [ ] Verify queue shape after each route visually

### Performance Considerations

- [ ] No performance-critical paths — all operations are queue mutations and LLM calls

## Proposed Changes

### Worker Module

#### MODIFY `src/tinycua/tinycua/loops/worker.py`

- **Add route labels to WorkerRouteLabel enum**: Add `task_recreation`, `task_reanalysis`, `passthrough`, `proceed_execution` to the enum
- **Rationale**: All five labels are required for Milestone 2.3 routing

- **Implement `_has_worker_spawned_nodes()`**: Check if worker-spawned nodes exist in the queue via `queue.find_worker_spawned_nodes()`
- **Rationale**: Needed for dynamic label adjustment

- **Implement `_get_classification_labels()`**: Return dynamic labels — always include task_recreation, task_reanalysis, proceed_execution; include passthrough only when worker-spawned nodes exist
- **Rationale**: LLM should only see valid classification options

- **Update `_build_default_route_map()`**: Register all five route labels with their handlers
- **Rationale**: Complete route map for all worker decisions

- **Implement `_route_task_recreation()`**: Clear worker-spawned nodes, spawn TaskAnalyzerNode with TaskInit/TaskCreate tools (LLM-assisted mode)
- **Rationale**: When worker classifies as task_recreation, existing task analysis is discarded and restarted with task creation tools

- **Implement `_route_task_reanalysis()`**: Clear worker-spawned nodes, spawn TaskAnalyzerNode without TaskInit/TaskCreate tools
- **Rationale**: When worker classifies as task_reanalysis, existing task analysis is discarded and restarted without task creation tools

- **Implement `_route_passthrough()`**: Call `queue.advance()` and forward input to next worker-spawned node without re-inserting WorkerNode
- **Rationale**: WorkerNode is transient; after forwarding, the next node takes over

- **Implement `_route_proceed_execution()`**: Spawn or continue TaskExecutor and ResultReviewer path
- **Rationale**: When task is ready for execution, ensure the execution path is established

- **Update `__call__()`**: Use dynamic labels when task exists instead of static `_DEFAULT_WORKER_LABELS`
- **Rationale**: LLM classification must see only valid labels based on current queue state

- **Update `__init__()`**: Initialize with all five labels (dynamic adjustment happens at call time)
- **Rationale**: Base labels are set at init; dynamic adjustment overrides at classification time

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `WorkerRouteLabel` | Modify | Add 4 new enum values (task_recreation, task_reanalysis, passthrough, proceed_execution) |
| `TinyCUAWorkerNode` | Modify | Add LLM decision flow, dynamic labels, 4 new route handlers, `_has_worker_spawned_nodes()`, `_get_classification_labels()` |
| `_build_default_route_map()` | Modify | Register all 5 route labels (was 1) |

## Data Model Changes

```python
# Modified enum — all five route labels
class WorkerRouteLabel(str, Enum):
    task_creation = "task_creation"           # Deterministic (Milestone 2.2)
    task_recreation = "task_recreation"       # LLM-assisted
    task_reanalysis = "task_reanalysis"       # LLM-assisted
    passthrough = "passthrough"               # LLM-assisted
    proceed_execution = "proceed_execution"   # LLM-assisted
```

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | — | No new dependencies |

### Internal Dependencies

- [x] Depends on Milestone 2.2 — deterministic routing (task_creation) already implemented
- [x] Depends on Milestone 2.1 — QueryAnalyst worker spawn/reuse
- [ ] Blocks Milestone 2.4 — TaskAnalyzerNode full behavior
- [ ] Blocks Milestone 3.2 — TaskExecutor and ResultReviewer

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Dynamic label adjustment could cause inconsistent LLM responses | Medium | Comprehensive unit tests for label adjustment; LLM sees only valid options |
| passthrough route handler could leave queue in inconsistent state | High | Defensive validation in route handler; ensure_terminal() call |
| proceed_execution handler could spawn duplicate executor/reviewer | Medium | Check for existing executor/reviewer before spawning |
| LLM classification could be ambiguous between task_recreation and task_reanalysis | Medium | Clear system prompt differentiation; NodeRetryPolicy for retries |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-08*
