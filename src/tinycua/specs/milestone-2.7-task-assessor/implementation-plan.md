# Implementation: TinyCUATaskAssessorNode

ProcessNode that evaluates the task tree and selects unfinished tasks for decomposition or reanalysis. Operates in effort-loop mode (full-tree assessment) and reviewer-replan mode (local-region assessment, deferred). Integrates with `AnalysisEffortNode` queue mechanics to prevent wasted LLM invocations.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: M
- **PR**: #107

## Environment Pre-requisites

### Configuration

- [x] **None** — no additional configuration beyond existing `NodeConfigBase`.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| - [x] **None** — no external services needed |

### Data / Fixtures

- [x] **None** — tests use mocked LLM responses and in-memory sessions.

### Access / Permissions

- [x] **None** — no special access required.

### Developer Tooling

- [x] **Runtime**: Python 3.12, uv
- [x] **None** — no special tooling required.

---

## Success Criteria — Integration Tests (TDD First)

```python
# Test file: tests/unit/test_task_assessor_node.py
"""Unit tests for TinyCUATaskAssessorNode."""


def test_effort_loop_mode_evaluates_task_tree():
    """In effort_loop mode, TaskAssessor evaluates full task tree."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    assessor = TinyCUATaskAssessorNode(config=config, mode="effort_loop")
    session = Session()
    session.task = "Write a script"
    assessor.ensure_session(session)
    input_data = NodeInput(input_type="continuation", messages=[...])
    mock_response = MagicMock(content='["task-1", "task-2"]', role="assistant", tool_calls=[], metadata={})

    # Act
    with patch.object(assessor, "_call_llm", return_value=mock_response):
        assessor(input_data)

    # Assert
    assert assessor.selected_tasks == ["task-1", "task-2"]


def test_effort_loop_mode_no_tasks_selected():
    """In effort_loop mode, returns empty list when all tasks complete."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    assessor = TinyCUATaskAssessorNode(config=config, mode="effort_loop")
    session = Session()
    session.task = "Write a script"
    assessor.ensure_session(session)
    input_data = NodeInput(input_type="continuation", messages=[...])
    mock_response = MagicMock(content="[]", role="assistant", tool_calls=[], metadata={})

    # Act
    with patch.object(assessor, "_call_llm", return_value=mock_response):
        assessor(input_data)

    # Assert
    assert assessor.selected_tasks == []


def test_effort_loop_mode_on_complete_advances_queue():
    """When tasks selected, on_complete advances queue normally."""
    # Arrange
    assessor = TinyCUATaskAssessorNode(config=NodeConfigBase(), mode="effort_loop")
    assessor.selected_tasks = ["task-1"]
    queue = NodeQueue()
    terminal = MagicMock(node_id="response", is_terminal=True)
    queue.items = [assessor, terminal]

    # Act
    assessor.on_complete(queue, MagicMock(content="Tasks selected"))

    # Assert
    assert queue.items[0].node_id == "response"


def test_effort_loop_mode_on_complete_no_tasks_skips_analyzer():
    """When no tasks selected, on_complete skips TaskAnalyzer."""
    # Arrange
    assessor = TinyCUATaskAssessorNode(config=NodeConfigBase(), mode="effort_loop")
    assessor.selected_tasks = []
    queue = NodeQueue()
    analyzer = MagicMock(node_id="task_analyzer", is_terminal=False)
    terminal = MagicMock(node_id="response", is_terminal=True)
    queue.items = [assessor, analyzer, terminal]

    # Act
    assessor.on_complete(queue, MagicMock(content="No tasks"))

    # Assert — TaskAnalyzer removed from queue
    assert queue.items[0].node_id == "response"
    assert all(n.node_id != "task_analyzer" for n in queue.items)


# Test file: tests/integration/test_analysis_effort_integration.py
"""Integration tests for AnalysisEffortNode + TaskAssessor flow."""


def test_analysis_effort_node_assessor_no_tasks():
    """TaskAssessor selects no tasks → no TaskAnalyzer → back to AnalysisEffortNode."""
    # Arrange
    config = NodeConfigBase(llm_client=MagicMock())
    effort_node = TinyCUAAnalysisEffortNode(config=config, effort=WorkerEffort.low)
    session = Session()
    effort_node.ensure_session(session)
    queue = NodeQueue()
    terminal = MagicMock(node_id="response", is_terminal=True)
    queue.items = [effort_node, terminal]

    # Act — execute effort node, then assessor
    input_data = NodeInput(input_type="continuation", messages=[...])
    response = effort_node(input_data)
    effort_node.on_complete(queue, response)
    assessor = queue.items.pop(0)
    assessor.ensure_session(session)
    with patch.object(assessor, "_call_llm", return_value=MagicMock(content="[]", role="assistant", tool_calls=[], metadata={})):
        queue.set_input(assessor, input_data)
        assessor_response = assessor(input_data)
        assessor.on_complete(queue, assessor_response)

    # Assert
    assert effort_node.pass_count == 1
    assert "task_analyzer" not in [n.node_id for n in queue.items]
    assert "analysis_effort" in [n.node_id for n in queue.items]
```

### Key Test Scenarios

- [x] **Scenario 1**: TaskAssessor evaluates task tree and returns selected task IDs (JSON list).
- [x] **Scenario 2**: TaskAssessor returns empty list when all tasks are complete.
- [x] **Scenario 3**: on_complete skips TaskAnalyzer when no tasks selected (design contract).
- [x] **Scenario 4**: on_complete advances queue normally when tasks are selected.
- [x] **Edge case**: Malformed LLM response (non-JSON) — treated as empty selection with warning.
- [x] **Edge case**: Empty LLM response — treated as empty selection.

## Verification Plan

### Automated Tests

- [x] Unit tests for `TinyCUATaskAssessorNode` initialization (5 tests)
- [x] Unit tests for `__call__` with various task tree states (3 tests)
- [x] Unit tests for `on_complete` queue advancement (2 tests)
- [x] Integration tests with `AnalysisEffortNode` (5 tests in `test_analysis_effort_integration.py`)
- [x] Full test suite: `cd src/tinycua && uv run pytest` — 575/575 pass (including all 15 TaskAssessor-related tests)

### Manual Verification

- [ ] Verify TaskAssessor behavior in a live TinyCUA session — **deferred to Phase 2 integration testing** (requires full TinyCUA environment setup).

### Performance Considerations

- [x] Effort-loop mode limits assessment passes via `pass_limit` — no unbounded LLM calls.

## Proposed Changes

### Task Assessor Module

#### [NEW] `tinycua/loops/task_assessor.py`

- **Description**: Core `TinyCUATaskAssessorNode` implementation as a concrete `ProcessNode`.
- **Dependencies**: `tinycua.loops.node.ProcessNode`, `tinycua.config.node_config.NodeConfigBase`

#### [DEFERRED] `tinycua/config/node_config.py`

- **Description**: No changes in Phase 1 — listed for cross-reference with design.md only. The design proposed `TinyCUATaskAssessorNodeConfig` with `assessment_schema` and `allow_task_updates`, but these are deferred to Phase 2. No file modification occurs in this milestone.
- **Rationale**: MVP requires no custom config fields. Uses base `NodeConfigBase` as-is.

#### [MODIFY] `tinycua/loops/__init__.py`

- **Description**: Export `TinyCUATaskAssessorNode` from the loops package.

### Analysis Effort Integration

#### [MODIFY] `tinycua/loops/analysis_effort.py`

- **Description**: `AnalysisEffortNode.on_complete` creates `TaskAssessorNode(mode="effort_loop")` + `TaskAnalyzerNode(mode="effort_loop_decomposition")` and calls `queue.suspend_current_and_prepend()`.
- **Rationale**: This is the integration point — AnalysisEffortNode is the producer of TaskAssessor instances.

### Tests

#### [NEW] `tests/unit/test_task_assessor_node.py`

- **Description**: 10 unit tests covering init, __call__, and on_complete.

#### [NEW] `tests/integration/test_analysis_effort_integration.py`

- **Description**: 5 integration tests covering the full AnalysisEffortNode → TaskAssessor → TaskAnalyzer flow.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.loops.task_assessor` | New | Core TaskAssessorNode implementation |
| `tinycua.loops.analysis_effort` | Modified | Prepends [TaskAssessor, TaskAnalyzer] pairs to queue |
| `tinycua.loops.__init__` | Modified | Exports TinyCUATaskAssessorNode |
| `tinycua.loops.node` | Unchanged | ProcessNode base class |
| `tinycua.loops.node_queue` | Unchanged | Queue mechanics |

## Data Model Changes

```python
# Conceptual data shape (internal to TaskAssessorNode)
# No new public types — selected_tasks is an instance attribute.
TaskAssessorNode:
    selected_tasks: list[str]    # Populated after __call__, consumed by on_complete
    mode: str                    # "effort_loop" (default) or "reviewer_replan" (future)
```

## API Changes

No public API changes — this is an internal node used by the orchestration loop.

## Dependencies

### External Dependencies

None — no new packages required.

### Internal Dependencies

- [x] Depends on `ProcessNode` base class (already implemented)
- [x] Depends on `NodeQueue.suspend_current_and_prepend()` (already implemented in PR #99)
- [x] Depends on `AnalysisEffortNode` integration (already implemented in PR #104)
- [ ] Blocks: TaskExecutor integration (Milestone 3.2)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM produces inconsistent task ID format | Medium | Robust JSON parsing with fallback to empty selection + warning log |
| Empty or null task tree | Low | Handled gracefully — returns empty selection |
| TaskAnalyzer skipped but expected downstream | Medium | `on_complete` only skips analyzer when queue has it at front; otherwise advances normally |

---

## Phase Status

### Phase 1 — MVP (COMPLETE)

- [x] `TinyCUATaskAssessorNode` class with effort-loop mode
- [x] LLM response parsing (JSON list of task IDs)
- [x] `on_complete` queue advancement (skip analyzer when no tasks)
- [x] Integration with `AnalysisEffortNode` prepending
- [x] Unit tests (10/10 passing)
- [x] Integration tests (5 tests covering full flow)
- [x] Exported in `loops/__init__.py`

### Phase 2 — Enhancements (DEFERRED)

- [ ] Reviewer-replan mode for local-region assessment
- [ ] `TinyCUATaskAssessorNodeConfig` with `assessment_schema` and `allow_task_updates`
- [ ] Structured assessment output via `assessment_schema`
- [ ] Task status update capabilities during assessment

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-10*
