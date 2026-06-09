# Implementation: TinyCUAAnalysisEffortNode

A deterministic `ProcessNode` that controls how many upfront task-assessment and task-analysis passes occur before advancing to execution. Maps `WorkerEffort` levels (`none`, `low`, `medium`, `high`) to pass limits (0, 1, 2, 3), prepends `[TaskAssessor, TaskAnalyzer]` pairs until the threshold is reached, and spawns TaskExecutor before advancing.

## Context

- **Spec Reference**: `./spec.md` — TinyCUAAnalysisEffortNode (Milestone 2.4)
- **Design Reference**: `./design.md` — Full architecture, data model, API contracts, queue shapes
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| [None] | No | — | — |

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+, uv
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_analysis_effort_integration.py
"""Integration tests for TinyCUAAnalysisEffortNode — worker → effort → executor flow."""


def test_analysis_effort_node_with_worker_task_creation():
    """End-to-end: WorkerNode → task_creation → TaskCreate → TaskAnalyzer → AnalysisEffortNode → TaskExecutor."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    session = Session()
    session.task = None  # No task → deterministic task_creation route
    worker.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [worker, terminal]

    # Simulate task_creation route
    result = DecisionResult(
        route_label="task_creation",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="task_creation", role="assistant"),
    )
    worker.on_complete(queue, result)

    # Act — verify queue shape
    node_ids = [n.node_id for n in queue.items]

    # Assert
    assert "task_create" in node_ids
    assert "task_analyzer" in node_ids
    assert "analysis_effort" in node_ids
    # Verify ordering: task_create → task_analyzer → analysis_effort → terminal
    tc_idx = node_ids.index("task_create")
    ta_idx = node_ids.index("task_analyzer")
    ae_idx = node_ids.index("analysis_effort")
    assert tc_idx < ta_idx < ae_idx


def test_analysis_effort_node_with_worker_task_recreation():
    """End-to-end: WorkerNode → task_recreation → TaskAnalyzer → AnalysisEffortNode → TaskExecutor."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    session = Session()
    session.task = "Existing task"
    worker.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [worker, terminal]

    result = DecisionResult(
        route_label="task_recreation",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="task_recreation", role="assistant"),
    )
    worker.on_complete(queue, result)

    # Act
    node_ids = [n.node_id for n in queue.items]

    # Assert
    assert "task_analyzer" in node_ids
    assert "analysis_effort" in node_ids
    ta_idx = node_ids.index("task_analyzer")
    ae_idx = node_ids.index("analysis_effort")
    assert ta_idx < ae_idx


def test_analysis_effort_node_with_worker_task_reanalysis():
    """End-to-end: WorkerNode → task_reanalysis → TaskAnalyzer → AnalysisEffortNode → TaskExecutor."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    worker = TinyCUAWorkerNode(node_id="worker", config=config)
    session = Session()
    session.task = "Existing task"
    worker.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [worker, terminal]

    result = DecisionResult(
        route_label="task_reanalysis",
        analysis_response=LLMResult(content="analysis", role="assistant"),
        classification_response=LLMResult(content="task_reanalysis", role="assistant"),
    )
    worker.on_complete(queue, result)

    # Act
    node_ids = [n.node_id for n in queue.items]

    # Assert
    assert "task_analyzer" in node_ids
    assert "analysis_effort" in node_ids
    ta_idx = node_ids.index("task_analyzer")
    ae_idx = node_ids.index("analysis_effort")
    assert ta_idx < ae_idx


def test_analysis_effort_node_passes_complete():
    """End-to-end: AnalysisEffortNode → [TaskAssessor, TaskAnalyzer] × N → TaskExecutor."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    effort_node = TinyCUAAnalysisEffortNode(
        node_id="analysis_effort", config=config, effort=WorkerEffort.low,
    )
    session = Session()
    effort_node.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [effort_node, terminal]

    # Act — execute with pass_count=0, pass_limit=1
    input_data = NodeInput(
        input_type="continuation",
        messages=[{"role": "user", "content": "Continue"}],
    )
    effort_node(queue)  # This should prepend [TaskAssessor, TaskAnalyzer]

    # Assert
    node_ids = [n.node_id for n in queue.items]
    assert "task_assessor" in node_ids
    assert "task_analyzer" in node_ids
    assert effort_node.pass_count == 1


def test_analysis_effort_node_assessor_no_tasks():
    """End-to-end: TaskAssessor selects no tasks → no TaskAnalyzer → back to AnalysisEffortNode."""
    config = NodeConfigBase(llm_client=MagicMock())
    effort_node = TinyCUAAnalysisEffortNode(
        node_id="analysis_effort", config=config, effort=WorkerEffort.low,
    )
    session = Session()
    effort_node.ensure_session(session)

    queue = NodeQueue()
    terminal = _make_mock_node("response", is_terminal=True)
    queue.items = [effort_node, terminal]

    # Mock TaskAssessor to return no tasks
    with patch('tinycua.loops.analysis_effort.TinyCUATaskAssessorNode') as MockAssessor:
        mock_assessor = Mock()
        mock_assessor.selected_tasks = []
        MockAssessor.return_value = mock_assessor

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Continue"}],
        )
        effort_node(input_data)

    node_ids = [n.node_id for n in queue.items]
    assert "task_analyzer" not in node_ids
    assert "analysis_effort" in node_ids
    assert effort_node.pass_count == 1
```

### Key Test Scenarios

- [ ] **Scenario 1**: Worker task_creation route inserts AnalysisEffortNode after TaskCreate/TaskAnalyzer
- [ ] **Scenario 2**: Worker task_recreation route inserts AnalysisEffortNode after TaskAnalyzer
- [ ] **Scenario 3**: Worker task_reanalysis route inserts AnalysisEffortNode after TaskAnalyzer
- [ ] **Scenario 4**: AnalysisEffortNode prepends [TaskAssessor, TaskAnalyzer] when pass_count < pass_limit
- [ ] **Scenario 5**: AnalysisEffortNode spawns TaskExecutor when pass_count >= pass_limit
- [ ] **Edge case**: TaskAssessor selects no tasks — TaskAnalyzer not spawned, queue advances back to AnalysisEffortNode

## Verification Plan

### Automated Tests

- [ ] Unit tests for `WorkerEffort` enum and `effort_to_pass_limit()` mapping
- [ ] Unit tests for `TinyCUAAnalysisEffortNode` — pass counting, threshold detection, queue mutations
- [ ] Unit tests for WorkerNode route handler modifications — queue shape after each route
- [ ] Integration tests for worker → effort → executor flow
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify AnalysisEffortNode queue shape visually with each effort level
- [ ] Verify pass counting with debug logging enabled

### Performance Considerations

- [ ] AnalysisEffortNode is deterministic (no LLM call) — zero latency overhead
- [ ] Pass counting is O(1) per pass — no performance concern

## Proposed Changes

### New Module: `tinycua.loops.analysis_effort`

#### [NEW] `src/tinycua/tinycua/loops/analysis_effort.py`

- **Description**: Create `WorkerEffort` enum, `effort_to_pass_limit()` mapping function, and `TinyCUAAnalysisEffortNode` class
- **Dependencies**: `tinycua.loops.node.ProcessNode`, `tinycua.loops.node_queue.NodeQueue`, `tinycua.loops.task_analyzer.TinyCUATaskAnalyzerNode`
- **Key components**:
  - `WorkerEffort(str, Enum)` — `none`, `low`, `medium`, `high`
  - `effort_to_pass_limit(effort: WorkerEffort) -> int` — maps effort to 0, 1, 2, 3
  - `TinyCUAAnalysisEffortNode(ProcessNode)` — deterministic node with pass counting
    - `__init__(node_id, config, effort)` — initializes pass_count=0, pass_limit from effort_to_pass_limit
    - `__call__(input)` — deterministic logic: prepend or spawn based on pass_count
    - `_should_spawn_executor() -> bool` — pass_count >= pass_limit
    - `_prepend_assessor_analyzer_pair(queue)` — creates TaskAssessor(mode=effort_loop) + TaskAnalyzer(mode=effort_loop_decomposition), prepends via queue
    - `_spawn_task_executor(queue)` — creates TaskExecutor, spawns after current (Milestone 3.2 stub)
    - `on_complete(queue, response)` — post-completion hook for queue mutations

#### [NEW] `src/tinycua/tinycua/loops/task_assessor.py`

- **Description**: Create `TinyCUATaskAssessorNode` — evaluates task tree and selects unfinished tasks
- **Dependencies**: `tinycua.loops.node.ProcessNode`
- **Note**: This is a dependency for AnalysisEffortNode. The spec references it as a key entity. Implementation should be minimal — enough to support the AnalysisEffortNode flow. Full effort-loop and reviewer-replan mode implementation can be deferred.
- **Key components**:
  - `TinyCUATaskAssessorNode(ProcessNode)` — evaluates task tree
    - `mode: str` — `"effort_loop"` or `"reviewer_replan"`
    - `on_complete(queue, response)` — if tasks selected, advance to TaskAnalyzer; if no tasks, advance back to AnalysisEffortNode

### Modified Module: `tinycua.loops.task_analyzer`

#### [MODIFY] `src/tinycua/tinycua/loops/task_analyzer.py`

- **Description**: Add `effort_loop_decomposition` to `_VALID_MODES` and route it to the same tool filtering as `initial_analysis`
- **Rationale**: AnalysisEffortNode spawns TaskAnalyzerNode with `mode="effort_loop_decomposition"`, which must be a recognized mode with appropriate tool scope
- **Breaking changes**: None — adding a new mode is additive
- **Changes**:
  - Add `"effort_loop_decomposition"` to `_VALID_MODES` frozenset
  - Include `"effort_loop_decomposition"` in `_resolve_tool_scope()` alongside `"initial_analysis"` for excluded tool filtering

### Modified Module: `tinycua.loops.worker`

#### [MODIFY] `src/tinycua/tinycua/loops/worker.py`

- **Description**: Update `_route_task_creation()`, `_route_task_recreation()`, and `_route_task_reanalysis()` to insert `AnalysisEffortNode` after the initial TaskCreate/TaskAnalyzer
- **Rationale**: WorkerNode route handlers must insert AnalysisEffortNode as part of the queue shape (FR-009)
- **Breaking changes**: None — AnalysisEffortNode defaults to `WorkerEffort.none` (pass_limit=0), so existing behavior is preserved when effort is not configured
- **Changes per route**:
  - `_route_task_creation()`: Add `analysis_effort` to spawned nodes: `[task_create, task_analyzer, analysis_effort]`
  - `_route_task_recreation()`: Add `analysis_effort` to spawned nodes: `[task_analyzer, analysis_effort]`
  - `_route_task_reanalysis()`: Add `analysis_effort` to spawned nodes: `[task_analyzer, analysis_effort]`
- **New attribute**: `TinyCUAWorkerNode._effort: WorkerEffort` — configurable effort level, defaults to `WorkerEffort.none`

### Modified Module: `tinycua.loops.__init__`

#### [MODIFY] `src/tinycua/tinycua/loops/__init__.py`

- **Description**: Export `TinyCUAAnalysisEffortNode`, `WorkerEffort`, and `TinyCUATaskAssessorNode`
- **Rationale**: Public API exposure for the new nodes

### Test Files

#### [NEW] `src/tinycua/tests/unit/test_analysis_effort_node.py`

- **Description**: Unit tests for `WorkerEffort`, `effort_to_pass_limit()`, and `TinyCUAAnalysisEffortNode`
- **Test count**: ~19 unit tests covering all acceptance scenarios

#### [NEW] `src/tinycua/tests/unit/test_task_assessor_node.py`

- **Description**: Unit tests for `TinyCUATaskAssessorNode`
- **Test count**: ~3 unit tests for task selection and no-tasks-selected behavior

#### [NEW] `src/tinycua/tests/integration/test_analysis_effort_integration.py`

- **Description**: Integration tests for worker → effort → executor flow
- **Test count**: ~5 integration tests

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.loops.analysis_effort` | New | Deterministic ProcessNode for effort control |
| `tinycua.loops.task_assessor` | New | ProcessNode for task tree evaluation and selection |
| `tinycua.loops.worker` | Modified | Route handlers insert AnalysisEffortNode after TaskCreate/TaskAnalyzer |
| `tinycua.loops.__init__` | Modified | Export new nodes |

## Data Model Changes

```python
from enum import Enum

class WorkerEffort(str, Enum):
    """Effort levels for task analysis passes."""
    none = "none"      # pass_limit=0
    low = "low"        # pass_limit=1
    medium = "medium"  # pass_limit=2
    high = "high"      # pass_limit=3


def effort_to_pass_limit(effort: WorkerEffort) -> int:
    """Map WorkerEffort to pass limit."""
    return {
        WorkerEffort.none: 0,
        WorkerEffort.low: 1,
        WorkerEffort.medium: 2,
        WorkerEffort.high: 3,
    }[effort]
```

## API Changes

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| N/A | N/A | No new API endpoints — this is an internal node |

### Modified Endpoints

| Method | Path | Change |
|--------|------|--------|
| N/A | N/A | No API changes — internal architecture only |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| None | — | No new external dependencies |

### Internal Dependencies

- [x] Depends on `tinycua.loops.node.ProcessNode` (existing)
- [x] Depends on `tinycua.loops.node_queue.NodeQueue` (existing)
- [x] Depends on `tinycua.loops.task_analyzer.TinyCUATaskAnalyzerNode` (existing)
- [x] Depends on `tinycua.loops.task_create.TinyCUATaskCreateNode` (existing, for task_creation route)
- [ ] Blocks Milestone 3.2 (TaskExecutor, ResultReviewer) — deferred

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| TaskAssessor is a new dependency not yet implemented | Medium | Create minimal TaskAssessor supporting effort-loop mode; full implementation deferred |
| TaskExecutor does not exist (Milestone 3.2) | Low | `_spawn_task_executor()` is a stub; spec explicitly defers TaskExecutor to Phase 2 |
| AnalysisEffortNode could create infinite loop if pass_count never increments | High | pass_count incremented atomically before prepending; on_complete called exactly once per pass |
| WorkerNode route handlers could forget to insert AnalysisEffortNode | Medium | Comprehensive unit tests for all route shapes; integration tests verify queue shape |
| Terminal response path could be lost after TaskExecutor spawning | High | ensure_terminal() call in _spawn_task_executor(); unit test verifies |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-09*
