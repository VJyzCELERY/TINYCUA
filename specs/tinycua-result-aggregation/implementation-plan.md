# Implementation: TinyCUAResultAggregationNode

This implementation introduces `TinyCUAResultAggregationNode` — a `ProcessNode` that performs read-only traversal of the accepted root task tree, consolidates task results/artifacts/reviewer decisions, and produces an `AggregatedResult` for `TinyCUAResponseNode`. Also wires root-task-accept routing in `TinyCUALoop` so that when `ResultReviewer` accepts the root task, the queue advances through `ResultAggregationNode` → `TinyCUAResponseNode`.

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

- [x] **None** — test fixtures are built programmatically in test files

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.12+
- [x] **Package manager**: uv
- [x] **Additional CLI tools**: pytest
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

Integration tests are defined in `src/tinycua/tests/integration/test_result_aggregation_integration.py` — see the file for full implementation.

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

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [x] Unit tests for `AggregatedResult` construction — test all fields, empty fields, serialization
- [x] Unit tests for `_traverse_bfs_right_to_left` — test multi-level trees, early termination, empty trees
- [x] Unit tests for `_consolidate` — test with various combinations of results/artifacts/decisions
- [x] Unit tests for `TinyCUAResultAggregationNode.__call__` — test guard, propagation, error cases
- [x] Unit tests for `on_complete` — verify queue advancement and session context recording
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] N/A — all behavior is verifiable through automated tests.

### Performance Considerations

- [x] Traversal of deep/wide task trees should be bounded by configurable `max_inspected_tasks`
- [x] Aggregation produces no new LLM content — purely mechanical consolidation

## Proposed Changes

### `tinycua.loops.result_aggregation` (New Module)

#### [NEW] `src/tinycua/tinycua/loops/result_aggregation.py`

- **[Description]**: New module containing `AggregatedResult` dataclass and `TinyCUAResultAggregationNode` class.
- **[Dependencies]**: `tinycua.loops.node` (ProcessNode), `tinycua.models.task` (Task, TaskResult), `tinycua.config.types` (LLMResult), `tinycua.models.node_input` (NodeInputLike), `tinycua.loops.node_queue` (NodeQueue), `tinycua.config.node_config` (NodeConfigBase).

**`AggregatedResult` dataclass** — defined in `src/tinycua/tinycua/loops/result_aggregation.py`.

**`TinyCUAResultAggregationNode` class**:
- Extends `ProcessNode` with `node_id="result_aggregation"`.
- `__init__(self, node_id="result_aggregation", config=None, loop=None)` — accepts optional `loop` reference for access to `root_task` and `session`.
- `__call__(self, input: NodeInputLike) -> LLMResult`:
  1. Guard: assert `session` is attached and root task is done (`session.task` / `loop.root_task` is done).
  2. Traverse task tree: `traversal_results = list(self._traverse_bfs_right_to_left(root_task))`.
  3. Consolidate: `result = self._consolidate(traversal_results)` → `AggregatedResult`.
  4. Record result to session context / response metadata.
  5. `propagate()`.
  6. Return `LLMResult` with `AggregatedResult` in `metadata["aggregated_result"]`.
- `_traverse_bfs_right_to_left(task: Task, max_inspected_tasks: int | None = None, context_sufficient_fn: Callable | None = None) -> Iterator[Task]`:
  - Generator-based guided BFS right-to-left / most-recent-first.
  - Uses `collections.deque` with a reversed children queue.
  - Supports early termination via `context_sufficient_fn` callback or `max_inspected_tasks` threshold.
    - `context_sufficient_fn` signature: `Optional[Callable[[Task, AggregatedResult], bool]]`
      - Called for each inspected task with `(current_task, partial_result)`.
      - Return `True` to stop traversal early (context sufficient).
      - Default `None` means no callback (used for MVP).
  - Inspects each visited task's context, result, artifacts, and reviewer decisions.
  - Yields each inspected task for the caller to consume.
- `_consolidate(traversal_results: list[Task]) -> AggregatedResult`:
  - Builds `AggregatedResult` from inspected tasks.
  - Collects: `root_task_id`, `task_summaries`, `accepted_results`, `artifacts`, `final_context`, `response_continuation`, `metadata`.
- `on_complete(self, queue: NodeQueue, response: LLMResult) -> None`:
  - Calls `queue.advance()` to advance to `TinyCUAResponseNode`.
  - Logs completion.

#### [MODIFY] `src/tinycua/tinycua/loops/__init__.py`

- **[Description]**: Add imports for `TinyCUAResultAggregationNode` and `AggregatedResult` from the new module.
- **[Rationale]**: Expose the new classes via the public `tinycua.loops` namespace.
- **Changes**:
  - Add: `from tinycua.loops.result_aggregation import TinyCUAResultAggregationNode, AggregatedResult`
  - Add to `__all__`: `"TinyCUAResultAggregationNode"`, `"AggregatedResult"`

#### [MODIFY] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **[Description]**: Wire root-task-accept → aggregation routing in `_on_reviewer_accept`.
- **[Rationale]**: When `ResultReviewer` accepts the root task (no parent), the loop needs to route to `ResultAggregationNode` then `TinyCUAResponseNode`.
- **Changes**:
  - **Add import**: `from tinycua.loops.result_aggregation import TinyCUAResultAggregationNode`
  - **Modify `_on_reviewer_accept`**: Currently returns a bool indicating whether root is done. We need to also handle queue mutation when root is done. The method should:
    1. Keep existing logic (mark task done, walk parent chain, check root).
    2. When root is done (`return True`), the caller (`ResultReviewer.on_complete`) should route to aggregation.
  - **Add `_route_to_aggregation` method**: Called by `ResultReviewer.on_complete` when `_on_reviewer_accept` returns `True`. Does:
    - `queue.clear_after_current()`
    - `queue.spawn_after_current([ResultAggregationNode, TinyCUAResponseNode])`
    - `queue.ensure_terminal(TinyCUAResponseNode)`
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

`AggregatedResult` dataclass — defined in `src/tinycua/tinycua/loops/result_aggregation.py`.

## API Changes

No public API changes — all changes are internal to `tinycua.loops`. The `AggregatedResult` and `TinyCUAResultAggregationNode` are re-exported from `tinycua.loops` for convenience.

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| (none) | — | All dependencies are internal to the project |

### Internal Dependencies

- [x] Depends on Milestone 3.2 (`TaskExecutor`, `ResultReviewer`) — already implemented
- [x] Depends on Milestone 3.3 (mandatory passthrough and continuation routing) — already implemented
- [x] Blocks Milestone 3.5 (`TinyCUAResponseNode` integration)
- [x] Relies on `tinycua.loops.node_queue.spawn_after_current()` and `ensure_terminal()` — already available

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Task tree is very deep/wide, causing slow traversal | Medium | Early termination heuristic (configurable `max_inspected_tasks`); generator-based traversal is lazy |
| `AggregatedResult` grows too large for LLM context window | Medium | `final_context` and `task_summaries` are produced from existing summaries; TinyCUAResponseNode is responsible for context window management |
| Loop wiring breaks existing accept path for non-root tasks | High | Guard the root-task check explicitly: only route to aggregation when `task.parent is None`. Non-root accept continues with existing behavior unchanged |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-11*
