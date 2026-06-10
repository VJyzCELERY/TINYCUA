# Tasks: TaskTree Active Task Lifecycle

Implementation tasks for TaskTree Active Task Lifecycle (Milestone 3.1). Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write unit tests for Task, TaskResult, ReviewerDecision models in `tests/unit/test_task_models.py` (relative to `src/tinycua/`) <!-- id: 0 -->
- [ ] Write unit tests for TinyCUALoop active task lifecycle helpers in `tests/unit/test_task_lifecycle.py` (relative to `src/tinycua/`) <!-- id: 1 -->
- [ ] Run tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

- [ ] Create `tinycua/models/task.py` with Task, TaskResult, ReviewerDecision dataclasses and type aliases <!-- id: 3 -->
  - [ ] Define `TaskStatus`, `ExecutionStatus`, `ReviewerOutcome` Literal type aliases
  - [ ] Implement `Task` dataclass with all fields
  - [ ] Implement `TaskResult` dataclass with all fields
  - [ ] Implement `ReviewerDecision` dataclass with all fields
- [ ] Update `tinycua/models/__init__.py` to export new types <!-- id: 4 -->
- [ ] Add `root_task` and `_active_task_id` attributes to `TinyCUALoop.__init__` <!-- id: 5 -->
- [ ] Implement `get_active_task()` with DFS pre-order traversal and `active_child_id` hint <!-- id: 6 -->
  - [ ] Implement `_dfs_find_active(task)` internal DFS helper
  - [ ] Handle `active_child_id` traversal hint with fallback for invalid hints
- [ ] Implement `set_active_task(task_id)` with validation <!-- id: 7 -->
- [ ] Implement `update_active_task_result(result)` with validation <!-- id: 8 -->
- [ ] Implement `_on_reviewer_accept(active_task)` task-tree completion algorithm <!-- id: 9 -->
  - [ ] Mark active task as done
  - [ ] Walk up parent chain and mark parents done when all children complete
  - [ ] Return True if root task is done, False otherwise
- [ ] Implement `_on_reviewer_retry(active_task)` preserve-active stub <!-- id: 10 -->
- [ ] Implement `_on_reviewer_replan(active_task)` preserve-active stub <!-- id: 11 -->
- [ ] Implement `_on_reviewer_open_question(active_task)` preserve-active stub <!-- id: 12 -->
- [ ] Implement `_is_root_task_done()` helper <!-- id: 13 -->

## Testing Phase

- [ ] Run unit tests — expect GREEN (all pass) <!-- id: 14 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 15 -->

## Verification Phase

- [ ] Verify `Task`, `TaskResult`, `ReviewerDecision` importable from `tinycua.models` <!-- id: 16 -->
- [ ] Verify DFS handles linear trees (no children, single child, multiple children) <!-- id: 17 -->
- [ ] Verify DFS handles nested trees (children with children, 4+ levels) <!-- id: 18 -->
- [ ] Verify DFS handles edge cases (None tree, all done, invalid hint) <!-- id: 19 -->
- [ ] Verify accept/retry/replan/open_question all behave correctly <!-- id: 20 -->
- [ ] Verify root-done detection when all children and root are complete <!-- id: 21 -->

## Documentation Phase

- [ ] No API docs needed for this milestone (internal helpers only) <!-- id: 22 -->

## Review and Merge

- [ ] Commit changes and push to PR branch <!-- id: 23 -->
- [ ] Address review feedback <!-- id: 24 -->
- [ ] Merge to base branch <!-- id: 25 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-10*
