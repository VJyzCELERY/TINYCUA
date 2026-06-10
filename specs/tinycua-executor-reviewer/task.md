# Tasks: TaskExecutor and ResultReviewer Nodes

Implementation tasks for Milestone 3.2 — Executor & Reviewer Nodes. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests in `src/tinycua/tests/integration/test_executor_reviewer_integration.py` (defined in implementation-plan.md) <!-- id: 0 -->
  - **Note**: Create the file if it doesn't exist. Directory `src/tinycua/tests/integration/` already exists.
  - [ ] test_executor_reviewer_accept_path
  - [ ] test_executor_reviewer_retry_path
  - [ ] test_executor_reviewer_replan_path
  - [ ] test_retry_threshold_enforcement
  - [ ] test_retry_counter_resets_on_accept
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create `tinycua/models/reviewer_decision.py` with ReviewerRetryState dataclass <!-- id: 2 -->
  - [ ] ReviewerRetryState: increment(), reset(), can_retry(), is_threshold_reached()
- [ ] Export ReviewerDecision + ReviewerRetryState from `tinycua/models/__init__.py` <!-- id: 3 -->
- [ ] Create `tinycua/loops/task_executor.py` with TinyCUATaskExecutorNode <!-- id: 4 -->
  - [ ] Extend ProcessNode, implement __call__ with ReAct execution
  - [ ] Implement on_complete to advance queue
  - [ ] Raise NodeExecutionError when no active task provided
- [ ] Create `tinycua/loops/result_reviewer.py` with TinyCUAResultReviewerNode <!-- id: 5 -->
  - [ ] Extend ProcessNode, implement __call__ to evaluate execution result
  - [ ] Implement on_complete to dispatch based on decision (accept/retry/replan/open_question)
  - [ ] Fallback to retry when decision cannot be parsed
- [ ] Update `tinycua/loops/__init__.py` to export new node classes <!-- id: 6 -->
- [ ] Add `_reviewer_retry_state` to TinyCUALoop.__init__ <!-- id: 7 -->
- [ ] Implement TinyCUALoop._on_reviewer_retry() (replace no-op stub) <!-- id: 8 -->
  - [ ] Increment retry count via _reviewer_retry_state.increment()
  - [ ] Log warning if threshold reached
  - [ ] Preserve active task
- [ ] Implement TinyCUALoop._on_reviewer_replan() (replace no-op stub) <!-- id: 9 -->
  - [ ] Log replan event
  - [ ] Preserve active task
  - [ ] Signal for TaskAssessor + TaskAnalyzer spawning
- [ ] Implement TinyCUALoop._on_reviewer_open_question() (replace no-op stub) <!-- id: 10 -->
  - [ ] Log open question event
  - [ ] Preserve active task
  - [ ] Signal for mandatory_passthrough installation
- [ ] Update TinyCUALoop._on_reviewer_accept() to reset retry counter <!-- id: 11 -->
- [ ] Replace AnalysisEffortNode._spawn_task_executor() stub <!-- id: 12 -->
  - [ ] Import TinyCUATaskExecutorNode and TinyCUAResultReviewerNode
  - [ ] Instantiate and spawn after current position
  - [ ] Ensure terminal response path
- [ ] Replace WorkerNode._route_proceed_execution() stub <!-- id: 13 -->
  - [ ] Import TinyCUATaskExecutorNode and TinyCUAResultReviewerNode
  - [ ] Clear after current, spawn executor+reviewer
  - [ ] Ensure terminal response path

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 14 -->
- [ ] Write unit tests for ReviewerRetryState <!-- id: 15 -->
  - [ ] test_increment, test_reset, test_can_retry, test_threshold_enforced
- [ ] Write unit tests for TinyCUATaskExecutorNode <!-- id: 16 -->
  - [ ] test_construction, test_call_with_mocked_llm, test_raises_when_no_active_task, test_on_complete_advances_queue
- [ ] Write unit tests for TinyCUAResultReviewerNode <!-- id: 17 -->
  - [ ] test_construction, test_call_accept, test_call_retry, test_call_replan, test_call_open_question
- [ ] Write unit tests for updated loop handlers <!-- id: 18 -->
  - [ ] test_on_reviewer_retry_increments_count, test_on_reviewer_replan_preserves_task, test_on_reviewer_open_question_preserves_task
- [ ] Write unit tests for updated spawning logic <!-- id: 19 -->
  - [ ] test_analysis_effort_spawn_task_executor, test_worker_route_proceed_execution
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 20 -->

## Verification Phase

- [ ] Verify no SDK public API changes: `git diff main -- src/tinycua-sdk/` shows no changes <!-- id: 21 -->
- [ ] Manual test: run `create_tinycua_agent(...).run(...)` with a simple task and verify executor→reviewer path completes <!-- id: 22 -->
- [ ] Verify ReAct iteration cap prevents infinite loops <!-- id: 23 -->
- [ ] Verify retry threshold enforcement: after 5 retries, reviewer cannot retry <!-- id: 24 -->

## Documentation Phase

- [ ] Update design docs if any decisions changed from implementation <!-- id: 25 -->
- [ ] Update spec success criteria checkboxes once verified <!-- id: 26 -->

## Review and Merge

- [ ] Self-review: verify all FR items from spec are covered <!-- id: 27 -->
- [ ] Address review feedback <!-- id: 28 -->
- [ ] Merge to feat/tinycua-research-prototype <!-- id: 29 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-10*
