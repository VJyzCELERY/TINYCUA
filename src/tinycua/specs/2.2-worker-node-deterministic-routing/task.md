# Tasks: TinyCUAWorkerNode Deterministic Routing and TaskCreate

Implementation tasks for TinyCUAWorkerNode Deterministic Routing and TaskCreate. Check off items as completed.

## Dependencies

- Tasks 0-2 (TDD Phase) must complete before 3+ (Implementation Phase)
- Task 3 (WorkerNode) blocks tasks 4-9 and task 19 (QueryAnalyst update)
- Task 10 (TaskCreateNode) blocks tasks 11-13
- Task 14 (TaskAnalyzerNode) blocks tasks 15-16
- Task 19 (QueryAnalyst update) depends on task 3 (WorkerNode creation)
- Task 20 (Module Exports) depends on tasks 3, 10, 14 (all new modules)

## TDD Phase (Tests First)

- [ ] Write integration tests for WorkerNode deterministic routing (defined in implementation-plan.md) <!-- id: 0, effort: M -->
- [ ] Write unit tests for WorkerNode, TaskCreateNode, TaskAnalyzerNode, NodeQueue extensions <!-- id: 1, effort: M -->
- [ ] Write error scenario tests: `test_task_create_node_failure_retries`, `test_worker_node_empty_input_passes_through`, `test_clear_after_current_without_ensure_terminal`, `test_stale_worker_spawned_nodes_detection` <!-- id: 1b, effort: S -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 2, effort: S -->

## Implementation Phase

### WorkerNode

- [ ] Create `src/tinycua/tinycua/loops/worker.py` with TinyCUAWorkerNode class <!-- id: 3, effort: M -->
  - [ ] Define `WorkerRouteLabel` enum with `task_creation` label <!-- id: 4, effort: S -->
  - [ ] Implement `_detect_task_exists()` to check `session.task` <!-- id: 5, effort: S -->
  - [ ] Implement `_detect_worker_spawned_nodes()` to find worker-owned nodes before terminal ResponseNode <!-- id: 6, effort: M -->
  - [ ] Implement `_route_task_creation()` handler that spawns TaskCreateNode <!-- id: 7, effort: M -->
  - [ ] Override `__call__()` with deterministic precheck for task_creation before LLM decision <!-- id: 8, effort: M -->
  - [ ] Set up RouteMap with `task_creation` label handler <!-- id: 9, effort: S -->

### TaskCreateNode

- [ ] Create `src/tinycua/tinycua/loops/task_create.py` with TinyCUATaskCreateNode class <!-- id: 10, effort: M -->
  - [ ] Set `tool_scope = ["TaskInit", "TaskCreate"]` <!-- id: 11, effort: S -->
  - [ ] Implement `__call__()` to create root task deterministically <!-- id: 12, effort: M -->
  - [ ] Implement `on_complete()` to advance queue to TaskAnalyzerNode <!-- id: 13, effort: S -->

### TaskAnalyzerNode

- [ ] Create `src/tinycua/tinycua/loops/task_analyzer.py` with TinyCUATaskAnalyzerNode class <!-- id: 14, effort: M -->
  - [ ] Add `mode` parameter (`initial_analysis` excludes TaskInit/TaskCreate tools) <!-- id: 15, effort: S -->
  - [ ] Implement tool_scope filtering based on mode <!-- id: 16, effort: S -->

### NodeQueue Extensions

- [ ] Add `find_worker_spawned_nodes()` to NodeQueue <!-- id: 17, effort: S -->
- [ ] Add `find_existing_worker_node()` to NodeQueue <!-- id: 18, effort: S -->

### QueryAnalyst Update

- [ ] Update `route_worker()` in TinyCUAQueryAnalystNode to use real TinyCUAWorkerNode <!-- id: 19, effort: S -->

### Module Exports

- [ ] Update `src/tinycua/tinycua/loops/__init__.py` to export new nodes <!-- id: 20, effort: S -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 21, effort: S -->
- [ ] Run unit tests for WorkerNode <!-- id: 22, effort: S -->
- [ ] Run unit tests for TaskCreateNode <!-- id: 23, effort: S -->
- [ ] Run unit tests for TaskAnalyzerNode <!-- id: 24, effort: S -->
- [ ] Run unit tests for NodeQueue extensions <!-- id: 25, effort: S -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 26, effort: S -->

## Verification Phase

- [ ] Verify WorkerNode routes to task_creation when no task exists <!-- id: 27, effort: S -->
- [ ] Verify WorkerNode does NOT call LLM for deterministic task_creation <!-- id: 28, effort: S -->
- [ ] Verify TaskCreateNode creates root task and advances queue <!-- id: 29, effort: S -->
- [ ] Verify TaskAnalyzerNode (initial_analysis) has no TaskInit/TaskCreate tools <!-- id: 30, effort: S -->
- [ ] Verify queue shape after task_creation route <!-- id: 31, effort: S -->
- [ ] Verify terminal response path guarantee after clear_after_current() <!-- id: 32, effort: S -->

## Documentation Phase

- [ ] Update docstrings for all new classes <!-- id: 33, effort: S -->
- [ ] Add type hints for all new methods <!-- id: 34, effort: S -->

## Review and Merge

- [ ] Create pull request <!-- id: 35, effort: S -->
- [ ] Address review feedback <!-- id: 36, effort: M -->
- [ ] Merge to main branch <!-- id: 37, effort: S -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-08*
