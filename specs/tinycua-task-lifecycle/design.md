# Design Document: TaskTree Active Task Lifecycle

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-10

---

## Overview

This design introduces structured Task, TaskResult, and ReviewerDecision models into `tinycua.models`, adds DFS-based active task selection and task-tree completion/update helpers to `TinyCUALoop`, and establishes the active task handoff protocol between the loop, TaskExecutor, and ResultReviewer. The design follows `src/tinycua/docs/design/models/task.md` and `src/tinycua/docs/design/loops/tinycua_loop.md`.

---

## Architecture

### Component Overview

```
tinycua.models.task
├── Task (dataclass)
├── TaskResult (dataclass)
├── ReviewerDecision (dataclass)
├── TaskStatus (type alias)
├── ExecutionStatus (type alias)
└── ReviewerOutcome (type alias)

tinycua.loops.tinycua_loop
├── TinyCUALoop.root_task: Task | None
├── TinyCUALoop._active_task_id: str | None
├── get_active_task() → Task | None          [DFS pre-order]
├── set_active_task(task_id) → None
├── update_active_task_result(result) → None
├── _dfs_find_active(task) → Task | None       [internal DFS]
├── _on_reviewer_accept(active_task) → None   [task-tree update]
├── _on_reviewer_retry(active_task) → None    [preserve active]
├── _on_reviewer_replan(active_task) → None   [preserve + spawn]
├── _on_reviewer_open_question(active_task) → None [preserve + passthrough]
└── _is_root_task_done() → bool
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/models/task.py` | New | Task, TaskResult, ReviewerDecision dataclasses and type aliases |
| `tinycua/models/__init__.py` | Modified | Export new model types |
| `tinycua/loops/tinycua_loop.py` | Modified | Add root_task, active task helpers, completion/update algorithm |
| `tinycua/models/session.py` | Referenced | `Session.task` field remains for backward compat; loop owns the structured tree |

---

## Data Model

### Task

```python
@dataclass
class Task:
    task_id: str
    title: str
    description: str = ""
    status: TaskStatus = "pending"          # pending | in_progress | blocked | done | failed
    children: list[Task] = field(default_factory=list)
    active_child_id: str | None = None      # traversal hint
    result: TaskResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### TaskResult

```python
@dataclass
class TaskResult:
    task_id: str
    execution_status: ExecutionStatus = "not_started"  # not_started | running | succeeded | failed | blocked
    reviewer_decision: ReviewerDecision | None = None
    summary: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

### ReviewerDecision

```python
@dataclass
class ReviewerDecision:
    outcome: ReviewerOutcome              # accept | retry | replan | open_question
    rationale: str | None = None
    target_task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### Type Aliases

```python
TaskStatus = Literal["pending", "in_progress", "blocked", "done", "failed"]
ExecutionStatus = Literal["not_started", "running", "succeeded", "failed", "blocked"]
ReviewerOutcome = Literal["accept", "retry", "replan", "open_question"]
```

---

## API / Interface Contracts

### TinyCUALoop Task Helpers

```python
class TinyCUALoop(BaseLoop):
    root_task: Task | None                  # owned by the loop
    _active_task_id: str | None             # current active task id

    def get_active_task(self) -> Task | None:
        """
        Resolve the active task via DFS pre-order traversal of self.root_task.
        Uses _active_task_id as a traversal hint when set.
        Returns None if root_task is None or all tasks are complete.
        """

    def set_active_task(self, task_id: str) -> None:
        """
        Explicitly set the active task by task_id.
        Raises ValueError if task_id is not found in the task tree.
        """

    def update_active_task_result(self, result: TaskResult) -> None:
        """
        Update the active task's result field.
        Raises ValueError if no active task is set.
        """
```

### DFS Pre-Order Traversal

```python
def _dfs_find_active(self, task: Task) -> Task | None:
    """
    DFS pre-order traversal returning the first unfinished task.
    Unfinished means status in {"pending", "in_progress", "blocked"}.
    When active_child_id is set, descends into that child first.
    """
    # 1. Check if this task is unfinished → return it
    # 2. If active_child_id is set, search that child first
    # 3. Then search remaining children in order
    # 4. Return None if all children are complete
    # Note: If active_child_id references a non-existent child, fall back to
    # standard pre-order traversal (ignore the hint and iterate children in
    # insertion order).
```

### Task-Tree Completion/Update Algorithm

```python
def _on_reviewer_accept(self, active_task: Task) -> bool:
    """
    Handle ResultReviewer accept decision.

    Returns True if root task is done (should route to aggregation).
    Returns False if there is a next active task (should route to executor).

    Algorithm:
    1. Mark active_task.result.reviewer_decision = ReviewerDecision(outcome="accept")
    2. Mark active_task.status = "done"
    3. If active_task is root_task and all children done → root done → return True
    4. If active_task has unfinished children → DFS to next child → return False
    5. If active_task has no unfinished children → check parent completion
    6. Walk up: if parent has no unfinished children → mark parent done → continue up
    7. If root reached and done → return True
    8. Otherwise → DFS from parent's next sibling → return False
    """
    # Note: This algorithm simplifies the target architecture doc's
    # on_result_reviewer_accept behavior. The architecture doc allows
    # re-evaluation of parent task completion after all children are done
    # (parent may need re-execution). This simplification marks parents as
    # done when all children complete. The re-evaluation behavior can be
    # added in a later milestone if needed.

def _on_reviewer_retry(self, active_task: Task) -> None:
    """Preserve active task. No recomputation needed."""

def _on_reviewer_replan(self, active_task: Task) -> None:
    """Preserve active task. Caller spawns TaskAssessor + TaskAnalyzer."""

def _on_reviewer_open_question(self, active_task: Task) -> None:
    """Preserve active task. Caller installs mandatory_passthrough."""
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `set_active_task()` with unknown ID | `ValueError("Task not found: {task_id}")` | Task ID not in tree |
| `update_active_task_result()` with no active task | `ValueError("No active task set")` | No task is currently active |
| `get_active_task()` with empty tree | Returns `None` | Graceful — no task to select |
| Task tree is `None` | Returns `None` | Graceful — no tree exists |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `tinycua/models/task.py` with `Task`, `TaskResult`, `ReviewerDecision` dataclasses
- [ ] Define `TaskStatus`, `ExecutionStatus`, `ReviewerOutcome` type aliases
- [ ] Update `tinycua/models/__init__.py` to export new types
- [ ] Add `root_task` and `_active_task_id` attributes to `TinyCUALoop.__init__`
- [ ] Implement `get_active_task()` with DFS pre-order traversal and `active_child_id` hint
- [ ] Implement `set_active_task(task_id)` with validation
- [ ] Implement `update_active_task_result(result)` with validation
- [ ] Implement `_dfs_find_active(task)` internal DFS helper
- [ ] Implement `_on_reviewer_accept(active_task)` task-tree completion algorithm
- [ ] Implement `_on_reviewer_retry(active_task)` preserve-active stub
- [ ] Implement `_on_reviewer_replan(active_task)` preserve-active stub
- [ ] Implement `_on_reviewer_open_question(active_task)` preserve-active stub
- [ ] Implement `_is_root_task_done()` helper
- [ ] Write unit tests for all models, DFS traversal, and completion/update algorithm

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- None for this milestone. Task tree mutation helpers (add_child, remove_child) are deferred to task creation milestones.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Store `root_task` on `TinyCUALoop` rather than on `Session`.
   - **Reason**: The design doc says "TinyCUALoop owns root task and active task id." The loop is the owner and the mutation boundary. `Session` is a data container; putting the task tree on the loop keeps ownership clear and avoids conflating session data with execution state.
   - **Alternatives Considered**: Store on `Session.task` replacing the string — rejected because `Session` is a value object that may be serialized/copied, and the task tree is execution state that belongs to the loop.

2. **Decision**: Use `active_child_id` as a traversal hint rather than a stack-based iterator.
   - **Reason**: The design doc specifies `active_child_id` as "a traversal hint maintained by the loop." A hint-based approach is simpler to serialize/debug and works with the append-only task tree model. A stack-based iterator would require additional state management.
   - **Alternatives Considered**: Stack-based iterator — rejected for complexity and serialization difficulty.

3. **Decision**: `_on_reviewer_accept` returns a boolean (root-done flag) rather than an enum.
   - **Reason**: The only two outcomes needed are "root done → route to aggregation" and "not done → route to executor." A boolean is the simplest representation. If more granular routing is needed later, it can be promoted to an enum.
   - **Alternatives Considered**: Enum return — rejected for over-engineering when two outcomes suffice.

4. **Decision**: Keep `Session.task: str | None` for backward compatibility.
   - **Reason**: Existing code and tests reference `session.task` as a string. Removing it would break existing callers. The structured task tree lives on the loop; `session.task` can be set to a summary string or removed in a later cleanup milestone.
   - **Alternatives Considered**: Remove `Session.task` entirely — rejected for breaking existing callers without a migration path.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| DFS traversal incorrect for deeply nested trees | Low | High | Comprehensive unit tests with nested trees up to 4 levels deep |
| `active_child_id` hint becomes stale after task mutations | Medium | Medium | Update hint lazily on each `get_active_task()` call; re-validate hint exists before using it |
| Backward compatibility breakage from Session.task changes | Low | Medium | Keep `Session.task` as string; loop owns the structured tree separately |
| Accept algorithm infinite loop when walking up parent chain | Low | High | Add cycle detection (visited set) and depth limit to parent walk |
| Task tree mutation during traversal causes inconsistency | Low | High | Traverse a snapshot or validate tree integrity before traversal |

---

## Open Questions _(optional)_

1. **Task tree serialization**: Should Task/TaskResult be serializable to JSON for transcript export?
   - **Owner**: @VJyzCELERY
   - **Status**: Proposed
   - **Proposed Answer**: Yes, dataclasses with `field(default_factory=dict)` and standard types are JSON-serializable by default with a simple encoder. No special serialization needed.

2. **Thread safety**: Is concurrent access to the task tree a concern?
   - **Owner**: @VJyzCELERY
   - **Status**: Proposed
   - **Proposed Answer**: No — TinyCUA is single-threaded per execution loop. Task tree mutations happen sequentially within the loop's node execution cycle.

---

## References

- Spec: `./spec.md`
- Design docs:
  - `src/tinycua/docs/design/models/task.md` — Task model, active task selection, handoff protocol
  - `src/tinycua/docs/design/models/reviewer_decision.md` — ReviewerDecision model
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — TinyCUALoop execution flow and ownership
  - `src/tinycua/docs/design/loops/task_executor.md` — TaskExecutor node (Milestone 3.2)
  - `src/tinycua/docs/design/loops/result_reviewer.md` — ResultReviewer node (Milestone 3.2)
- Existing specs:
  - `specs/tinycua-task-analyzer/spec.md` — TaskAnalyzerNode (completed, Milestone 2.6)
- Issue: [#87](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Milestone 3.1
