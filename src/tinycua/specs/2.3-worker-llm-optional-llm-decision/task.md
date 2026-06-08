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
- [ ] Implement _has_worker_spawned_nodes(queue) method <!-- id: 3 -->
  - [ ] Add queue: NodeQueue parameter
  - [ ] Convenience wrapper around existing _detect_worker_spawned_nodes(queue) (returns list)
  - [ ] Return bool indicating worker-spawned node presence
- [ ] Implement _get_classification_labels(queue) method <!-- id: 4 -->
  - [ ] Add queue: NodeQueue parameter
  - [ ] Always include task_recreation, task_reanalysis, proceed_execution
  - [ ] Include passthrough only when _has_worker_spawned_nodes(queue) is True
- [ ] Update _build_default_route_map() to register all five labels <!-- id: 5 -->
  - [ ] Register task_recreation handler
  - [ ] Register task_reanalysis handler
  - [ ] Register passthrough handler
  - [ ] Register proceed_execution handler
- [ ] Implement _route_task_recreation() handler <!-- id: 6 -->
  - [ ] Call queue.clear_after_current()
  - [ ] Spawn TaskAnalyzerNode with TaskInit/TaskCreate tools (mode="analysis" — NOT "initial_analysis" which excludes TaskInit/TaskCreate)
  - [ ] Call queue.ensure_terminal(default_response_node)
- [ ] Implement _route_task_reanalysis() handler <!-- id: 7 -->
  - [ ] Call queue.clear_after_current()
  - [ ] Spawn TaskAnalyzerNode without TaskInit/TaskCreate tools (mode="initial_analysis")
  - [ ] Call queue.ensure_terminal(default_response_node)
- [ ] Implement _route_passthrough() handler <!-- id: 8 -->
  - [ ] Call queue.advance() to move to next node
  - [ ] Forward input to next worker-spawned node
  - [ ] Do NOT re-insert WorkerNode into the queue
- [ ] Implement _route_proceed_execution() handler <!-- id: 9 -->
  - [ ] Log classification at INFO level (observability)
  - [ ] Call queue.ensure_terminal(default_response_node) — terminal route for Milestone 2.3
  - [ ] Note: TaskExecutor/ResultReviewer spawning deferred to Milestone 3.2 (Phase 2)
- [ ] Update __call__() to use dynamic labels when task exists <!-- id: 10 -->
  - [ ] Replace static _DEFAULT_WORKER_LABELS with _get_classification_labels()
  - [ ] Ensure classification uses dynamic label list

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 11 -->
- [ ] Write unit tests for new methods <!-- id: 12 -->
  - [ ] test_has_worker_spawned_nodes_true/false: assert returns True when spawned nodes exist, False otherwise
  - [ ] test_get_classification_labels_with_spawned: assert includes passthrough when spawned nodes exist
  - [ ] test_get_classification_labels_without_spawned: assert excludes passthrough when no spawned nodes
  - [ ] test_route_task_recreation_clears_and_spawns: assert old nodes cleared, task_analyzer spawned with mode="analysis"
  - [ ] test_route_task_reanalysis_clears_and_spawns: assert old nodes cleared, task_analyzer spawned with mode="initial_analysis"
  - [ ] test_route_passthrough_advances: assert worker removed, next node is current
  - [ ] test_route_proceed_execution_ensures_terminal: assert queue.items[-1].is_terminal is True
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 13 -->

## Verification Phase

- [ ] Verify queue shape after each route matches expected architecture <!-- id: 14 -->
  - [ ] task_recreation: queue.items contains ["task_analyzer", <terminal>] after handler
  - [ ] task_reanalysis: queue.items contains ["task_analyzer", <terminal>] after handler
  - [ ] passthrough: queue.items[0] is the next worker-spawned node after handler
  - [ ] proceed_execution: queue.items[-1].is_terminal is True after handler
- [ ] Verify dynamic label adjustment with and without worker-spawned nodes <!-- id: 15 -->
  - [ ] With spawned nodes: assert "passthrough" in worker._get_classification_labels()
  - [ ] Without spawned nodes: assert "passthrough" not in worker._get_classification_labels()
  - [ ] Both cases: assert task_recreation, task_reanalysis, proceed_execution are always present
- [ ] Verify NodeRetryPolicy integration for invalid classification labels <!-- id: 16 -->
  - [ ] Mock LLM to return invalid label, assert NodeExecutionError raised after max_attempts
  - [ ] Verify retry count matches config.retry_policy.max_attempts
- [ ] Verify terminal response path guarantee in all route handlers <!-- id: 17 -->
  - [ ] task_recreation: assert queue.items[-1].is_terminal is True
  - [ ] task_reanalysis: assert queue.items[-1].is_terminal is True
  - [ ] proceed_execution: assert queue.items[-1].is_terminal is True
- [ ] Run type checking: `cd src/tinycua && uv run mypy tinycua/` <!-- id: 18 -->

## Documentation Phase

- [ ] Update spec.md status tracker to reflect completed items <!-- id: 19 -->
- [ ] Update design.md implementation phases checklist <!-- id: 20 -->
- [ ] No API documentation changes needed (internal implementation only) <!-- id: 21 -->

## Review and Merge

- [ ] Create pull request <!-- id: 22 -->
- [ ] Address review feedback <!-- id: 23 -->
- [ ] Merge to main branch <!-- id: 24 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-08*
