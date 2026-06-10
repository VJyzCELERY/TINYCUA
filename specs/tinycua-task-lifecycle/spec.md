# Feature Specification: TaskTree Active Task Lifecycle

**Status**: Approved
**Created**: 2026-06-10
**Last Updated**: 2026-06-10
**Subproject(s) Affected**: tinycua (models/task, loops/tinycua_loop)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a structured `Task` model, `TaskResult` model, `ReviewerDecision` model, DFS-based active task selection, and task-tree completion/update algorithm so that **TinyCUALoop** can **manage the full active task lifecycle from selection through execution, review, and completion**.
- **Gaps**: The current `Session` model stores `task` as a plain `str | None`. There is no structured Task tree, no `TaskResult` model, no `ReviewerDecision` model, and no active task selection or completion/update algorithm. TaskExecutor and ResultReviewer cannot participate in the active task handoff protocol without these primitives.
- **Non-Goals**: This spec does NOT cover TaskExecutor node behavior (Milestone 3.2), ResultReviewer node behavior (Milestone 3.2), ResultAggregationNode (Milestone 3.4), or ResponseNode (Milestone 3.5). It does NOT cover task creation tools or task analysis nodes.
- **Constraints**: Must work without modifying `tinycua-sdk` public APIs. Task models are mutable dataclasses that should be treated as immutable value objects during transport (copy-on-transfer). Mutation of Task trees must go through explicit TinyCUALoop task helpers — direct mutation outside the loop is prohibited. The `Session.task` field will remain as `str | None` for backward compatibility. The structured Task tree is owned by TinyCUALoop as `self.root_task`, separate from `Session`.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

TinyCUA's execution loop needs to track which task in a decomposed task tree is currently being executed. When a WorkerNode creates a task tree (via TaskCreate/TaskAnalyzer), the loop selects the first unfinished task using DFS pre-order traversal. TaskExecutor receives this active task, executes it, and produces a `TaskResult`. ResultReviewer evaluates the result and decides to accept, retry, replan, or ask an open question. On accept, the loop recomputes the next active task. On root-task completion, the loop routes to ResultAggregationNode.

### Acceptance Scenarios

1. **Given** a root task with children `[T-1 (done), T-2 (pending), T-3 (pending)]`, **When** `get_active_task()` is called, **Then** it returns `T-2` (first unfinished task in DFS pre-order).
2. **Given** a root task with all children complete, **When** `get_active_task()` is called, **Then** it returns the root task itself if it is not yet marked complete.
3. **Given** a root task with all tasks complete, **When** `get_active_task()` is called, **Then** it returns `None`.
4. **Given** an active task `T-2` with `active_child_id = "T-2.1"`, **When** `get_active_task()` starts DFS from `T-2`, **Then** it resumes from `T-2.1` using the traversal hint.
5. **Given** TaskExecutor completes execution of `T-2`, **When** ResultReviewer decides `accept`, **Then** `T-2` is marked done and the loop recomputes the next active task.
6. **Given** ResultReviewer decides `retry` for `T-2`, **When** the loop processes the decision, **Then** `T-2` remains the active task and TaskExecutor is re-queued.
7. **Given** ResultReviewer decides `replan` for `T-2`, **When** the loop processes the decision, **Then** TaskAssessor and TaskAnalyzer are spawned before TaskExecutor.
8. **Given** ResultReviewer decides `open_question` for `T-2`, **When** the loop processes the decision, **Then** ResultReviewer remains active with mandatory_passthrough targeting its session.
9. **Given** the root task is the active task and all children are complete, **When** ResultReviewer accepts, **Then** the root task is marked done and the loop routes to ResultAggregationNode.
10. **Given** a Task with `status="done"` and a valid `TaskResult`, **When** the result is inspected, **Then** `TaskResult.execution_status` is `"succeeded"` and `reviewer_decision` is set.

### Edge Cases

- What happens when the task tree is `None`? `get_active_task()` returns `None`.
- What happens when `active_child_id` references a non-existent task? DFS falls back to standard pre-order traversal from the parent.
- What happens when a task has no children and is not complete? It is selected as the active task for execution.
- What happens when `set_active_task()` is called with an unknown `task_id`? The method raises a `ValueError`.
- What happens when `update_active_task_result()` is called with no active task? The method raises a `ValueError`.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a `Task` dataclass with fields: `task_id`, `title`, `description`, `status`, `children`, `active_child_id`, `result`, `metadata`.
- **FR-002**: System MUST provide a `TaskResult` dataclass with fields: `task_id`, `execution_status`, `reviewer_decision`, `summary`, `artifacts`, `metadata`.
- **FR-003**: System MUST provide a `ReviewerDecision` dataclass with fields: `outcome`, `rationale`, `target_task_id`, `metadata`.
- **FR-004**: System MUST support task statuses: `pending`, `in_progress`, `blocked`, `done`, `failed`.
- **FR-005**: System MUST support execution statuses: `not_started`, `running`, `succeeded`, `failed`, `blocked`.
- **FR-006**: System MUST support reviewer decision outcomes: `accept`, `retry`, `replan`, `open_question`.
- **FR-007**: TinyCUALoop MUST provide `get_active_task() -> Task | None` using DFS pre-order traversal of the root task tree.
- **FR-008**: TinyCUALoop MUST provide `set_active_task(task_id: str) -> None` to explicitly set the active task.
- **FR-009**: TinyCUALoop MUST provide `update_active_task_result(result: TaskResult) -> None` to update the active task's result.
- **FR-010**: DFS pre-order traversal MUST use `active_child_id` as a traversal hint when available.
- **FR-011**: The active-task predicate MUST select the first unfinished task (status in `pending`, `in_progress`, `blocked`).
- **FR-012**: On ResultReviewer `accept`, the system MUST recompute the next active task using DFS.
- **FR-013**: On ResultReviewer `retry`, the system MUST preserve the same active task.
- **FR-014**: On ResultReviewer `replan`, the system MUST preserve the same active task and spawn TaskAssessor + TaskAnalyzer.
- **FR-015**: On ResultReviewer `open_question`, the system MUST preserve the same active task and install mandatory_passthrough.
- **FR-016**: When the root task is complete (all children done, root status updated), the system MUST signal that ResultAggregationNode should be entered.
- **FR-017**: `Task.children` is an append-only list. No explicit `add_child`/`remove_child` helpers are exposed in this milestone — mutation occurs through TinyCUALoop lifecycle methods only (`update_active_task_result`, `_on_reviewer_accept`, etc.).
- **FR-018**: System MUST NOT modify `tinycua-sdk` public APIs.

### Key Entities _(include if feature involves data)_

- **Task**: A node in the task tree. Has a unique `task_id`, human-readable `title` and `description`, a `status` from the valid status set, optional `children` (sub-tasks), an `active_child_id` traversal hint, an optional `TaskResult`, and arbitrary `metadata`.
- **TaskResult**: The execution outcome of a task. Contains `task_id`, `execution_status`, optional `ReviewerDecision`, a `summary` string, a list of `artifacts`, and `metadata`.
- **ReviewerDecision**: The outcome of a result review. Contains `outcome` (accept/retry/replan/open_question), optional `rationale`, optional `target_task_id`, and `metadata`.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Task model exists**: `Task` dataclass with all specified fields is implemented.
- [ ] **TaskResult model exists**: `TaskResult` dataclass with all specified fields is implemented.
- [ ] **ReviewerDecision model exists**: `ReviewerDecision` dataclass with all specified fields is implemented.
- [ ] **DFS active task selection works**: `get_active_task()` returns the correct task for linear, nested, and empty trees.
- [ ] **Traversal hint works**: `active_child_id` causes DFS to resume from the hinted child.
- [ ] **set_active_task works**: Sets the active task by ID; raises on unknown ID.
- [ ] **update_active_task_result works**: Updates the active task's result; raises when no active task.
- [ ] **Accept recomputes active task**: After accept, next DFS active task is selected or root-done signal is emitted.
- [ ] **Retry preserves active task**: After retry, same task remains active.
- [ ] **Replan preserves active task**: After replan, same task remains active.
- [ ] **Open question preserves active task**: After open_question, same task remains active.
- [ ] **Root-done detection works**: When root task and all children are complete, system signals aggregation entry.
- [ ] **No SDK changes**: All implementation lives in `tinycua.models` and `tinycua.loops`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test `Task` dataclass construction, default values, and field validation.
- Test `TaskResult` dataclass construction and field validation.
- Test `ReviewerDecision` dataclass construction and field validation.
- Test `get_active_task()` with linear task trees (no children, single child, multiple children).
- Test `get_active_task()` with nested task trees (children with children).
- Test `get_active_task()` with `active_child_id` traversal hint.
- Test `get_active_task()` returns `None` when all tasks are complete.
- Test `get_active_task()` returns `None` when task tree is `None`.
- Test `set_active_task()` with valid and invalid task IDs.
- Test `update_active_task_result()` with valid active task and with no active task.
- Test task-tree completion/update algorithm for accept, retry, replan, and open_question decisions.
- Test root-done detection when all children and root are complete.

### Integration Tests

> **Note**: Integration tests requiring TaskExecutor and ResultReviewer are deferred to
> Milestone 3.2. Milestone 3.1 validates lifecycle behavior through unit tests (see
> `implementation-plan.md`). Add this section when TaskExecutor and ResultReviewer exist.

### Manual Tests _(if applicable)_

- None required for this milestone.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Task model | TODO | |
| TaskResult model | TODO | |
| ReviewerDecision model | TODO | |
| DFS active task selection | TODO | |
| set_active_task / update_active_task_result | TODO | |
| Task-tree completion/update algorithm | TODO | |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **Task tree storage location**: Should the root task tree be stored on `Session.task` (replacing the current `str | None`) or on `TinyCUALoop` directly?
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Accepted
   - **Proposed Answer**: Store on `TinyCUALoop` as `self.root_task: Task | None`. `Session.task` remains a string for backward compatibility or is removed. The loop owns the task tree per the ownership rules in the design doc.

2. **active_child_id update timing**: Should `active_child_id` be updated immediately when a child is selected, or lazily on the next `get_active_task()` call?
   - **Owner**: @VJyzCELERY
   - **Target**: 2026-06-10
   - **Status**: Accepted
   - **Proposed Answer**: Update lazily on `get_active_task()` — the traversal writes back the hint as it descends. This avoids stale hints from intermediate mutations.

---

## Review Checklist

- [ ] No implementation details — code, framework, or architecture choices must live in design docs only
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable

---

## References

- Design: `./design.md`
- Design docs:
  - `src/tinycua/docs/design/models/task.md` — Task model and active task selection
  - `src/tinycua/docs/design/models/reviewer_decision.md` — ReviewerDecision model
  - `src/tinycua/docs/design/loops/task_executor.md` — TaskExecutor node (Milestone 3.2)
  - `src/tinycua/docs/design/loops/result_reviewer.md` — ResultReviewer node (Milestone 3.2)
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — TinyCUALoop execution flow
- Issue: [#87](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Milestone 3.1
