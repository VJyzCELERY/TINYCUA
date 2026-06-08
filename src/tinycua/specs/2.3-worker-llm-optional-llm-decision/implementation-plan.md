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

# --- Standard library ---
import pytest
from unittest.mock import MagicMock

# --- Third-party / local ---
from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult, NodeRetryPolicy
from tinycua.loops.node import DecisionResult, NodeExecutionError, ProcessNode
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.session import Session
from tinycua.models.node_input import NodeInput


def _make_session_with_task(task: str = "Write a sorting script") -> Session:
    """Create a Session with an existing task (matches existing test patterns)."""
    session = Session()
    session.task = task
    return session


def _make_mock_node(node_id: str, is_terminal: bool = False) -> ProcessNode:
    """Create a lightweight mock node for queue testing.

    Returns a ProcessNode with the given node_id. Uses MagicMock for llm_client
    to avoid real LLM calls during queue operations.
    """
    config = NodeConfigBase(llm_client=MagicMock())
    return ProcessNode(node_id=node_id, config=config, is_terminal=is_terminal)


def test_worker_node_llm_decision_with_task_exists():
    """WorkerNode performs two-step LLM decision (analysis → classification) when task exists."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Mock two sequential LLM calls: analysis then classification
    mock_analysis = LLMResult(content="Worker should recreate task", role="assistant")
    mock_classification = LLMResult(content="task_recreation", role="assistant")
    mock_llm = MagicMock(side_effect=[mock_analysis, mock_classification])
    worker._call_llm = mock_llm

    # Act
    result = worker(input_data)

    # Assert — verify two LLM calls occurred (analysis → classification)
    assert mock_llm.call_count == 2
    assert result.route_label == "task_recreation"
    assert result.analysis_response == mock_analysis
    assert result.classification_response == mock_classification


def test_worker_node_dynamic_labels_with_worker_spawned():
    """Classification labels include passthrough when worker-spawned nodes exist."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    # Simulate worker-spawned node
    spawned = _make_mock_node("spawned_task")
    queue.spawn_after_current([spawned])

    # Act
    labels = worker._get_classification_labels(queue)

    # Assert
    assert "passthrough" in labels
    assert "task_recreation" in labels
    assert "task_reanalysis" in labels
    assert "proceed_execution" in labels


def test_worker_node_dynamic_labels_without_worker_spawned():
    """Classification labels exclude passthrough when no worker-spawned nodes exist."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    # Act
    labels = worker._get_classification_labels(queue)

    # Assert
    assert "passthrough" not in labels
    assert "task_recreation" in labels
    assert "task_reanalysis" in labels
    assert "proceed_execution" in labels


def test_worker_node_route_task_recreation():
    """task_recreation route handler clears worker-spawned nodes and spawns TaskAnalyzerNode with TaskInit/TaskCreate tools."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    spawned = _make_mock_node("old_spawned")
    queue.spawn_after_current([spawned])

    result = DecisionResult(
        route_label="task_recreation",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="task_recreation", role="assistant"),
    )

    # Act
    worker._route_task_recreation(queue, result)

    # Assert — old spawned node cleared, TaskAnalyzerNode spawned with correct mode
    node_ids = [n.node_id for n in queue.items]
    assert "old_spawned" not in node_ids
    assert "task_analyzer" in node_ids
    
    # CRITICAL: Assert mode is "analysis" (NOT "initial_analysis")
    task_analyzer = [n for n in queue.items if n.node_id == "task_analyzer"][0]
    assert task_analyzer.mode == "analysis"  # Includes TaskInit/TaskCreate


def test_worker_node_route_task_reanalysis():
    """task_reanalysis route handler clears worker-spawned nodes and spawns TaskAnalyzerNode without TaskInit/TaskCreate."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    spawned = _make_mock_node("old_spawned")
    queue.spawn_after_current([spawned])

    result = DecisionResult(
        route_label="task_reanalysis",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="task_reanalysis", role="assistant"),
    )

    # Act
    worker._route_task_reanalysis(queue, result)

    # Assert — TaskAnalyzerNode spawned without task_init/task_create tools
    task_analyzer = [n for n in queue.items if n.node_id == "task_analyzer"][0]
    assert task_analyzer.mode == "initial_analysis"  # Excludes TaskInit/TaskCreate


def test_worker_node_route_passthrough():
    """passthrough route handler advances queue and forwards input to next worker-spawned node."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]
    spawned = _make_mock_node("next_node")
    queue.spawn_after_current([spawned])

    result = DecisionResult(
        route_label="passthrough",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="passthrough", role="assistant"),
    )

    # Act
    worker._route_passthrough(queue, result)

    # Assert — worker removed, next_node is now current, input forwarded
    assert queue.items[0].node_id == "next_node"
    # Verify input was forwarded to next node (behavioral contract)
    # NOTE: Accesses private NodeQueue._inputs — intentional coupling for test purposes.
    # Refactor if NodeQueue changes input storage implementation.
    assert queue._inputs.get("next_node") is not None or queue.items[0]._input is not None
    # Assert — result object preserved (on_complete uses result.route_label for dispatch)
    assert result.route_label == "passthrough"


def test_worker_node_route_proceed_execution():
    """proceed_execution route handler ensures terminal response path (Milestone 2.3)."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    result = DecisionResult(
        route_label="proceed_execution",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="proceed_execution", role="assistant"),
    )

    # Act
    worker._route_proceed_execution(queue, result)

    # Assert — terminal response path exists
    assert queue.items[-1].is_terminal


def test_worker_node_invalid_label_retry():
    """Invalid classification labels trigger retry per NodeRetryPolicy."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(retry_policy=NodeRetryPolicy(max_attempts=3))
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    # Mock LLM to return invalid label
    mock_llm = MagicMock(return_value=LLMResult(content="invalid_label", role="assistant"))
    worker._call_llm = mock_llm

    # Act + Assert — should raise NodeExecutionError after retries
    with pytest.raises(NodeExecutionError):
        worker("Help me write a script")

    # Verify retry count matches max_attempts
    assert mock_llm.call_count == config.retry_policy.max_attempts


def test_worker_node_route_clear_ensures_terminal():
    """Route handlers calling clear_after_current() ensure terminal response path exists."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    result = DecisionResult(
        route_label="task_recreation",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="task_recreation", role="assistant"),
    )

    # Act
    worker._route_task_recreation(queue, result)

    # Assert — terminal node exists
    last_node = queue.items[-1]
    assert last_node.is_terminal


def test_worker_node_queue_invariant_query_analyst_first():
    """QueryAnalyst remains first in queue after WorkerNode dispatches to any route (FR-016)."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    query_analyst = _make_mock_node("query_analyst", is_terminal=False)
    queue = NodeQueue()
    queue.items = [query_analyst, worker]
    queue.current_index = 1  # WorkerNode is current

    result = DecisionResult(
        route_label="task_recreation",
        analysis_response=LLMResult(content="analysis text", role="assistant"),
        classification_response=LLMResult(content="task_recreation", role="assistant"),
    )

    # Act
    worker._route_task_recreation(queue, result)

    # Assert — QueryAnalyst remains first
    assert queue.items[0].node_id == "query_analyst"


def test_worker_node_latest_valid_verdict_wins():
    """Latest valid classification verdict determines route label when multiple tool calls occur (FR-005, SC-009)."""
    # Arrange
    session = _make_session_with_task(task="Write a sorting script")
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(config=config)
    worker.ensure_session(session)
    queue = NodeQueue()
    response_node = ProcessNode(node_id="response", config=config, is_terminal=True)
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Mock: analysis → first classification (invalid) → second classification (valid)
    mock_analysis = LLMResult(content="Worker should analyze task", role="assistant")
    # First classification call outputs invalid route label
    mock_classification_invalid = LLMResult(content="invalid_label", role="assistant")
    # Second classification call outputs valid route label
    mock_classification_valid = LLMResult(content="task_recreation", role="assistant")

    # Simulate multiple tool calls: analysis call returns, then classification tool calls
    mock_llm = MagicMock(side_effect=[
        mock_analysis,              # Analysis LLM call
        mock_classification_invalid, # Classification tool call 1 (invalid)
        mock_classification_valid,   # Classification tool call 2 (valid — wins)
    ])
    worker._call_llm = mock_llm

    # Act
    result = worker(input_data)

    # Assert — latest valid verdict wins (task_recreation, not invalid_label)
    assert result.route_label == "task_recreation"
    # Verify the classification result is from the latest valid call
    assert result.classification_response == mock_classification_valid
```

### Key Test Scenarios

- [ ] **Scenario 1** (SC-001, FR-001, FR-002): WorkerNode performs two-step LLM decision when task exists — primary success criterion
- [ ] **Scenario 2** (SC-002, FR-003): Dynamic label adjustment includes/excludes passthrough based on worker-spawned nodes
- [ ] **Scenario 3** (SC-003–SC-006, FR-007–FR-012): Each route handler (task_recreation, task_reanalysis, passthrough, proceed_execution) executes correctly
- [ ] **Scenario 4** (SC-007, FR-006): Invalid classification labels retry per NodeRetryPolicy and raise after exhaustion
- [ ] **Scenario 5** (SC-008, FR-011, FR-012): Terminal response path guaranteed after any route handler
- [ ] **Scenario 6** (SC-011, FR-013): Input preservation for downstream nodes
- [ ] **Scenario 7** (SC-010, FR-016): Queue invariant — QueryAnalyst remains first after WorkerNode dispatches
- [ ] **Scenario 8** (SC-009, FR-005): Latest valid verdict — when multiple tool calls occur, the latest valid verdict determines the route label

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

- **Implement `_route_proceed_execution()`**: Log classification and ensure terminal response path (TaskExecutor/ResultReviewer spawning deferred to Milestone 3.2)
- **Rationale**: TaskExecutor and ResultReviewer classes do not exist yet. Handler ensures queue reaches stable state with terminal response.

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

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Dynamic label adjustment could cause inconsistent LLM responses | Low | Medium | Comprehensive unit tests for label adjustment; LLM sees only valid options |
| passthrough route handler could leave queue in inconsistent state | Medium | High | Defensive validation in route handler; ensure_terminal() call |
| proceed_execution handler could leave queue without terminal path | Medium | High | ensure_terminal() call in all route handlers |
| NodeRetryPolicy could cause infinite loop for persistent invalid labels | Low | Low | Max retries limit (default 3); NodeExecutionError after exhaustion |
| LLM classification could be ambiguous between task_recreation and task_reanalysis | Medium | Medium | Clear system prompt differentiation; NodeRetryPolicy for retries |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-08*
