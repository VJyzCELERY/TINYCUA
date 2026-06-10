# Implementation: TaskExecutor and ResultReviewer Nodes

Implement `TinyCUATaskExecutorNode` (ReAct-style task execution) and `TinyCUAResultReviewerNode` (result evaluation with accept/retry/replan/open_question decisions), wire the executor→reviewer path through existing stubs, and replace no-op reviewer handlers on `TinyCUALoop` with real implementations. Completes Milestone 3.2.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [ ] **None** — no configuration dependencies for this feature

### Running Services

- [ ] **None** — no external services needed

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python 3.11+
- [ ] **Package manager**: uv

---

## Success Criteria — Integration Tests (TDD First)

```python
# Test file: src/tinycua/tests/integration/test_executor_reviewer_integration.py
"""Integration tests for executor→reviewer path."""


def test_executor_reviewer_accept_path():
    """Full executor → reviewer → accept path with mocked LLM.

    Verifies: active task is executed, reviewed, accepted,
    and next active task is selected via DFS.
    """
    # Arrange
    loop = _build_loop_with_active_task()
    mock_llm_response_executor = _make_execution_result("succeeded")
    mock_llm_response_reviewer = _make_reviewer_decision("accept")

    # Act — TaskExecutor runs
    executor_node = TinyCUATaskExecutorNode(config=loop.session_config)
    executor_result = executor_node(_make_node_input(loop.get_active_task()))

    # Act — ResultReviewer evaluates
    reviewer_node = TinyCUAResultReviewerNode(config=loop.session_config)
    reviewer_result = reviewer_node(_make_reviewer_input(executor_result))

    # Assert
    assert reviewer_result.content  # decision present
    loop._on_reviewer_accept(loop.get_active_task())
    assert loop.get_active_task().status == "done"


def test_executor_reviewer_retry_path():
    """Executor → reviewer → retry → executor path.

    Verifies: retry increments counter, same task remains active.
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()

    # Act — reviewer decides retry
    loop._on_reviewer_retry(active_task)

    # Assert
    assert loop._reviewer_retry_state.retry_count == 1
    assert loop.get_active_task().task_id == active_task.task_id


def test_executor_reviewer_replan_path():
    """Executor → reviewer → replan → assessor → analyzer → executor.

    Verifies: replan spawns TaskAssessor + TaskAnalyzer before TaskExecutor.
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()
    queue = loop._queue

    # Act — reviewer decides replan
    loop._on_reviewer_replan(active_task)

    # Assert — queue should have assessor + analyzer prepended
    # (exact assertion depends on spawning mechanism in design)


def test_retry_threshold_enforcement():
    """After 5 retries (default), reviewer accepts or escalates.

    Verifies: reviewer cannot retry again once threshold reached.
    """
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()

    # Act — exhaust retries
    for _ in range(5):
        loop._on_reviewer_retry(active_task)

    # Assert
    assert loop._reviewer_retry_state.is_threshold_reached()
    assert not loop._reviewer_retry_state.can_retry()


def test_retry_counter_resets_on_accept():
    """After successful accept, retry counter resets to 0."""
    # Arrange
    loop = _build_loop_with_active_task()
    active_task = loop.get_active_task()

    # Act — retry a few times, then accept
    for _ in range(3):
        loop._on_reviewer_retry(active_task)
    loop._on_reviewer_accept(active_task)

    # Assert
    assert loop._reviewer_retry_state.retry_count == 0
```

### Key Test Scenarios

- [ ] **Scenario 1**: Full executor→reviewer→accept path — verifies end-to-end flow
- [ ] **Scenario 2**: Retry path with counter increment and threshold enforcement
- [ ] **Scenario 3**: Replan path spawns correct nodes
- [ ] **Edge case**: Retry threshold reached — reviewer must accept or escalate
- [ ] **Edge case**: Retry counter resets on accept

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for TaskExecutorNode, ResultReviewerNode, ReviewerRetryState
- [ ] Unit tests for updated loop handlers and spawning logic
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Run `create_tinycua_agent(...).run(...)` with a simple task and verify executor→reviewer path completes
- [ ] Verify no SDK public API changes: `git diff main -- src/tinycua-sdk/` shows no changes

### Performance Considerations

- [ ] ReAct loop in TaskExecutor bounded by `max_react_iterations` (default 10)
- [ ] No infinite retry loops — `ReviewerRetryState` enforces threshold

## Proposed Changes

### Models

#### NEW `src/tinycua/tinycua/models/reviewer_decision.py`

- **ReviewerRetryState dataclass**: Tracks retry failure count with `increment()`, `reset()`, `can_retry()`, `is_threshold_reached()`. Default threshold: 5. Distinct from `NodeRetryPolicy.max_attempts`.
- **Rationale**: Separates retry tracking from task models; the loop owns this as execution state.

#### MODIFY `src/tinycua/tinycua/models/__init__.py`

- **Export ReviewerRetryState**: Add to existing `__all__` alongside `ReviewerDecision`.

### Nodes

#### NEW `src/tinycua/tinycua/loops/task_executor.py`

- **TinyCUATaskExecutorNode(ProcessNode)**: ReAct-style execution of the active task. Receives active task via NodeInput metadata. Produces `TaskResult`. Does not mutate the active task. `on_complete` advances queue (ResultReviewer is next).
- **Dependencies**: `ProcessNode` from `tinycua.loops.node`, `TaskResult` from `tinycua.models.task`, `NodeInput` from `tinycua.models.node_input`.

#### NEW `src/tinycua/tinycua/loops/result_reviewer.py`

- **TinyCUAResultReviewerNode(ProcessNode)**: Evaluates TaskExecutor output. Decides accept/retry/replan/open_question. Uses `ReviewerRetryState` from loop to check threshold. `on_complete` dispatches based on decision.
- **Dependencies**: `ProcessNode` from `tinycua.loops.node`, `ReviewerDecision` from `tinycua.models.task`, `ReviewerRetryState` from `tinycua.models.reviewer_decision`.

#### MODIFY `src/tinycua/tinycua/loops/__init__.py`

- **Export TinyCUATaskExecutorNode and TinyCUAResultReviewerNode**: Add to `__all__`.

### Loop Integration

#### MODIFY `src/tinycua/tinycua/loops/tinycua_loop.py`

- **`__init__`**: Add `self._reviewer_retry_state: ReviewerRetryState = ReviewerRetryState()`.
- **`_on_reviewer_retry()`** (replace no-op): Increment retry count via `_reviewer_retry_state.increment()`. Log warning if threshold reached. Preserve active task.
- **`_on_reviewer_replan()`** (replace no-op): Log replan event. Preserve active task. Caller spawns assessor+analyzer+executor.
- **`_on_reviewer_open_question()`** (replace no-op): Log open question event. Preserve active task. Caller installs mandatory_passthrough.
- **`_on_reviewer_accept()`** (update existing): Reset retry counter via `_reviewer_retry_state.reset()`.

#### MODIFY `src/tinycua/tinycua/loops/analysis_effort.py`

- **`_spawn_task_executor()`** (replace stub): Import and instantiate `TinyCUATaskExecutorNode` + `TinyCUAResultReviewerNode`. Spawn after current position via `queue.spawn_after_current()`. Ensure terminal response path.

#### MODIFY `src/tinycua/tinycua/loops/worker.py`

- **`_route_proceed_execution()`** (replace stub): Import and instantiate `TinyCUATaskExecutorNode` + `TinyCUAResultReviewerNode`. Clear after current, spawn executor+reviewer, ensure terminal response path.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/models/reviewer_decision.py` | New | ReviewerRetryState dataclass |
| `tinycua/loops/task_executor.py` | New | TaskExecutorNode ProcessNode |
| `tinycua/loops/result_reviewer.py` | New | ResultReviewerNode ProcessNode |
| `tinycua/loops/__init__.py` | Modify | Export new node classes |
| `tinycua/models/__init__.py` | Modify | Export ReviewerRetryState |
| `tinycua/loops/tinycua_loop.py` | Modify | Real reviewer handlers + retry state |
| `tinycua/loops/analysis_effort.py` | Modify | Replace _spawn_task_executor stub |
| `tinycua/loops/worker.py` | Modify | Replace _route_proceed_execution stub |

## Data Model Changes

```python
# New dataclass in tinycua/models/reviewer_decision.py
@dataclass
class ReviewerRetryState:
    retry_count: int = 0
    threshold: int = 5

    def increment(self) -> int: ...
    def reset(self) -> None: ...
    def is_threshold_reached(self) -> bool: ...
    def can_retry(self) -> bool: ...
```

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | — | No new external dependencies |

### Internal Dependencies

- [x] Depends on Milestone 3.1 (Task/TaskResult/ReviewerDecision models, DFS helpers) — already completed
- [ ] Blocks Milestone 3.3 (MandatoryPassthrough routing for open_question)
- [ ] Blocks Milestone 3.4 (ResultAggregationNode)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ReAct loop in TaskExecutor may not converge | High | `max_react_iterations` cap (default 10); log warning on limit |
| LLM may not produce parseable reviewer decision | Medium | Fallback to `retry` when decision cannot be parsed |
| Retry threshold too aggressive for complex tasks | Medium | Configurable threshold via ReviewerRetryState; document tuning |
| Worker._route_proceed_execution stub replacement breaks existing tests | Medium | Run full test suite after replacement; backward compatible |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-10*
