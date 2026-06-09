# Tasks: TinyCUAWorkerNode Optional LLM Decision

Implementation tasks for TinyCUAWorkerNode Optional LLM Decision (Milestone 2.3). Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests for WorkerNode LLM decision flow (defined in implementation-plan.md) <!-- id: 0 -->
  - [x] test_worker_node_llm_decision_with_task_exists
  - [x] test_worker_node_dynamic_labels_with_worker_spawned
  - [x] test_worker_node_dynamic_labels_without_worker_spawned
  - [x] test_worker_node_route_task_recreation
  - [x] test_worker_node_route_task_reanalysis
  - [x] test_worker_node_route_passthrough
  - [x] test_worker_node_route_proceed_execution
  - [x] test_worker_node_invalid_label_retry
  - [x] test_worker_node_route_clear_ensures_terminal
  - [x] test_worker_node_queue_invariant_query_analyst_first
  - [x] test_worker_node_latest_valid_verdict_wins
- [x] Run integration tests — expect RED (failures since no implementation yet) <!-- id: 1 -->

## Implementation Phase

- [x] Add all five route labels to WorkerRouteLabel enum <!-- id: 2 -->
  - [x] Add task_recreation, task_reanalysis, passthrough, proceed_execution to WorkerRouteLabel
  - [x] Update docstring to reflect all labels are implemented
- [x] Implement _has_worker_spawned_nodes(queue) method <!-- id: 3 -->
  - [x] Add queue: NodeQueue parameter
  - [x] Convenience wrapper around existing _detect_worker_spawned_nodes(queue) (returns list)
  - [x] Return bool indicating worker-spawned node presence
- [x] Implement _get_classification_labels(queue) method <!-- id: 4 -->
  - [x] Add queue: NodeQueue parameter
  - [x] Always include task_recreation, task_reanalysis, proceed_execution
  - [x] Include passthrough only when _has_worker_spawned_nodes(queue) is True
- [x] Update _build_default_route_map() to register all five labels <!-- id: 5 -->
  - [x] Register task_recreation handler
  - [x] Register task_reanalysis handler
  - [x] Register passthrough handler
  - [x] Register proceed_execution handler
- [x] Implement _route_task_recreation() handler <!-- id: 6 -->
  - [x] Call queue.clear_after_current()
  - [x] Spawn TaskAnalyzerNode with TaskInit/TaskCreate tools (mode="analysis" — NOT "initial_analysis" which excludes TaskInit/TaskCreate)
  - [x] Call queue.ensure_terminal(default_response_node)
- [x] Implement _route_task_reanalysis() handler <!-- id: 7 -->
  - [x] Call queue.clear_after_current()
  - [x] Spawn TaskAnalyzerNode without TaskInit/TaskCreate tools (mode="initial_analysis")
  - [x] Call queue.ensure_terminal(default_response_node)
- [x] Implement _route_passthrough() handler <!-- id: 8 -->
  - [x] Call queue.advance() to move to next node
  - [x] Forward input to next worker-spawned node
  - [x] Do NOT re-insert WorkerNode into the queue
- [x] Implement _route_proceed_execution() handler <!-- id: 9 -->
  - [x] Log classification at INFO level (observability)
  - [x] Call queue.ensure_terminal(default_response_node) — terminal route for Milestone 2.3
  - [x] Note: TaskExecutor/ResultReviewer spawning deferred to Milestone 3.2 (Phase 2)
- [x] Update __call__() to use dynamic labels when task exists <!-- id: 10 -->
  - [x] Replace static _DEFAULT_WORKER_LABELS with _get_classification_labels()
  - [x] Ensure classification uses dynamic label list
- [x] Restrict WorkerNode tool scope to decision tools only (FR-014) <!-- id: 10a -->
  - [x] Ensure __call__() passes only worker decision tools (WorkerRouteLabel classification) to LLM
  - [x] Exclude task creation (TaskInit/TaskCreate), analysis, and execution tools from classification context
  - [x] Verify no task/execution tools leak into LLM tool_scope during classification
- [x] Integrate NodeRetryPolicy for invalid classification labels <!-- id: 11 -->
  - [x] Wire NodeRetryPolicy into the classification retry loop in __call__()
  - [x] Set default max_attempts=3 with on_retry_exhausted="raise"
  - [x] Raise NodeExecutionError after retries exhausted

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 12 -->
- [x] Write unit tests for new methods <!-- id: 13 -->
  - [x] test_has_worker_spawned_nodes_true/false: assert returns True when spawned nodes exist, False otherwise
  - [x] test_get_classification_labels_with_spawned: assert includes passthrough when spawned nodes exist
  - [x] test_get_classification_labels_without_spawned: assert excludes passthrough when no spawned nodes
  - [x] test_route_task_creation_clears_and_spawns: assert old nodes cleared, task_create + task_analyzer spawned with mode="initial_analysis"
  - [x] test_detect_task_exists_true: assert returns True when session.task is set
  - [x] test_detect_task_exists_false: assert returns False when session.task is None/empty
  - [x] test_on_complete_dispatches_to_route_map: assert route_map.dispatch called with correct label
  - [x] test_call_deterministic_precheck_no_task: assert returns task_creation without LLM calls
  - [x] test_call_llm_decision_with_task: assert delegates to super().__call__ when task exists
  - [x] test_route_task_recreation_clears_and_spawns: assert old nodes cleared, task_analyzer spawned with mode="analysis"
  - [x] test_route_task_reanalysis_clears_and_spawns: assert old nodes cleared, task_analyzer spawned with mode="initial_analysis"
  - [x] test_route_passthrough_advances: assert worker removed, next node is current
  - [x] test_route_proceed_execution_ensures_terminal: assert queue.items[-1].is_terminal is True
  - [x] test_queue_invariant_query_analyst_first: assert query_analyst remains first after dispatch
  - [x] test_worker_node_preserves_input: assert original input query is preserved for downstream
  - [x] test_worker_node_tool_scope: assert WorkerNode only has access to worker decision tools
  - [x] test_worker_node_classification_tool_call_format: assert classification uses tool-call response with WorkerRouteLabel enum values
  - [x] test_worker_node_classifies_task_recreation: assert classification returns task_recreation label
  - [x] test_worker_node_classifies_task_reanalysis: assert classification returns task_reanalysis label
  - [x] test_worker_node_classifies_passthrough: assert classification returns passthrough label
  - [x] test_worker_node_classifies_proceed_execution: assert classification returns proceed_execution label
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 14 -->

## Verification Phase

- [x] Verify queue shape after each route matches expected architecture <!-- id: 15 -->
  - [x] task_recreation: queue.items contains ["task_analyzer", <terminal>] after handler
  - [x] task_reanalysis: queue.items contains ["task_analyzer", <terminal>] after handler
  - [x] passthrough: queue.items[0] is the next worker-spawned node after handler
  - [x] proceed_execution: queue.items[-1].is_terminal is True after handler
- [x] Verify dynamic label adjustment with and without worker-spawned nodes <!-- id: 16 -->
  - [x] With spawned nodes: assert "passthrough" in worker._get_classification_labels()
  - [x] Without spawned nodes: assert "passthrough" not in worker._get_classification_labels()
  - [x] Both cases: assert task_recreation, task_reanalysis, proceed_execution are always present
- [x] Verify NodeRetryPolicy integration for invalid classification labels <!-- id: 17 -->
  - [x] Mock LLM to return invalid label, assert NodeExecutionError raised after max_attempts
  - [x] Verify retry count matches config.retry_policy.max_attempts
- [x] Verify terminal response path guarantee in all route handlers <!-- id: 18 -->
  - [x] task_recreation: assert queue.items[-1].is_terminal is True
  - [x] task_reanalysis: assert queue.items[-1].is_terminal is True
  - [x] proceed_execution: assert queue.items[-1].is_terminal is True
- [x] Run type checking: `cd src/tinycua && uv run mypy tinycua/` <!-- id: 19 -->

## Documentation Phase

- [x] Update spec.md status tracker to reflect completed items <!-- id: 20 -->
- [x] Update design.md implementation phases checklist <!-- id: 21 -->
- [x] No API documentation changes needed (internal implementation only) <!-- id: 22 -->

## Review and Merge

- [x] Create pull request <!-- id: 23 -->
- [x] Address review feedback <!-- id: 24 -->
- [x] Merge to main branch <!-- id: 25 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-09*
