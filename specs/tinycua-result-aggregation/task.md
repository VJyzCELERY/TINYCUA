# Tasks: TinyCUAResultAggregationNode

Implementation tasks for TinyCUAResultAggregationNode. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 0 --> <!-- Depends: [] -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 --> <!-- Depends: [0] -->

## Implementation Phase

- [ ] Implement `AggregatedResult` dataclass in `tinycua/loops/result_aggregation.py` <!-- id: 2 --> <!-- Depends: [] -->
  - [ ] Define `@dataclass` with all fields: `root_task_id`, `task_summaries`, `accepted_results`, `artifacts`, `final_context`, `response_continuation`, `metadata`
  - [ ] Ensure type hints match `TaskResult` from `tinycua.models.task`
  - [ ] Verify dataclass can be instantiated with empty lists/strings as defaults

- [ ] Implement `_traverse_bfs_right_to_left` generator in `tinycua/loops/result_aggregation.py` <!-- id: 3 --> <!-- Depends: [2] -->
  - [ ] Generator-based BFS using `collections.deque`
  - [ ] Right-to-left / most-recent-first order (children reversed before enqueue)
  - [ ] Support early termination via `max_inspected_tasks` parameter
  - [ ] Yield each inspected `Task` for the caller to consume
  - [ ] Handle empty children gracefully

- [ ] Implement `TinyCUAResultAggregationNode` class <!-- id: 4 --> <!-- Depends: [2, 3] -->
  - [ ] Extend `ProcessNode` with `node_id="result_aggregation"`
  - [ ] `__init__`: accept optional `loop` reference
  - [ ] `__call__`: guard (session + root task done), materialize traversal results (`list(_traverse_bfs_right_to_left(...))`), call `_consolidate`, record result, propagate
  - [ ] `_consolidate(traversal_results) -> AggregatedResult`: build consolidated result from traversed tasks
  - [ ] `on_complete`: call `queue.advance()` to advance to `ResponseNode`
  - [ ] Handle tasks with no result gracefully (skip / record "not_executed")

- [ ] Wire loop routing in `tinycua_loop.py` <!-- id: 5 --> <!-- Depends: [4] -->
  - [ ] Add import for `TinyCUAResultAggregationNode`
  - [ ] Add `_route_to_aggregation` method: `clear_after_current()`, `spawn_after_current([ResultAggregationNode, ResponseNode])`, `ensure_terminal(ResponseNode)`
  - [ ] Modify `ResultReviewer.on_complete`: when `loop._on_reviewer_accept` returns True, call `loop._route_to_aggregation(queue)`
  - [ ] Verify non-root accept path unchanged

- [ ] Update module exports in `__init__.py` <!-- id: 6 --> <!-- Depends: [4] -->
  - [ ] Add import: `from tinycua.loops.result_aggregation import TinyCUAResultAggregationNode, AggregatedResult`
  - [ ] Add to `__all__`: `"TinyCUAResultAggregationNode"`, `"AggregatedResult"`

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 7 --> <!-- Depends: [0, 1, 2, 3, 4, 5, 6] -->
- [ ] Write unit tests for `AggregatedResult` construction <!-- id: 8 --> <!-- Depends: [2] -->
  - [ ] All fields populated
  - [ ] Empty lists/strings for missing data
  - [ ] Type checking

- [ ] Write unit tests for `_traverse_bfs_right_to_left` <!-- id: 9 --> <!-- Depends: [3] -->
  - [ ] Multi-level task tree with right-to-left order
  - [ ] Early termination (max_inspected_tasks threshold)
  - [ ] Empty children (leaf task)
  - [ ] Single task (root only, no children)
  - [ ] Read-only guarantee (no mutation)

- [ ] Write unit tests for `_consolidate` <!-- id: 10 --> <!-- Depends: [4] -->
  - [ ] With accepted results
  - [ ] With artifacts
  - [ ] With reviewer decisions
  - [ ] With missing results (not_executed tasks)
  - [ ] Empty traversal list

- [ ] Write unit tests for `TinyCUAResultAggregationNode.__call__` <!-- id: 11 --> <!-- Depends: [4] -->
  - [ ] Guard raises when session not attached
  - [ ] Guard raises when root task not done
  - [ ] Returns `LLMResult` with `AggregatedResult` in metadata

- [ ] Write unit tests for `on_complete` <!-- id: 12 --> <!-- Depends: [4] -->
  - [ ] Queue advances correctly
  - [ ] Logs completion

- [ ] Write unit tests for loop wiring <!-- id: 13 --> <!-- Depends: [5] -->
  - [ ] `_route_to_aggregation` spawns aggregation + response nodes
  - [ ] `_on_reviewer_accept` returns True for root task, False for non-root
  - [ ] Non-root accept path unchanged (existing tests still pass)

- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 14 --> <!-- Depends: [7, 8, 9, 10, 11, 12, 13] -->

## Verification Phase

- [ ] All integration tests pass (see Success Criteria section) <!-- id: 15 --> <!-- Depends: [7] -->
- [ ] All unit tests pass <!-- id: 16 --> <!-- Depends: [14] -->
- [ ] No regressions in existing test suite <!-- id: 17 --> <!-- Depends: [14] -->
- [ ] Verify manual: run `cd src/tinycua && uv run pytest -xvs tests/integration/test_result_aggregation_integration.py` <!-- id: 18 --> <!-- Depends: [15, 16, 17] -->

## Documentation Phase

- [ ] Update module-level docstring in `result_aggregation.py` <!-- id: 19 --> <!-- Depends: [4] -->
- [ ] Add `TinyCUAResultAggregationNode` to any relevant README or documentation <!-- id: 20 --> <!-- Depends: [4] -->
- [ ] Update `CHANGELOG.md` or equivalent if it exists <!-- id: 21 --> <!-- Depends: [4] -->

## Review and Merge

- [ ] Run `/review-loop` to start review cycle <!-- id: 22 --> <!-- Depends: [18] -->
- [ ] Address review feedback <!-- id: 23 --> <!-- Depends: [22] -->
- [ ] Commit final version and push <!-- id: 24 --> <!-- Depends: [23] -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-11*
