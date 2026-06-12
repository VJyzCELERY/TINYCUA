# Tasks: TinyCUAResultAggregationNode

Implementation tasks for TinyCUAResultAggregationNode. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests (defined in implementation-plan.md) <!-- id: 0 --> <!-- Depends: [] -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 --> <!-- Depends: [0] -->

## Implementation Phase

- [x] Implement `AggregatedResult` dataclass in `tinycua/loops/result_aggregation.py` <!-- id: 2 --> <!-- Depends: [] -->
  - [x] Define `@dataclass` with all fields: `root_task_id`, `task_summaries`, `accepted_results`, `artifacts`, `final_context`, `response_continuation`, `metadata`
  - [x] Ensure type hints match `TaskResult` from `tinycua.models.task`
  - [x] Verify dataclass can be instantiated with empty lists/strings as defaults

- [x] Implement `_traverse_bfs_right_to_left` generator in `tinycua/loops/result_aggregation.py` <!-- id: 3 --> <!-- Depends: [2] -->
  - [x] Generator-based BFS using `collections.deque`
  - [x] Right-to-left / most-recent-first order (children reversed before enqueue)
  - [x] Support early termination via `max_inspected_tasks` parameter
  - [x] Yield each inspected `Task` for the caller to consume
  - [x] Handle empty children gracefully

- [x] Implement `TinyCUAResultAggregationNode` class <!-- id: 4 --> <!-- Depends: [2, 3] -->
  - [x] Extend `ProcessNode` with `node_id="result_aggregation"`
  - [x] `__init__`: accept optional `loop` reference
  - [x] `__call__`: guard (session + root task done), materialize traversal results (`list(_traverse_bfs_right_to_left(...))`), call `_consolidate`, record result, propagate
  - [x] `_consolidate(traversal_results) -> AggregatedResult`: build consolidated result from traversed tasks
  - [x] `on_complete`: call `queue.advance()` to advance to `TinyCUAResponseNode`
  - [x] Handle tasks with no result gracefully (skip / record "not_executed")

- [x] Wire loop routing in `tinycua_loop.py` <!-- id: 5 --> <!-- Depends: [4] -->
  - [x] Add import for `TinyCUAResultAggregationNode`
  - [x] Add `_route_to_aggregation` method: `clear_after_current()`, `spawn_after_current([ResultAggregationNode, TinyCUAResponseNode])`, `ensure_terminal(TinyCUAResponseNode)`
  - [x] Modify `ResultReviewer.on_complete`: when `loop._on_reviewer_accept` returns True, call `loop._route_to_aggregation(queue)`
  - [x] Verify non-root accept path unchanged

- [x] Update module exports in `__init__.py` <!-- id: 6 --> <!-- Depends: [4] -->
  - [x] Add import: `from tinycua.loops.result_aggregation import TinyCUAResultAggregationNode, AggregatedResult`
  - [x] Add to `__all__`: `"TinyCUAResultAggregationNode"`, `"AggregatedResult"`

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 7 --> <!-- Depends: [0, 1, 2, 3, 4, 5, 6] -->
- [x] Write unit tests for `AggregatedResult` construction <!-- id: 8 --> <!-- Depends: [2] -->
  - [x] All fields populated
  - [x] Empty lists/strings for missing data
  - [x] Type checking

- [x] Write unit tests for `_traverse_bfs_right_to_left` <!-- id: 9 --> <!-- Depends: [3] -->
  - [x] Multi-level task tree with right-to-left order
  - [x] Early termination (max_inspected_tasks threshold)
  - [x] Empty children (leaf task)
  - [x] Single task (root only, no children)
  - [x] Read-only guarantee (no mutation)

- [x] Write unit tests for `_consolidate` <!-- id: 10 --> <!-- Depends: [4] -->
  - [x] With accepted results
  - [x] With artifacts
  - [x] With reviewer decisions
  - [x] With missing results (not_executed tasks)
  - [x] Empty traversal list

- [x] Write unit tests for `TinyCUAResultAggregationNode.__call__` <!-- id: 11 --> <!-- Depends: [4] -->
  - [x] Guard raises when session not attached
  - [x] Guard raises when root task not done
  - [x] Returns `LLMResult` with `AggregatedResult` in metadata

- [x] Write unit tests for `on_complete` <!-- id: 12 --> <!-- Depends: [4] -->
  - [x] Queue advances correctly
  - [x] Logs completion

- [x] Write unit tests for loop wiring <!-- id: 13 --> <!-- Depends: [5] -->
  - [x] `_route_to_aggregation` spawns aggregation + response nodes
  - [x] `_on_reviewer_accept` returns True for root task, False for non-root
  - [x] Non-root accept path unchanged (existing tests still pass)

- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 14 --> <!-- Depends: [7, 8, 9, 10, 11, 12, 13] -->

## Verification Phase

- [x] All integration tests pass (see Success Criteria section) <!-- id: 15 --> <!-- Depends: [7] -->
- [x] All unit tests pass <!-- id: 16 --> <!-- Depends: [14] -->
- [x] No regressions in existing test suite <!-- id: 17 --> <!-- Depends: [14] -->
- [x] Verify manual: run `cd src/tinycua && uv run pytest -xvs tests/integration/test_result_aggregation_integration.py` <!-- id: 18 --> <!-- Depends: [15, 16, 17] -->

## Documentation Phase

- [x] Update module-level docstring in `result_aggregation.py` <!-- id: 19 --> <!-- Depends: [4] -->
- [x] N/A: `TinyCUAResultAggregationNode` is an internal loop node, not user-facing; no README update needed <!-- id: 20 --> <!-- Depends: [4] -->
- [x] N/A: No CHANGELOG.md exists in this repo <!-- id: 21 --> <!-- Depends: [4] -->

## Review and Merge

- [x] Run `/review-loop` to start review cycle <!-- id: 22 --> <!-- Depends: [18] -->
- [x] Address review feedback <!-- id: 23 --> <!-- Depends: [22] -->
- [x] Commit final version and push <!-- id: 24 --> <!-- Depends: [23] -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-11*
