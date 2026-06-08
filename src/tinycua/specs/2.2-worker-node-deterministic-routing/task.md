# Tasks: TinyCUAWorkerNode Deterministic Routing and TaskCreate

Implementation tasks for TinyCUAWorkerNode Deterministic Routing and TaskCreate. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for WorkerNode deterministic routing (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Write unit tests for WorkerNode, TaskCreateNode, TaskAnalyzerNode, NodeQueue extensions <!-- id: 1 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

### WorkerNode

- [ ] Create `src/tinycua/tinycua/loops/worker.py` with TinyCUAWorkerNode class <!-- id: 3 -->
  - [ ] Define `WorkerRouteLabel` enum with `task_creation` label <!-- id: 4 -->
  - [ ] Implement `_detect_task_exists()` to check `session.task` <!-- id: 5 -->
  - [ ] Implement `_detect_worker_spawned_nodes()` to find worker-owned nodes before terminal ResponseNode <!-- id: 6 -->
  - [ ] Implement `_route_task_creation()` handler that spawns TaskCreateNode <!-- id: 7 -->
  - [ ] Override `__call__()` with deterministic precheck for task_creation before LLM decision <!-- id: 8 -->
  - [ ] Set up RouteMap with `task_creation` label handler <!-- id: 9 -->

### TaskCreateNode

- [ ] Create `src/tinycua/tinycua/loops/task_create.py` with TinyCUATaskCreateNode class <!-- id: 10 -->
  - [ ] Set `tool_scope = ["TaskInit", "TaskCreate"]` <!-- id: 11 -->
  - [ ] Implement `__call__()` to create root task deterministically <!-- id: 12 -->
  - [ ] Implement `on_complete()` to advance queue to TaskAnalyzerNode <!-- id: 13 -->

### TaskAnalyzerNode

- [ ] Create `src/tinycua/tinycua/loops/task_analyzer.py` with TinyCUATaskAnalyzerNode class <!-- id: 14 -->
  - [ ] Add `mode` parameter (`initial_analysis` excludes TaskInit/TaskCreate tools) <!-- id: 15 -->
  - [ ] Implement tool_scope filtering based on mode <!-- id: 16 -->

### NodeQueue Extensions

- [ ] Add `find_worker_spawned_nodes()` to NodeQueue <!-- id: 17 -->
- [ ] Add `find_existing_worker_node()` to NodeQueue <!-- id: 18 -->

### QueryAnalyst Update

- [ ] Update `route_worker()` in TinyCUAQueryAnalystNode to use real TinyCUAWorkerNode <!-- id: 19 -->

### Module Exports

- [ ] Update `src/tinycua/tinycua/loops/__init__.py` to export new nodes <!-- id: 20 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 21 -->
- [ ] Run unit tests for WorkerNode <!-- id: 22 -->
- [ ] Run unit tests for TaskCreateNode <!-- id: 23 -->
- [ ] Run unit tests for TaskAnalyzerNode <!-- id: 24 -->
- [ ] Run unit tests for NodeQueue extensions <!-- id: 25 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 26 -->

## Verification Phase

- [ ] Verify WorkerNode routes to task_creation when no task exists <!-- id: 27 -->
- [ ] Verify WorkerNode does NOT call LLM for deterministic task_creation <!-- id: 28 -->
- [ ] Verify TaskCreateNode creates root task and advances queue <!-- id: 29 -->
- [ ] Verify TaskAnalyzerNode (initial_analysis) has no TaskInit/TaskCreate tools <!-- id: 30 -->
- [ ] Verify queue shape after task_creation route <!-- id: 31 -->
- [ ] Verify terminal response path guarantee after clear_after_current() <!-- id: 32 -->

## Documentation Phase

- [ ] Update docstrings for all new classes <!-- id: 33 -->
- [ ] Add type hints for all new methods <!-- id: 34 -->

## Review and Merge

- [ ] Create pull request <!-- id: 35 -->
- [ ] Address review feedback <!-- id: 36 -->
- [ ] Merge to main branch <!-- id: 37 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-08*
