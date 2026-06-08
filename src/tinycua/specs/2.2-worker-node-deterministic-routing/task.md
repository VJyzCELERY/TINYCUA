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

- [x] Write integration tests for WorkerNode deterministic routing (defined in implementation-plan.md) <!-- id: 0, effort: M -->
- [x] Write unit tests for WorkerNode, TaskCreateNode, TaskAnalyzerNode, NodeQueue extensions <!-- id: 1, effort: M -->
- [x] Write error scenario tests: `test_task_create_node_failure_retries`, `test_worker_node_empty_input_passes_through`, `test_clear_after_current_without_ensure_terminal`, `test_stale_worker_spawned_nodes_detection` <!-- id: 1b, effort: S -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 2, effort: S -->

## Implementation Phase

### WorkerNode

- [x] Create `src/tinycua/tinycua/loops/worker.py` with TinyCUAWorkerNode class <!-- id: 3, effort: M -->
  - [x] Define `WorkerRouteLabel` enum with `task_creation` label <!-- id: 4, effort: S -->
  - [x] Implement `_detect_task_exists()` to check `session.task` <!-- id: 5, effort: S -->
  - [x] Implement `_detect_worker_spawned_nodes()` to find worker-owned nodes before terminal ResponseNode <!-- id: 6, effort: M -->
  - [x] Implement `_route_task_creation()` handler that spawns TaskCreateNode <!-- id: 7, effort: M -->
  - [x] Override `__call__()` with deterministic precheck for task_creation before LLM decision <!-- id: 8, effort: M -->
  - [x] Set up RouteMap with `task_creation` label handler <!-- id: 9, effort: S -->

### TaskCreateNode

- [x] Create `src/tinycua/tinycua/loops/task_create.py` with TinyCUATaskCreateNode class <!-- id: 10, effort: M -->
  - [x] Set `tool_scope = ["TaskInit", "TaskCreate"]` <!-- id: 11, effort: S -->
  - [x] Implement `__call__()` to create root task deterministically <!-- id: 12, effort: M -->
  - [x] Implement `on_complete()` to advance queue to TaskAnalyzerNode <!-- id: 13, effort: S -->

### TaskAnalyzerNode

- [x] Create `src/tinycua/tinycua/loops/task_analyzer.py` with TinyCUATaskAnalyzerNode class <!-- id: 14, effort: M -->
  - [x] Add `mode` parameter (`initial_analysis` excludes TaskInit/TaskCreate tools) <!-- id: 15, effort: S -->
  - [x] Implement tool_scope filtering based on mode <!-- id: 16, effort: S -->

### NodeQueue Extensions

- [x] Add `find_worker_spawned_nodes()` to NodeQueue <!-- id: 17, effort: S -->
- [x] Add `find_existing_worker_node()` to NodeQueue <!-- id: 18, effort: S -->

### QueryAnalyst Update

- [x] Update `route_worker()` in TinyCUAQueryAnalystNode to use real TinyCUAWorkerNode <!-- id: 19, effort: S -->

### Module Exports

- [x] Update `src/tinycua/tinycua/loops/__init__.py` to export new nodes <!-- id: 20, effort: S -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 21, effort: S -->
- [x] Run unit tests for WorkerNode <!-- id: 22, effort: S -->
- [x] Run unit tests for TaskCreateNode <!-- id: 23, effort: S -->
- [x] Run unit tests for TaskAnalyzerNode <!-- id: 24, effort: S -->
- [x] Run unit tests for NodeQueue extensions <!-- id: 25, effort: S -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 26, effort: S -->

## Verification Phase

- [x] Verify WorkerNode routes to task_creation when no task exists <!-- id: 27, effort: S, SC-001 -->
- [x] Verify WorkerNode does NOT call LLM for deterministic task_creation <!-- id: 28, effort: S, SC-001 -->
- [x] Verify TaskCreateNode creates root task and advances queue <!-- id: 29, effort: S, SC-002 -->
- [x] Verify TaskAnalyzerNode (initial_analysis) has no TaskInit/TaskCreate tools <!-- id: 30, effort: S, SC-003 -->
- [x] Verify queue shape after task_creation route <!-- id: 31, effort: S, SC-008 -->
- [x] Verify terminal response path guarantee after clear_after_current() <!-- id: 32, effort: S, SC-006 -->
- [x] Verify worker-spawned-node detection for stale nodes <!-- id: 33, effort: S, SC-004 -->
- [x] Verify WorkerNode reuse for existing worker-owned queue segment <!-- id: 34, effort: S, SC-005 -->
- [x] Verify original input query is preserved for downstream nodes <!-- id: 35, effort: S, SC-007 -->

## Documentation Phase

- [x] Update docstrings for all new classes <!-- id: 36, effort: S -->
- [x] Add type hints for all new methods <!-- id: 37, effort: S -->

## Review and Merge

- [x] Create pull request <!-- id: 38, effort: S -->
- [x] Address review feedback <!-- id: 39, effort: M -->
- [x] Merge to main branch <!-- id: 40, effort: S -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-08*
