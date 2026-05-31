# Task

> **File:** `docs/design/state/task.md`
> **Package:** `tinycua.state.task`, `tinycua.state.task_result`
> **Last Updated:** 2026-05-31

---

## Role

`Task` is a node in the task execution tree. Navigated via DFS pre-order traversal.
Leaf tasks (`child_tasks=None`) are executable; container tasks derive status from children.

`TaskResult` records the outcome of a single task execution.

---

## Class Contract

### `Task`

**File:** `tinycua/state/task.py`

```python
@dataclass
class Task(StateObject):
    task_id: str                      # UUID for root, T-{idx}.{subidx}... for children
    task_name: str                    # short label
    task_description: str             # agent-readable prose
    task_context: str                 # task-specific structured markdown
    success_criteria: list[str]       # completion criteria
    confidence: float                 # agent confidence
    parent_task_id: str | None = None
    task_result: TaskResult | None = None
    child_tasks: list[Task] | None = None  # None = leaf, list = container
    # _parent: Task | None (hidden, re-established after deserialization)
```

### `TaskResult`

**File:** `tinycua/state/task_result.py`

```python
@dataclass
class TaskResult(StateObject):
    task_id: str
    status: TaskStatus  # Literal["not_started","inprogress","completed","failed","blocked"]
    result: str
    discovered_sequence_issues: list[str] | None = None
    uncertainty_notes: list[str] | None = None
```

---

## Key Methods (Task)

| Method | Returns | Description |
|--------|---------|-------------|
| `is_completed` | `bool` | Leaf: `task_result.status == "completed"`. Container: all children completed |
| `traverse()` | `Task` | DFS pre-order: find next non-completed executable leaf |
| `at_id(task_id)` | `Task` | Navigate to any node by ID from anywhere |
| `root()` | `Task` | Walk up `_parent` chain to root |
| `parent` (property) | `Task \| None` | Direct parent via `_parent` reference |
| `is_root()` | `bool` | True if `_parent is None` |
| `set_parents()` | `None` | Re-establish `_parent` references — called after deserialization |
| `display()` | `str` | Tree display with status markers: `[ ]` not_started, `[*]` inprogress, `[x]` completed, `[-]` failed, `[/]` blocked |

---

## Tree Rules

- Root: `parent_task_id=None`, ID is UUID
- Child: ID format `T-{idx}.{subidx}...`, `_parent` set in `__post_init__`
- Container: has `child_tasks`, not executed directly, completion derived from children
- Leaf: `child_tasks=None`, executable, may have `task_result`
- After deserialization: `Task.from_dict()` auto-calls `set_parents()`

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tree via _parent references | Hidden field, not serialized | O(1) upward traversal; re-established via set_parents() |
| Child ID format | `T-{idx}.{subidx}...` | Enables efficient at_id() navigation via index path |
| Container vs leaf | `child_tasks is None` = leaf | Single field toggles execution semantics |
| DFS pre-order | `traverse()` | Natural execution order: depth-first left-to-right |


---


---


---

## See also

Prev : [`AgentState` Lifecycle Tracking](agent_state.md) | Next : [`ModeDecision` + `ContextEnhancedQuery`](mode_decision.md)


## Related

- [Shared Task object on Session.task](session.md)
- [TaskResult is the output of each execution](worker_result.md)
