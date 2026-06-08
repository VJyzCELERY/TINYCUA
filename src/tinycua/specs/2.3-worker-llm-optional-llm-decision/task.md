# Tasks: TinyCUAWorkerNode Optional LLM Decision

Implementation tasks for TinyCUAWorkerNode Optional LLM Decision (Milestone 2.3). Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for WorkerNode LLM decision flow (defined in implementation-plan.md) <!-- id: 0 -->
  - [ ] test_worker_node_llm_decision_with_task_exists
  - [ ] test_worker_node_dynamic_labels_with_worker_spawned
  - [ ] test_worker_node_dynamic_labels_without_worker_spawned
  - [ ] test_worker_node_route_task_recreation
  - [ ] test_worker_node_route_task_reanalysis
  - [ ] test_worker_node_route_passthrough
  - [ ] test_worker_node_route_proceed_execution
  - [ ] test_worker_node_invalid_label_retry
  - [ ] test_worker_node_route_clear_ensures_terminal
- [ ] Run integration tests — expect RED (failures since no implementation yet) <!-- id: 1 -->

## Implementation Phase

- [ ] Add all five route labels to WorkerRouteLabel enum <!-- id: 2 -->
  - [ ] Add task_recreation, task_reanalysis, passthrough, proceed_execution to WorkerRouteLabel
  - [ ] Update docstring to reflect all labels are implemented
- [ ] Implement _has_worker_spawned_nodes() method <!-- id: 3 -->
  - [ ] Convenience wrapper around existing _detect_worker_spawned_nodes() (returns list)
  - [ ] Return bool indicating worker-spawned node presence
- [ ] Implement _get_classification_labels() method <!-- id: 4 -->
  - [ ] Always include task_recreation, task_reanalysis, proceed_execution
  - [ ] Include passthrough only when _has_worker_spawned_nodes() is True
- [ ] Update _build_default_route_map() to register all five labels <!-- id: 5 -->
  - [ ] Register task_recreation handler
  - [ ] Register task_reanalysis handler
  - [ ] Register passthrough handler
  - [ ] Register proceed_execution handler
- [ ] Implement _route_task_recreation() handler <!-- id: 6 -->
  - [ ] Call queue.clear_after_current()
  - [ ] Spawn TaskAnalyzerNode with TaskInit/TaskCreate tools (mode="initial_analysis" or equivalent)
  - [ ] Call queue.ensure_terminal(default_response_node)
- [ ] Implement _route_task_reanalysis() handler <!-- id: 7 -->
  - [ ] Call queue.clear_after_current()
  - [ ] Spawn TaskAnalyzerNode without TaskInit/TaskCreate tools (mode="reanalysis" or equivalent)
  - [ ] Call queue.ensure_terminal(default_response_node)
- [ ] Implement _route_passthrough() handler <!-- id: 8 -->
  - [ ] Call queue.advance() to move to next node
  - [ ] Forward input to next worker-spawned node
  - [ ] Do NOT re-insert WorkerNode into the queue
- [ ] Implement _route_proceed_execution() handler <!-- id: 9 -->
  - [ ] Check for existing TaskExecutor/ResultReviewer before spawning
  - [ ] Spawn TaskExecutor and ResultReviewer path
  - [ ] Call queue.ensure_terminal(default_response_node)
- [ ] Update __call__() to use dynamic labels when task exists <!-- id: 10 -->
  - [ ] Replace static _DEFAULT_WORKER_LABELS with _get_classification_labels()
  - [ ] Ensure classification uses dynamic label list

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 11 -->
- [ ] Write unit tests for new methods <!-- id: 12 -->
  - [ ] test_has_worker_spawned_nodes_true/false
  - [ ] test_get_classification_labels_with_spawned
  - [ ] test_get_classification_labels_without_spawned
  - [ ] test_route_task_recreation_clears_and_spawns
  - [ ] test_route_task_reanalysis_clears_and_spawns
  - [ ] test_route_passthrough_advances
  - [ ] test_route_proceed_execution_spawns
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 13 -->

## Verification Phase

- [ ] Verify queue shape after each route matches expected architecture <!-- id: 14 -->
- [ ] Verify dynamic label adjustment with and without worker-spawned nodes <!-- id: 15 -->
- [ ] Verify NodeRetryPolicy integration for invalid classification labels <!-- id: 16 -->
- [ ] Verify terminal response path guarantee in all route handlers <!-- id: 17 -->
- [ ] Run type checking: `cd src/tinycua && uv run mypy tinycua/` <!-- id: 18 -->

## Documentation Phase

- [ ] Update spec.md status tracker to reflect completed items <!-- id: 18 -->
- [ ] Update design.md implementation phases checklist <!-- id: 19 -->
- [ ] No API documentation changes needed (internal implementation only) <!-- id: 20 -->

## Review and Merge

- [ ] Create pull request <!-- id: 21 -->
- [ ] Address review feedback <!-- id: 22 -->
- [ ] Merge to main branch <!-- id: 23 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-08*
