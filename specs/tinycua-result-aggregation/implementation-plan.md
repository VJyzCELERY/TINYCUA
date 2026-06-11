# Implementation: TinyCUAResultAggregationNode

This implementation introduces `TinyCUAResultAggregationNode` — a `ProcessNode` that performs read-only traversal of the accepted root task tree, consolidates task results/artifacts/reviewer decisions, and produces an `AggregatedResult` for `ResponseNode`. Also wires root-task-accept routing in `TinyCUALoop` so that when `ResultReviewer` accepts the root task, the queue advances through `ResultAggregationNode` → `ResponseNode`.

## Context

- **Spec Reference**: `specs/tinycua-result-aggregation/spec.md`
- **Design Reference**: `specs/tinycua-result-aggregation/design.md`
- **Priority**: P0
- **Estimated Effort**: M

## Environment Pre-requisites

> No special environment setup is needed — all dependencies already exist in the `tinycua` subproject.

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [ ] **None** — test fixtures are built programmatically in test files

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **Additional CLI tools**: pytest
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

> **Note**: `Task` and `TaskResult` should be imported from `tinycua.models.task`. These imports are used in test helpers and are shown in the test code snippets below for clarity.

```python
# Test file: src/tinycua/tests/integration/test_result_aggregation_integration.py
"""Integration tests for TinyCUAResultAggregationNode."""

import pytest
from tinycua.config.types import LLMResult
from tinycua.models.task import Task, TaskResult
from tinycua.loops.result_aggregation import (
    TinyCUAResultAggregationNode,
    AggregatedResult,
)
from tinycua.loops.tinycua_loop import TinyCUALoop


def _build_completed_root_task_tree():
    """Build a completed root task tree with TaskResult on at least one child."""
    return Task(
        task_id="root", title="Root",
        status="done",
        children=[
            Task(
                task_id="child_1", title="Child 1", status="done",
                result=TaskResult(
                    task_id="child_1",
                    summary="Done successfully",
                    execution_status="succeeded",
                ),
            ),
        ],
    )


def _build_session(task):
    """Build a minimal Session for ensure_session."""
    from tinycua.models.session import Session
    session = Session()
    session.task = task  # Match design.md:210 access pattern
    return session


def test_aggregation_produces_aggregated_result():
    """Given a completed root task tree where root task is done,
    When TinyCUAResultAggregationNode is invoked,
    Then it produces an AggregatedResult with task summaries and artifacts."""
    # Arrange — build a completed root task tree
    root_task = _build_completed_root_task_tree()
    node = TinyCUAResultAggregationNode()
    node.ensure_session(_build_session(root_task))

    # Act
    result = node._consolidate(list(node._traverse_bfs_right_to_left(root_task)))

    # Assert
    assert isinstance(result, AggregatedResult)
    assert result.root_task_id == root_task.task_id
    assert len(result.task_summaries) >= 1
    assert any("not_executed" in s or ":" in s for s in result.task_summaries)
    assert len(result.accepted_results) >= 1


def test_bfs_right_to_left_traversal():
    """Given a root task tree with nested accepted tasks at multiple depths,
    When the aggregation node traverses,
    Then it visits children right-to-left / most-recent-first."""
    # Arrange — build tree: root -> [child_1 (older), child_2 (newer)]
    # Tree: root -> child_1 -> grandchild_1
    #            -> child_2 -> grandchild_2
    root = Task(
        task_id="root", title="Root",
        children=[
            Task(task_id="child_1", title="Child 1 (older)", status="done",
                 children=[Task(task_id="grandchild_1", title="GC1", status="done")]),
            Task(task_id="child_2", title="Child 2 (newer)", status="done",
                 children=[Task(task_id="grandchild_2", title="GC2", status="done")]),
        ],
        status="done",
    )
    node = TinyCUAResultAggregationNode()

    # Act — traverse and collect task IDs in order visited
    visited_ids = [t.task_id for t in node._traverse_bfs_right_to_left(root)]

    # Assert — right-to-left BFS: child_2 before child_1
    # Level 0: root
    # Level 1: child_2, child_1 (right-to-left)
    # Level 2: grandchild_2, grandchild_1
    child_2_idx = visited_ids.index("child_2")
    child_1_idx = visited_ids.index("child_1")
    assert child_2_idx < child_1_idx, "child_2 (newer) should be visited before child_1 (older)"

    gc_2_idx = visited_ids.index("grandchild_2")
    gc_1_idx = visited_ids.index("grandchild_1")
    assert gc_2_idx < gc_1_idx, "grandchild_2 should be visited before grandchild_1"


def test_early_termination():
    """Given sufficient response-ready context is found early,
    When the aggregation node inspects tasks,
    Then it may stop early without exhaustive BFS."""
    root = Task(
        task_id="root", title="Root",
        status="done",
        children=[
            Task(task_id="child_1", title="Child 1", status="done"),
            Task(task_id="child_2", title="Child 2", status="done"),
            Task(task_id="child_3", title="Child 3", status="done"),
        ],
    )
    # Threshold of 1 — stop after first node is inspected (root itself)
    node = TinyCUAResultAggregationNode()
    result = node._consolidate(list(node._traverse_bfs_right_to_left(root, max_inspected_tasks=1)))
    assert len(result.task_summaries) == 1  # Only root inspected, children skipped
    assert all(":" in s or "not_executed" in s for s in result.task_summaries)
    # Traversal stopped early (not exhaustive) — verified by exact count


def test_on_complete_advances_queue():
    """Given TinyCUAResultAggregationNode produces an AggregatedResult,
    When on_complete is called,
    Then the queue advances to the next node."""
    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.response_node import ResponseNode

    queue = NodeQueue(items=[
        TinyCUAResultAggregationNode(),
        ResponseNode(),
    ])
    response = LLMResult(content="", metadata={"aggregated_result": AggregatedResult(
        root_task_id="test", task_summaries=[], accepted_results=[],
        artifacts=[], final_context="", response_continuation="", metadata={},
    )})

    current_before = queue.current
    node = queue.current
    node.on_complete(queue, response)

    assert queue.current is not None
    assert queue.current.node_id != current_before.node_id


def test_read_only_guarantee():
    """Given a completed task tree,
    When the aggregation node traverses,
    Then it does NOT mutate any task's status, result, or children."""
    child = Task(task_id="child", title="Child", status="done")
    root = Task(task_id="root", title="Root", children=[child], status="done")
    original_child_status = child.status
    original_child_result = child.result

    node = TinyCUAResultAggregationNode()
    list(node._traverse_bfs_right_to_left(root))  # Materialize the generator

    assert child.status == original_child_status
    assert child.result == original_child_result


def test_empty_task_tree():
    """Given a root task with no children,
    When the aggregation node is invoked,
    Then it produces an AggregatedResult from the single root task."""
    root = Task(task_id="root", title="Root only", status="done")
    node = TinyCUAResultAggregationNode()

    result = node._consolidate(list(node._traverse_bfs_right_to_left(root)))
    assert result.root_task_id == "root"
    assert len(result.task_summaries) == 1
    assert all(":" in s or "not_executed" in s for s in result.task_summaries)


def test_tasks_with_missing_results():
    """Given some tasks have no result (were never executed),
    When the aggregation node traverses,
    Then it records 'not_executed' status instead of failing."""
    child_executed = Task(
        task_id="executed", title="Executed", status="done",
        result=TaskResult(task_id="executed", summary="Done", execution_status="succeeded"),
    )
    child_not_executed = Task(
        task_id="not_exec", title="Not Executed", status="pending",
    )
    root = Task(task_id="root", title="Root", children=[child_executed, child_not_executed], status="done")

    node = TinyCUAResultAggregationNode()
    result = node._consolidate(list(node._traverse_bfs_right_to_left(root)))
    # Should not raise; not_executed tasks are skipped gracefully
    assert len(result.task_summaries) >= 1
    assert all(":" in s or "not_executed" in s for s in result.task_summaries)


def _build_loop_with_active_task() -> TinyCUALoop:
    """Build a TinyCUALoop with one active task for testing.

    Replicates the helper pattern from
    tests/integration/test_executor_reviewer_integration.py.
    """
    task = Task(task_id="test-1", title="Test Task", description="Test task", status="in_progress")
    queue = NodeQueue()
    loop = TinyCUALoop(queue=queue)
    loop.root_task = task
    loop._active_task_id = "test-1"
    return loop


def test_on_reviewer_accept_returns_true_for_root():
    """Given a root task with all children done,
    When _on_reviewer_accept is called on the root task,
    Then it returns True (root task is done).

    Queue mutation is NOT the responsibility of _on_reviewer_accept —
    that happens in ResultReviewer.on_complete (see
    test_root_accept_routes_to_aggregation).
    """
    # Use the helper to set up a loop with an active task, then replace it
    # with a proper root + child tree
    loop = _build_loop_with_active_task()
    root = Task(task_id="root", title="Root", status="in_progress",
                children=[Task(task_id="child", title="Child", status="done")])
    loop.root_task = root
    loop._active_task_id = "root"

    # Act
    is_root_done = loop._on_reviewer_accept(root)

    # Assert — root is done
    assert is_root_done is True


def test_root_accept_routes_to_aggregation():
    """Given a root task is accepted,
    When ResultReviewer.on_complete is called with outcome=accept,
    Then _on_reviewer_accept is called and _route_to_aggregation is invoked
    to mutate the queue with aggregation → response nodes.

    Tests the full routing path via ResultReviewer.on_complete, not the
    low-level _on_reviewer_accept handler.
    """
    from unittest.mock import MagicMock

    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode

    # Build loop with active root task (all children done so root becomes
    # done when accepted)
    root = Task(task_id="root", title="Root", status="in_progress",
                children=[Task(task_id="child", title="Child", status="done")])
    queue = NodeQueue()
    loop = TinyCUALoop(queue=queue)
    loop.root_task = root
    loop._active_task_id = "root"

    # Mock the loop so we can intercept _route_to_aggregation without
    # requiring TinyCUAResultAggregationNode or ResponseNode to exist yet
    mock_loop = MagicMock()
    mock_loop._on_reviewer_accept = loop._on_reviewer_accept  # real handler
    mock_loop._route_to_aggregation = MagicMock()
    mock_loop._reviewer_retry_state = loop._reviewer_retry_state

    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)
    decision_data = {"outcome": "accept", "rationale": "Root complete"}
    response = LLMResult(
        content='{"outcome": "accept"}',
        metadata={"reviewer_decision": decision_data, "active_task": root},
    )

    # Act
    reviewer.on_complete(queue, response)

    # Assert — _on_reviewer_accept was called (handles task status changes)
    mock_loop._on_reviewer_accept.assert_called_once_with(root)
    # Assert — _route_to_aggregation was invoked (queue mutation: clear + spawn)
    mock_loop._route_to_aggregation.assert_called_once_with(queue)


def test_force_accept_on_threshold_routes_to_aggregation():
    """Given retry threshold is reached,
    When ResultReviewer.on_complete is called with outcome=retry,
    Then _on_reviewer_accept is called (force-accept) and _route_to_aggregation
    is invoked when root task is done."""
    from unittest.mock import MagicMock

    from tinycua.loops.node_queue import NodeQueue
    from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode

    root = Task(task_id="root", title="Root", status="in_progress",
                children=[Task(task_id="child", title="Child", status="done")])
    queue = NodeQueue()
    loop = TinyCUALoop(queue=queue)
    loop.root_task = root
    loop._active_task_id = "root"
    # Exhaust retry threshold
    loop._reviewer_retry_state.retry_count = loop._reviewer_retry_state.threshold

    mock_loop = MagicMock()
    mock_loop._on_reviewer_accept = loop._on_reviewer_accept
    mock_loop._route_to_aggregation = MagicMock()
    mock_loop._reviewer_retry_state = loop._reviewer_retry_state

    reviewer = TinyCUAResultReviewerNode(loop=mock_loop)
    decision_data = {"outcome": "retry", "rationale": "Threshold reached"}
    response = LLMResult(
        content='{"outcome": "retry"}',
        metadata={"reviewer_decision": decision_data, "active_task": root},
    )

    reviewer.on_complete(queue, response)

    mock_loop._on_reviewer_accept.assert_called_once_with(root)
    mock_loop._route_to_aggregation.assert_called_once_with(queue)
```

### Key Test Scenarios

- [x] **Scenario 1**: Aggregation produces valid `AggregatedResult` from a completed root task tree
- [x] **Scenario 2**: BFS right-to-left / most-recent-first traversal order
- [x] **Scenario 3**: Early termination when sufficient context gathered
- [x] **Scenario 4**: `on_complete` advances the queue properly
- [x] **Edge case**: Read-only guarantee — no mutation of task tree
- [x] **Edge case**: Empty task tree (root with no children)
- [x] **Edge case**: Tasks with missing results/artifacts are handled gracefully
- [x] **Integration**: Full path — root task accept → aggregation → response

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for `AggregatedResult` construction — test all fields, empty fields, serialization
- [ ] Unit tests for `_traverse_bfs_right_to_left` — test multi-level trees, early termination, empty trees
- [ ] Unit tests for `_consolidate` — test with various combinations of results/artifacts/decisions
- [ ] Unit tests for `TinyCUAResultAggregationNode.__call__` — test guard, propagation, error cases
- [ ] Unit tests for `on_complete` — verify queue advancement and session context recording
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] N/A — all behavior is verifiable through automated tests.

### Performance Considerations

- [ ] Traversal of deep/wide task trees should be bounded by configurable `max_inspected_tasks`
- [ ] Aggregation produces no new LLM content — purely mechanical consolidation

## Proposed Changes

### `tinycua.loops.result_aggregation` (New Module)

#### [NEW] `src/tinycua/tinycua/loops/result_aggregation.py`

- **[Description]**: New module containing `AggregatedResult` dataclass and `TinyCUAResultAggregationNode` class.
- **[Dependencies]**: `tinycua.loops.node` (ProcessNode), `tinycua.models.task` (Task, TaskResult), `tinycua.config.types` (LLMResult), `tinycua.models.node_input` (NodeInputLike), `tinycua.loops.node_queue` (NodeQueue), `tinycua.config.node_config` (NodeConfigBase).

**`AggregatedResult` dataclass**:
```python
@dataclass
class AggregatedResult:
    root_task_id: str
    task_summaries: list[str]
    accepted_results: list[TaskResult]
    artifacts: list[dict[str, Any]]
    final_context: str
    response_continuation: str
    metadata: dict
```

**`TinyCUAResultAggregationNode` class**:
- Extends `ProcessNode` with `node_id="result_aggregation"`.
- `__init__(self, node_id="result_aggregation", config=None, loop=None)` — accepts optional `loop` reference for access to `root_task` and `session`.
- `__call__(self, input: NodeInputLike) -> LLMResult`:
  1. Guard: assert `session` is attached and root task is done (`session.task` / `loop.root_task` is done).
  2. Traverse task tree via `_traverse_bfs_right_to_left(root_task)` generator.
  3. Consolidate traversal results via `_consolidate(traversal_results)` → `AggregatedResult`.
  4. Record result to session context / response metadata.
  5. `propagate()`.
  6. Return `LLMResult` with `AggregatedResult` in `metadata["aggregated_result"]`.
- `_traverse_bfs_right_to_left(task: Task, max_inspected_tasks: int | None = None, context_sufficient_fn: Callable | None = None) -> Iterator[Task]`:
  - Generator-based guided BFS right-to-left / most-recent-first.
  - Uses `collections.deque` with a reversed children queue.
  - Supports early termination via `stop_traversal` attribute or `max_inspected_tasks` threshold.
  - Inspects each visited task's context, result, artifacts, and reviewer decisions.
  - Yields each inspected task for the caller to consume.
- `_consolidate(traversal_results: list[Task]) -> AggregatedResult`:
  - Builds `AggregatedResult` from inspected tasks.
  - Collects: `root_task_id`, `task_summaries`, `accepted_results`, `artifacts`, `final_context`, `response_continuation`, `metadata`.
- `on_complete(self, queue: NodeQueue, response: LLMResult) -> None`:
  - Calls `queue.advance()` to advance to `ResponseNode`.
  - Logs completion.

#### [MODIFY] `src/tinycua/tinycua/loops/__init__.py`

- **[Description]**: Add imports for `TinyCUAResultAggregationNode` and `AggregatedResult` from the new module.
- **[Rationale]**: Expose the new classes via the public `tinycua.loops` namespace.
- **Changes**:
  - Add: `from tinycua.loops.result_aggregation import TinyCUAResultAggregationNode, AggregatedResult`
  - Add to `__all__`: `"TinyCUAResultAggregationNode"`, `"AggregatedResult"`

#### [MODIFY] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **[Description]**: Wire root-task-accept → aggregation routing in `_on_reviewer_accept`.
- **[Rationale]**: When `ResultReviewer` accepts the root task (no parent), the loop needs to route to `ResultAggregationNode` then `ResponseNode`.
- **Changes**:
  - **Add import**: `from tinycua.loops.result_aggregation import TinyCUAResultAggregationNode`
  - **Modify `_on_reviewer_accept`**: Currently returns a bool indicating whether root is done. We need to also handle queue mutation when root is done. The method should:
    1. Keep existing logic (mark task done, walk parent chain, check root).
    2. When root is done (`return True`), the caller (`ResultReviewer.on_complete`) should route to aggregation.
  - **Add `_route_to_aggregation` method**: Called by `ResultReviewer.on_complete` when `_on_reviewer_accept` returns `True`. Does:
    - `queue.clear_after_current()`
    - `queue.spawn_after_current([ResultAggregationNode, ResponseNode])`
    - `queue.ensure_terminal(ResponseNode)`
  - **Modify `ResultReviewer.on_complete`**: After calling `loop._on_reviewer_accept(active_task)`, if it returns `True`, call `loop._route_to_aggregation(queue)`.

#### [MODIFY] `src/tinycua/tinycua/loops/result_reviewer.py`

- **[Description]**: Capture the return value of `_on_reviewer_accept` and route to aggregation when root task is accepted.
- **[Rationale]**: Currently `on_complete` calls `self.loop._on_reviewer_accept(active_task)` in two places (normal accept at line 196 and force-accept on retry threshold at line 202) but ignores the boolean result in both.
- **Changes**:
  - **Line 196 (normal accept)**: `self.loop._on_reviewer_accept(active_task)` → `root_done = self.loop._on_reviewer_accept(active_task)` + `if root_done: self.loop._route_to_aggregation(queue)`
  - **Line 202 (force-accept on threshold)**: `self.loop._on_reviewer_accept(active_task)` → `root_done = self.loop._on_reviewer_accept(active_task)` + `if root_done: self.loop._route_to_aggregation(queue)`

### Tests

#### [NEW] `src/tinycua/tests/unit/test_result_aggregation.py`

- **[Description]**: Unit tests for `AggregatedResult` construction, `_traverse_bfs_right_to_left` helper (BFS right-to-left, early termination, empty tree), `_consolidate`, and `on_complete` queue advancement.
- **[Dependencies]**: `pytest`, `tinycua.loops.result_aggregation`, `tinycua.models.task`.

#### [NEW] `src/tinycua/tests/integration/test_result_aggregation_integration.py`

- **[Description]**: Integration tests from the "Success Criteria — Integration Tests" section above.
- **[Dependencies]**: `pytest`, `tinycua.loops.result_aggregation`, `tinycua.loops.tinycua_loop`, `tinycua.loops.node_queue`.

---

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.loops.result_aggregation` | New | Module with `AggregatedResult` dataclass and `TinyCUAResultAggregationNode` class |
| `tinycua.loops.__init__` | Modify | Export new classes |
| `tinycua.loops.tinycua_loop` | Modify | Wire root-task-accept → aggregation routing |
| `tinycua.loops.result_reviewer` | Modify | Call `loop._route_to_aggregation()` when `_on_reviewer_accept` returns True |
| `src/tinycua/tests/unit/test_result_aggregation.py` | New | Unit tests for aggregation |
| `src/tinycua/tests/integration/test_result_aggregation_integration.py` | New | Integration tests |

## Data Model Changes

### New Types

```python
@dataclass
class AggregatedResult:
    """Consolidated result from traversing an accepted root task tree."""
    root_task_id: str
    task_summaries: list[str]
    accepted_results: list[TaskResult]
    artifacts: list[dict[str, Any]]
    final_context: str
    response_continuation: str
    metadata: dict
```

## API Changes

No public API changes — all changes are internal to `tinycua.loops`. The `AggregatedResult` and `TinyCUAResultAggregationNode` are re-exported from `tinycua.loops` for convenience.

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | — | All dependencies are internal to the project |

### Internal Dependencies

- [ ] Depends on Milestone 3.2 (`TaskExecutor`, `ResultReviewer`) — already implemented
- [ ] Depends on Milestone 3.3 (mandatory passthrough and continuation routing) — already implemented
- [x] Blocks Milestone 3.5 (`ResponseNode` integration)
- [ ] Relies on `tinycua.loops.node_queue.spawn_after_current()` and `ensure_terminal()` — already available

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Task tree is very deep/wide, causing slow traversal | Medium | Early termination heuristic (configurable `max_inspected_tasks`); generator-based traversal is lazy |
| `AggregatedResult` grows too large for LLM context window | Medium | `final_context` and `task_summaries` are produced from existing summaries; ResponseNode is responsible for context window management |
| Loop wiring breaks existing accept path for non-root tasks | High | Guard the root-task check explicitly: only route to aggregation when `task.parent is None`. Non-root accept continues with existing behavior unchanged |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-11*
