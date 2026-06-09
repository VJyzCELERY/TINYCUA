# Tasks: TinyCUAAnalysisEffortNode

Implementation tasks for TinyCUAAnalysisEffortNode. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write unit tests for `WorkerEffort` enum and `effort_to_pass_limit()` mapping <!-- id: 0 -->
  - [ ] `test_worker_effort_enum_values` — verify none, low, medium, high exist
  - [ ] `test_effort_to_pass_limit_none` — none → 0
  - [ ] `test_effort_to_pass_limit_low` — low → 1
  - [ ] `test_effort_to_pass_limit_medium` — medium → 2
  - [ ] `test_effort_to_pass_limit_high` — high → 3
- [ ] Write unit tests for `TinyCUAAnalysisEffortNode` <!-- id: 1 -->
  - [ ] `test_analysis_effort_node_none_effort` — pass_limit=0, spawns TaskExecutor immediately
  - [ ] `test_analysis_effort_node_low_effort` — pass_limit=1, prepends one [TaskAssessor, TaskAnalyzer]
  - [ ] `test_analysis_effort_node_medium_effort` — pass_limit=2, prepends two passes
  - [ ] `test_analysis_effort_node_high_effort` — pass_limit=3, prepends three passes
  - [ ] `test_analysis_effort_node_pass_count_increment` — pass_count increments on each pass
  - [ ] `test_analysis_effort_node_threshold_reached` — TaskExecutor spawns when pass_count >= pass_limit
  - [ ] `test_analysis_effort_node_no_llm_call` — deterministic node makes no LLM calls
  - [ ] `test_analysis_effort_node_default_effort` — defaults to WorkerEffort="none" when not configured
  - [ ] `test_analysis_effort_node_preserves_terminal_path` — terminal response path maintained
  - [ ] `test_analysis_effort_node_effort_to_pass_limit_mapping` — all four levels map correctly
  - [ ] `test_analysis_effort_node_task_tree_propagation` — task tree state changes propagated (SC-013 / FR-014)
- [ ] Write unit tests for WorkerNode route handler modifications <!-- id: 2 -->
  - [ ] `test_analysis_effort_node_queue_shape_after_task_creation` — [task_create, task_analyzer, analysis_effort, terminal]
  - [ ] `test_analysis_effort_node_queue_shape_after_task_recreation` — [task_analyzer, analysis_effort, terminal]
  - [ ] `test_analysis_effort_node_queue_shape_after_task_reanalysis` — [task_analyzer, analysis_effort, terminal]
- [ ] Write unit tests for `TinyCUATaskAssessorNode` <!-- id: 3 -->
  - [ ] `test_task_assessor_node_effort_loop_mode` — evaluates full task tree
  - [ ] `test_task_assessor_node_no_tasks_selected` — signals no analyzer pass needed
  - [ ] `test_task_assessor_node_selects_tasks` — selects unfinished tasks
- [ ] Run unit tests — expect RED (failures) since no implementation yet <!-- id: 4 -->
- [ ] Write integration tests for worker → effort → executor flow <!-- id: 5 -->
  - [ ] `test_analysis_effort_node_with_worker_task_creation` — end-to-end task_creation route
  - [ ] `test_analysis_effort_node_with_worker_task_recreation` — end-to-end task_recreation route
  - [ ] `test_analysis_effort_node_with_worker_task_reanalysis` — end-to-end task_reanalysis route
  - [ ] `test_analysis_effort_node_passes_complete` — AnalysisEffortNode → [Assessor, Analyzer] × N → Executor
  - [ ] `test_analysis_effort_node_assessor_no_tasks` — no tasks → no analyzer → back to AnalysisEffortNode
- [ ] Run integration tests — expect RED <!-- id: 6 -->

## Implementation Phase

- [ ] Create `WorkerEffort` enum <!-- id: 7 -->
  - [ ] Define `WorkerEffort(str, Enum)` with none, low, medium, high values
  - [ ] Implement `effort_to_pass_limit()` mapping function
- [ ] Create `TinyCUATaskAssessorNode` <!-- id: 8 -->
  - [ ] Implement `__init__(node_id, config, mode)` with mode parameter
  - [ ] Implement `__call__(input)` — LLM-based task tree evaluation
  - [ ] Implement `on_complete(queue, response)` — advance or skip analyzer based on task selection
  - [ ] Support `effort_loop` mode (evaluate full tree, select unfinished tasks)
- [ ] Create `TinyCUAAnalysisEffortNode` <!-- id: 9 -->
  - [ ] Implement `__init__(node_id, config, effort)` — pass_count=0, pass_limit from effort_to_pass_limit
  - [ ] Implement `__call__(input)` — deterministic logic: prepend or spawn
  - [ ] Implement `_should_spawn_executor() -> bool`
  - [ ] Implement `_prepend_assessor_analyzer_pair(queue)` — create TaskAssessor + TaskAnalyzer, prepend
  - [ ] Implement `_spawn_task_executor(queue)` — stub for Milestone 3.2
  - [ ] Implement `on_complete(queue, response)` — post-completion hook for queue mutations
- [ ] Update WorkerNode route handlers <!-- id: 10 -->
  - [ ] Add `_effort: WorkerEffort` attribute to `TinyCUAWorkerNode.__init__()` with default `WorkerEffort.none`
  - [ ] Update `_route_task_creation()` to insert AnalysisEffortNode after TaskCreate/TaskAnalyzer
  - [ ] Update `_route_task_recreation()` to insert AnalysisEffortNode after TaskAnalyzer
  - [ ] Update `_route_task_reanalysis()` to insert AnalysisEffortNode after TaskAnalyzer
- [ ] Update `tinycua.loops.__init__` exports <!-- id: 11 -->
  - [ ] Export `TinyCUAAnalysisEffortNode`, `WorkerEffort`, `TinyCUATaskAssessorNode`

## Testing Phase

- [ ] Run unit tests — expect GREEN (all pass) <!-- id: 12 -->
  - [ ] `cd src/tinycua && uv run pytest tests/unit/test_analysis_effort_node.py -v`
  - [ ] `cd src/tinycua && uv run pytest tests/unit/test_task_assessor_node.py -v`
  - [ ] `cd src/tinycua && uv run pytest tests/unit/test_worker_node.py -v`
- [ ] Run integration tests — expect GREEN <!-- id: 13 -->
  - [ ] `cd src/tinycua && uv run pytest tests/integration/test_analysis_effort_integration.py -v`
- [ ] Run full test suite — confirm no regressions <!-- id: 14 -->
  - [ ] `cd src/tinycua && uv run pytest`

## Verification Phase

- [ ] Verify queue shapes match design for all effort levels <!-- id: 15 -->
- [ ] Verify pass counting with debug logging <!-- id: 16 -->
- [ ] Verify terminal response path is maintained after TaskExecutor spawning <!-- id: 17 -->
- [ ] Verify AnalysisEffortNode makes no LLM calls (mock assertion) <!-- id: 18 -->

## Documentation Phase

- [ ] Update `src/tinycua/specs/2.4-analysis-effort-node/spec.md` status tracker <!-- id: 19 -->
- [ ] Update `src/tinycua/specs/2.4-analysis-effort-node/design.md` implementation phases <!-- id: 20 -->

## Review and Merge

- [ ] Create pull request <!-- id: 21 -->
- [ ] Address review feedback <!-- id: 22 -->
- [ ] Merge to main branch <!-- id: 23 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-09*
