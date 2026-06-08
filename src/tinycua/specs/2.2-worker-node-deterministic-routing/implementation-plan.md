# Implementation: TinyCUAWorkerNode Deterministic Routing and TaskCreate

Implements deterministic task-creation routing for TinyCUAWorkerNode so that when no task exists, the worker can initialize task creation and analysis without requiring LLM decisions. Introduces TinyCUATaskCreateNode as a concrete ProcessNode for first-time root task creation.

## Context

- **Spec Reference**: `./spec.md` — TinyCUAWorkerNode Deterministic Routing and TaskCreate
- **Design Reference**: `./design.md` — WorkerNode architecture and TaskCreateNode design
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+, uv
- [x] **Package manager**: uv

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

> **Note**: Import paths below are aspirational and should be validated against actual module structure during implementation. WorkerNode, TaskCreateNode, and TaskAnalyzerNode do not exist yet — their import paths may change.

```python
# Test file: src/tinycua/tests/integration/test_worker_node_task_creation_integration.py
"""Integration tests for WorkerNode deterministic task_creation routing."""


import pytest
from unittest.mock import MagicMock
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.node import ProcessNode, DecisionResult
from tinycua.config.types import LLMResult
from tinycua.models.session import Session
from tinycua.models.node_input import NodeInput


def test_worker_node_routes_to_task_creation_when_no_task():
    """WorkerNode routes to task_creation deterministically when no task exists."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    session.task = None  # No task exists

    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Act
    result = worker(input_data)

    # Assert
    assert result.route_label == "task_creation"


def test_worker_node_does_not_use_llm_for_task_creation():
    """WorkerNode task_creation route does not trigger LLM decision."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    session.task = None

    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Act
    _ = worker(input_data)

    # Assert — LLM client should NOT have been called
    config.llm_client.assert_not_called()


def test_task_create_node_creates_root_task():
    """TaskCreateNode creates root task using TaskInit/TaskCreate tools."""
    # Arrange
    from tinycua.loops.task_create import TinyCUATaskCreateNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
    task_create.ensure_session(session)

    # Act
    # TaskCreateNode uses LLM to create task — mock the LLM response
    mock_llm = MagicMock()
    mock_llm.return_value = {
        "content": "Task created: Write a script",
        "role": "assistant",
        "tool_calls": [],
    }
    config.llm_client = mock_llm

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )
    _ = task_create(input_data)

    # Assert
    assert session.task is not None


def test_task_create_node_advances_queue_to_task_analyzer():
    """TaskCreateNode advances queue with TaskAnalyzerNode as next node."""
    # Arrange
    from tinycua.loops.task_create import TinyCUATaskCreateNode
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
    task_create.ensure_session(session)

    queue = NodeQueue()
    task_analyzer = ProcessNode(node_id="task_analyzer", config=config)
    queue.items = [task_create, task_analyzer]

    # Mock LLM to return a successful response
    mock_llm = MagicMock()
    mock_llm.return_value = {
        "content": "Task created",
        "role": "assistant",
        "tool_calls": [],
    }
    config.llm_client = mock_llm

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )
    result = task_create(input_data)

    # Act — on_complete should advance queue
    task_create.on_complete(queue, result)

    # Assert
    assert queue.current.node_id == "task_analyzer"


def test_task_analyzer_no_task_tools_in_initial_analysis():
    """TaskAnalyzerNode (initial_analysis) does not have TaskInit/TaskCreate tools."""
    # Arrange
    from tinycua.loops.task_analyzer import TinyCUATaskAnalyzerNode
    from tinycua.config.node_config import NodeConfigBase

    config = NodeConfigBase()
    task_analyzer = TinyCUATaskAnalyzerNode(
        node_id="task_analyzer",
        config=config,
        mode="initial_analysis",
    )

    # Assert
    assert "TaskInit" not in task_analyzer.tool_scope
    assert "TaskCreate" not in task_analyzer.tool_scope


def test_worker_node_detects_worker_spawned_nodes():
    """WorkerNode detects worker-spawned nodes in queue."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    spawned_node = ProcessNode(node_id="task_create", config=config)
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, spawned_node, response_node]

    # Act
    spawned_nodes = worker._detect_worker_spawned_nodes(queue)

    # Assert
    assert len(spawned_nodes) == 1
    assert spawned_nodes[0].node_id == "task_create"


def test_worker_node_reuse_detection():
    """Existing WorkerNode is recognized in worker-owned segment."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    # Act
    existing = queue.find_existing_worker_node()

    # Assert
    assert existing is worker


def test_worker_node_preserves_input():
    """Original input query is preserved for downstream nodes."""
    # Arrange
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    session.task = None
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Act
    result = worker(input_data)

    # Assert — the original input content should be preserved in session_context
    # for downstream nodes to access
    context_contents = [ctx.get("content", "") for ctx in session.session_context]
    assert any("task_creation" in c for c in context_contents)
    # Also verify original input content is accessible
    assert result is not None


def test_clear_after_current_ensures_terminal():
    """Route handler ensures terminal response after clear."""
    # Arrange
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.worker import TinyCUAWorkerNode
    from tinycua.config.node_config import NodeConfigBase

    session = Session()
    config = NodeConfigBase()
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    worker.ensure_session(session)

    queue = NodeQueue()
    response_node = ProcessNode(
        node_id="response", config=config, is_terminal=True,
    )
    queue.items = [worker, response_node]

    # Act — clear after current removes terminal
    queue.clear_after_current()

    # Assert — ensure_terminal should add it back
    default_response = ProcessNode(
        node_id="default_response", config=config, is_terminal=True,
    )
    queue.ensure_terminal(default_response)

    assert queue.items[-1].is_terminal
```

### Key Test Scenarios

- [ ] **Scenario 1**: WorkerNode routes to `task_creation` when no task exists — this is the primary success criterion for deterministic routing
- [ ] **Scenario 2**: WorkerNode does NOT call LLM for task_creation — verifies the deterministic behavior
- [ ] **Scenario 3**: TaskCreateNode creates root task and advances queue — verifies the full task creation flow
- [ ] **Edge case**: `clear_after_current()` removes terminal ResponseNode — verifies `ensure_terminal()` call

### Error Scenario Tests

- [ ] **test_task_create_node_failure_retries**: TaskCreateNode failure triggers NodeRetryPolicy; after max retries, error propagates to WorkerNode
- [ ] **test_worker_node_empty_input_passes_through**: Empty or null input reaches WorkerNode without crash; original input is preserved for downstream
- [ ] **test_clear_after_current_without_ensure_terminal**: Verify the actual failure mode when ensure_terminal is NOT called — queue has no terminal node
- [ ] **test_stale_worker_spawned_nodes_detection**: Worker-spawned nodes detected as stale when WorkerNode is re-entered with existing spawned nodes

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for WorkerNode, TaskCreateNode, TaskAnalyzerNode, NodeQueue additions
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify WorkerNode deterministic routing in a local environment with mock LLM endpoint
- [ ] Verify queue shape after `task_creation` route visually

### Performance Considerations

- [ ] No performance impact — deterministic routing avoids unnecessary LLM calls

## Proposed Changes

### WorkerNode Module

#### [NEW] `src/tinycua/tinycua/loops/worker.py`

- **Description**: Concrete DecisionNode for task planning and execution orchestration
- **Dependencies**: `DecisionNode`, `RouteMap`, `NodeQueue`, `Session`

#### [MODIFY] `src/tinycua/tinycua/loops/query_analyst.py`

- **Description**: Replace placeholder `ProcessNode` in `route_worker()` with actual `TinyCUAWorkerNode` import. Also refactor `find_existing_worker()` (line 131) to delegate to `NodeQueue.find_existing_worker_node()` to avoid duplicating worker-node lookup logic.
- **Rationale**: Currently spawns a generic ProcessNode; must spawn the real WorkerNode. `find_existing_worker()` and `find_existing_worker_node()` have overlapping semantics — NodeQueue should be the source of truth.

### TaskCreateNode Module

#### [NEW] `src/tinycua/tinycua/loops/task_create.py`

- **Description**: ProcessNode for deterministic first-time root task creation with TaskInit/TaskCreate tool scope
- **Dependencies**: `ProcessNode`, `NodeQueue`, `Session`

### TaskAnalyzerNode Module

#### [NEW] `src/tinycua/tinycua/loops/task_analyzer.py`

- **Description**: ProcessNode with `mode=initial_analysis` that excludes TaskInit/TaskCreate tools
- **Dependencies**: `ProcessNode`, `NodeQueue`

### NodeQueue Extensions

#### [MODIFY] `src/tinycua/tinycua/loops/node_queue.py`

- **Description**: Add `find_worker_spawned_nodes()` and `find_existing_worker_node()` methods. `clear_after_current()` (line 121) and `ensure_terminal()` (line 183) already exist.
- **Rationale**: WorkerNode needs to detect worker-spawned nodes for stale detection and reuse

### Module Exports

#### [MODIFY] `src/tinycua/tinycua/loops/__init__.py`

- **Description**: Export `TinyCUAWorkerNode`, `TinyCUATaskCreateNode`, `TinyCUATaskAnalyzerNode`
- **Rationale**: Make new nodes available for imports

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.loops.worker.TinyCUAWorkerNode` | New | Concrete DecisionNode with route_map for task_creation routing |
| `tinycua.loops.task_create.TinyCUATaskCreateNode` | New | ProcessNode for deterministic root task creation |
| `tinycua.loops.task_analyzer.TinyCUATaskAnalyzerNode` | New | ProcessNode with mode=initial_analysis without TaskInit/TaskCreate tools |
| `tinycua.loops.node_queue.NodeQueue` | Modified | Add `find_worker_spawned_nodes()` and `find_existing_worker_node()` for worker-spawned-node detection; `clear_after_current()` and `ensure_terminal()` already exist |
| `tinycua.loops.query_analyst.TinyCUAQueryAnalystNode` | Modified | Use real WorkerNode in route_worker(); refactor `find_existing_worker()` to delegate to `NodeQueue.find_existing_worker_node()` |

## Data Model Changes

```python
# WorkerNode route labels (subset implemented in this milestone)
class WorkerRouteLabel(str, Enum):
    task_creation = "task_creation"
    task_recreation = "task_recreation"        # Deferred to 2.3
    task_reanalysis = "task_reanalysis"        # Deferred to 2.3
    passthrough = "passthrough"                # Deferred to 2.3
    proceed_execution = "proceed_execution"    # Deferred to 2.3

# TaskCreateNode output: plain string in session.task (no structured dataclass)
# Session.task: str | None — stores LLM response content as a raw string.
# Task metadata (task_id, task_summary, created_at) is not available at this stage.
```

## API Changes

### New Classes

| Class | Parent | Description |
|-------|--------|-------------|
| `TinyCUAWorkerNode` | `DecisionNode` | Worker routing with deterministic task_creation |
| `TinyCUATaskCreateNode` | `ProcessNode` | Root task creation with TaskInit/TaskCreate tools |
| `TinyCUATaskAnalyzerNode` | `ProcessNode` | Analysis without task tools (initial_analysis mode) |

### Modified Classes

| Class | Change |
|-------|--------|
| `NodeQueue` | Added `find_worker_spawned_nodes()` and `find_existing_worker_node()` (existing: `clear_after_current()`, `ensure_terminal()`) |

## Dependencies

### External Dependencies

- [x] None — uses existing project dependencies

### Internal Dependencies

- [x] Depends on Milestone 2.1 (QueryAnalyst worker spawn/reuse)
- [ ] Blocks Milestone 2.3 (LLM worker decisions)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| WorkerNode route_map incomplete for non-task_creation routes | Medium | Phase 2 defers remaining routes; only task_creation is required |
| TaskCreateNode retry loop could block queue | Low | NodeRetryPolicy with max retries; failure propagates to WorkerNode |
| `ensure_terminal()` called incorrectly by route handlers | High | Comprehensive unit tests for all route handlers; code review checklist |
| Worker-spawned-node detection misses nodes due to queue ordering | High | Tests verify detection with various queue shapes; consistent with QueryAnalyst logic |

## Design Decisions

These decisions are resolved from design.md open questions and must be honored during implementation:

1. **WorkerNode uses retry, not default route, for unrecognized labels** — WorkerNode always retries via NodeRetryPolicy. No fallback route. Only `task_creation` is valid in this milestone; revisit in 2.3.
2. **TaskCreateNode emits INFO-level log for task creation** — Log task ID and summary at INFO level for observability. No external event infrastructure required.

## Rollback Strategy

If implementation introduces regressions, revert in this order:

1. **New modules** (`worker.py`, `task_create.py`, `task_analyzer.py`) — safe to remove without impact on existing code
2. **`NodeQueue` changes** — additive only (new methods: `find_worker_spawned_nodes()`, `find_existing_worker_node()`); `clear_after_current()` and `ensure_terminal()` already exist; safe to revert independently
3. **`query_analyst.py` modification** — riskiest change (replaces `ProcessNode` with `TinyCUAWorkerNode` in `route_worker()`); should be a single atomic commit that can be reverted in isolation
4. **`__init__.py` export changes** — revert cleanly when new modules are removed

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-08*
