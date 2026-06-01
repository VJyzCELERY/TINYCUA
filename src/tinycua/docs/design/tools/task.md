# Task Tools

> **File:** `docs/design/tools/task.md`
> **Package:** `tinycua.tools.task`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Overview

Task tools operate on the **shared `Task` tree** stored at `session.task`. They are
split into two categories:

| Category | Tools | Purpose |
|----------|-------|---------|
| **Read** | `ReadActiveTask`, `ReadTask`, `ListTask` | Inspect the task tree without side effects |
| **Write** | `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask`, `UpdateTaskResult`, `UpdateActiveTaskResult` | Mutate task metadata, structure, or task results |
| **Review-scoped write** | `ReviewContextUpdateTool`, `UpdateActiveTaskResult` | Minimal ResultReviewer writes: add targeted context to unfinished tasks and reset active task for retry |

Structural write tools follow a **safe re-indexing pattern** to prevent malformed
indices on partial failures. Task-result update tools only replace `Task.task_result`
and do not alter task structure or task IDs.

---

## Re-Indexing Helper

Every write tool uses the same internal mechanism:

```text
_apply_task_mutation(session: Session, mutator: Callable[[tinycua_sdk.Task], tinycua_sdk.Task]) → tinycua_sdk.Task
    · root = session.task.root()           # 1. keep root in memory
    · mutated = mutator(root)              # 2. apply changes (on a copy)
    · _reindex_tree(mutated)               # 3. re-index entire tree (DFS)
    · session.task = mutated               # 4. atomic replace
    · return mutated

_reindex_tree(root: tinycua_sdk.Task) → None
    · if root.parent_task_id is not None: root.parent_task_id = None  # root must have no parent
    · _reindex_children(root, prefix="T")

_reindex_children(parent: tinycua_sdk.Task, prefix: str) → None
    · if parent.child_tasks is None: return
    · for idx, child in enumerate(parent.child_tasks):
        · child.task_id = f"{prefix}-{idx}"
        · child.parent_task_id = parent.task_id
        · _reindex_children(child, child.task_id)  # recurse into grandchildren
```

**Why re-index?** Task IDs encode position (`T-0.1` = root's second child's first
grandchild). After any mutation (insert, delete, swap), the indices must be recalculated.
Re-indexing before committing ensures no stale or broken IDs exist.

---

## Read Tools

Read tools are **read-only** — no mutation, no re-indexing. They can be given to any
agent that needs to inspect the task tree (e.g., QueryAnalyst for routing decisions).

### `ReadActiveTask`

```text
ReadActiveTask() → dict | None  (@tool, session via closure)
    · if session.task is None → return None
    · active = session.task.traverse()  # DFS pre-order, next non-completed leaf
    · if active is None → return None
    · return _task_to_dict(active)  # { task_id, task_name, task_description, task_context, success_criteria, confidence, parent_task_id, status }
```

### `ReadTask`

```text
ReadTask(task_id: str) → dict | None  (@tool, session via closure)
    · if session.task is None → return None
    · found = session.task.at_id(task_id)
    · if found is None → return None
    · return _task_to_dict(found)
```

### `ListTask`

```text
ListTask() → str  (@tool, session via closure)
    · if session.task is None → return "No active task tree."
    · return session.task.display()  # markdown tree with status markers: [ ] not_started, [*] inprogress, [x] completed, [-] failed, [/] blocked
```

### Shared helper

```text
_task_to_dict(task: tinycua_sdk.Task) → dict
    → return {
        task_id, task_name, task_description, task_context,
        success_criteria, confidence, parent_task_id,
        status: task.task_result.status or "not_started",
        task_result: task.task_result.to_dict() or None,
        child_count: len(task.child_tasks) or 0
    }
```

---

## Write Tools

All write tools follow the `_apply_task_mutation` pattern. The tool receives arguments,
constructs a `mutator` function, and the helper handles cloning + re-indexing + atomic
swap.

For task-result-only updates, the same clone-before-mutate safety rule applies, but
the mutation is limited to `target.task_result`; no structural fields are edited.

### Task Init Data Format

Tools that create tasks accept dictionaries with these fields:

```text
primary_task_data (root task):
    { name: str, description: str, success_criteria: list[str], confidence: float, task_context: str }

sub_task / SubTask (child task):
    { task_name: str, task_description: str, task_context: str, success_criteria: list[str], confidence: float }

# task_id, parent_task_id, child_tasks are assigned internally by the tool
```

Note: `task_id`, `parent_task_id`, `child_tasks` are assigned internally by the tool.

### Task Result Data Format

Task result update tools accept dictionaries with these fields:

```text
{
    status: TaskStatus ("not_started"|"inprogress"|"completed"|"failed"|"blocked"),
    result: str,
    discovered_sequence_issues: list[str] | None,
    uncertainty_notes: list[str] | None,
}
# task_id is intentionally omitted — the owning task already supplies identity
```

`task_id` is intentionally omitted. The result is embedded inside a `Task`, so the
owning task already supplies identity.

---

### `TaskInit`

Replaces the **entire** session task tree with a new root + optional immediate children.

```text
TaskInit(primary_task_data: dict, sub_task: list[dict]? = None) → dict  (@tool)
    · mutator(_root) → tinycua_sdk.Task:
        → root = Task(id="uuid" placeholder, name=primary_task_data["name"], ..., parent_task_id=None, child_tasks=[])
        → for each st in sub_task: create child Task, append to root.child_tasks
        → return root
    · new_root = _apply_task_mutation(session, mutator)  # clones → re-indexes → atomically swaps
    · return { root_id: str, child_ids: list[str], total: int }
```

---

### `SetSubTask`

Replaces a parent's **entire** `child_tasks` list. If the parent already has children,
they are removed and replaced.

```text
SetSubTask(parent_task_id: str, sub_task: list[dict]) → dict  (@tool)
    · mutator(root) → tinycua_sdk.Task:
        → parent = root.at_id(parent_task_id); raise ValueError if not found
        → if empty sub_task: parent.child_tasks = None (container→leaf toggle); return root
        → else: replace parent.child_tasks with new Task objects from sub_task dicts
        → return root
    · new_root = _apply_task_mutation(session, mutator)
    · return { parent_id: str, child_ids: list[str], count: int }
```

---

### `AddSubTask`

Appends new children to the parent's existing `child_tasks` list (preserves existing).

```text
AddSubTask(parent_task_id: str, sub_task: list[dict]) → dict  (@tool)
    · mutator(root) → tinycua_sdk.Task:
        → parent = root.at_id(parent_task_id); raise ValueError if not found
        → if parent.child_tasks is None: parent.child_tasks = []
        → existing_count = len(parent.child_tasks)
        → append new Task objects from sub_task dicts to parent.child_tasks
        → return root
    · new_root = _apply_task_mutation(session, mutator)
    · return { parent_id: str, new_child_ids: list[str] (only newly added), total_children: int }
```

---

### `DeleteSubTask`

Deletes one or more subtasks by ID. If a deleted task has children, they are also
removed.

```text
DeleteSubTask(task_id: str | list[str]) → dict  (@tool)
    · ids = [task_id] if str else task_id
    · mutator(root) → tinycua_sdk.Task:
        · for tid in ids:
            → forbid deleting root task (raise ValueError)
            → _remove_by_id(root, tid, collect_deleted)  # DFS removal, cascading to descendants
        · return root
    · _remove_by_id(parent, target_id, collect) → bool:
        · if parent.child_tasks is None: return False
        · for each child: if child.task_id == target_id:
            → _collect_ids(child, collect)  # collect target + all descendant IDs
            → pop child from parent.child_tasks; toggle to leaf if list is now empty
            → return True
        · recurse into each child; return True if found anywhere
    · _collect_ids(task, collect):
        → add task.task_id; recurse into all descendants
    · _apply_task_mutation(session, mutator)
    · return { deleted_ids: list[str], count: int }
```

---

### `EditSubTask`

Edits metadata and success criteria of an existing task. Structural fields
(`task_id`, `parent_task_id`, `child_tasks`, `task_result`) are not editable
through this tool — they are managed internally.

```text
EditSubTask(task_id: str, task_data: dict) → dict  (@tool)
    · mutator(root) → tinycua_sdk.Task:
        → target = root.at_id(task_id); raise ValueError if not found
        → copy task_name, task_description, task_context, success_criteria, confidence from task_data if present
        · structural fields (task_id, parent_task_id, child_tasks, task_result) are NOT editable
        → return root
    · new_root = _apply_task_mutation(session, mutator)
    · return _task_to_dict(new_root.at_id(task_id))
```

---

### `SwapTask`

Swaps the positions of two tasks in the tree. Can swap sibling tasks, cross-parent
tasks, or a child with an ancestor (reorganizing the tree). Re-indexing after swap
ensures IDs are consistent.

```text
SwapTask(task_id_1: str, task_id_2: str) → dict  (@tool)
    · mutator(root) → tinycua_sdk.Task:
        → forbid swapping root task (raise ValueError)
        → find both tasks and their parents via _find_parent_and_child (DFS)
        → raise ValueError if either task not found
        → check ancestor circularity: if task_1 is ancestor of task_2 (or vice versa) → raise ValueError
        → swap in parent child_tasks lists; update parent_task_id references
        → capture references for post-reindex ID reading
        → return root
    · _find_parent_and_child(parent, target_id) → (Task?, Task?): DFS search for child with matching task_id
    · _is_ancestor(ancestor, target_id) → bool: recursive check for descendant with matching task_id
    · new_root = _apply_task_mutation(session, mutator)  # re-indexes after swap
    · return { swapped: [task_id_1, task_id_2], new_id_1: str, new_id_2: str }
```

---

## Task Result Update Tools

Task result tools update only the `task_result` field on a `Task`. They do not edit
task metadata, child structure, or task IDs.

### `UpdateActiveTaskResult`

Updates the current active executable leaf task. This is the only result-write tool
given to TaskExecutor.

```text
UpdateActiveTaskResult(result_data: dict) → dict  (@tool)
    · mutator(root) → tinycua_sdk.Task:
        → active = root.traverse()  # DFS next non-completed leaf
        → if None: raise ValueError("No active task available.")
        → active.task_result = TaskResult(status=result_data["status"], result=..., discovered_sequence_issues=..., uncertainty_notes=...)
        → capture active.task_id for post-mutation lookup
        → return root
    · new_root = _apply_task_mutation(session, mutator)
    · return _task_to_dict(new_root.at_id(captured_task_id))
```

**Scope:** active task only. No `task_id` parameter is accepted.

---

### `UpdateTaskResult`

Updates the `TaskResult` for any task by explicit `task_id`. This tool is intended
for planning/analysis agents such as TaskAnalyzer, not TaskExecutor.

```text
UpdateTaskResult(task_id: str, result_data: dict) → dict  (@tool)
    · mutator(root) → tinycua_sdk.Task:
        → target = root.at_id(task_id); raise ValueError if not found
        → target.task_result = TaskResult(status=result_data["status"], result=..., discovered_sequence_issues=..., uncertainty_notes=...)
        → return root
    · new_root = _apply_task_mutation(session, mutator)
    · return _task_to_dict(new_root.at_id(task_id))
```

**Scope:** any task by ID. Intended for TaskAnalyzer and other task-management
agents that may need to correct or annotate arbitrary task results.

---

## Review-Scoped Task Tools

ResultReviewer has a deliberately smaller write surface than TaskAnalyzer. It should
not arbitrarily edit task structure. It may only reset the active task for retry and
add context updates to unfinished tasks.

### `ReviewContextUpdateTool`

Adds targeted context updates to unfinished tasks.

```text
ReviewContextUpdateTool(updates: list[dict]) → dict  (@tool)
    · updates format:
        [{"task_id": str, "context": str}, ...]
    · for each update:
        → target = root.at_id(task_id); raise ValueError if not found
        → if target.is_completed: skip by default
        → append context to target.task_context
    · return {updated_task_ids: list[str], skipped_completed_ids: list[str]}
```

`ReviewContextUpdateTool` must avoid updating previous completed tasks unless a future
special override mode explicitly allows it. The default reviewer path updates
unfinished tasks only.

### Reviewer retry reset

ResultReviewer may use `UpdateActiveTaskResult` to reset the active task for retry:

```text
UpdateActiveTaskResult({
    "status": "not_started",
    "result": "Retry required: <reason>. Previous result: <summary>",
    "uncertainty_notes": [retry_instructions],
})
```

This keeps retry behavior scoped to the current active task.

---

## Read-Only Task Tools Constant

```text
READ_ONLY_TASK_TOOLS: list[tinycua_sdk.Tool] = [ReadActiveTask, ReadTask, ListTask]
```

These are injected into agents that need task inspection (e.g., QueryAnalyst when
an active task exists).

## Write Task Tools Constant

```text
WRITE_TASK_TOOLS: list[tinycua_sdk.Tool] = [TaskInit, SetSubTask, AddSubTask, DeleteSubTask, EditSubTask, SwapTask, UpdateTaskResult]
```

Injected into agents that create and manage tasks (e.g., TaskAnalyzer). `TaskInit`
is still excluded from TaskAnalyzer's base tools unless explicitly injected.

## Task Executor Task Tools Constant

```text
TASK_EXECUTOR_BASE_TOOLS: list[tinycua_sdk.Tool] = [*SHARED_AGENT_BASE_TOOLS, ReadActiveTask, ListTask, UpdateActiveTaskResult]
```

TaskExecutor can inspect the active task and task tree, then update only the current
active task's result. It cannot update arbitrary tasks.

## Result Reviewer Task Tools Constant

```text
RESULT_REVIEWER_BASE_TOOLS: list[tinycua_sdk.Tool] = [
    *READ_ONLY_TASK_TOOLS,
    UpdateActiveTaskResult,
    ReviewContextUpdateTool,
]
```

ResultReviewer can inspect tasks, reset the active task for retry, and add targeted
context updates to unfinished tasks. It does not receive broad structural write tools.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Re-index on every write | `_apply_task_mutation` clones → mutates → re-indexes → atomically swaps | No broken indices on crash; task IDs always reflect current position |
| Root ID is UUID | `parent_task_id=None`, `task_id=uuid4()` | Root is unique across sessions; children use `T-{idx}` format |
| Child IDs are positional | `T-0`, `T-0.1`, etc. | Enables `at_id()` O(path) navigation via index path parsing |
| Clone-before-mutate | Mutator receives root, produces new tree | If mutator fails, original tree is untouched |
| Write tools modify session.task directly | Tools receive session via closure | No need to pass session as parameter; same pattern as other tools |
| SwapTask cross-parent | Tasks can swap across different parents | Full tree reorganization; ancestor circularity prevented |
| DeleteSubTask removes descendants | Cascading delete | Consistent — no orphaned subtrees |
| Container ↔ leaf toggle | `child_tasks=None` = leaf, `child_tasks=[]` = empty container | `SetSubTask` with empty list toggles container → leaf |
| Read tools are safe | No re-indexing, no mutation | Can be given to any agent without risk |
| `UpdateActiveTaskResult` scoped to active task | No `task_id` parameter | Prevents TaskExecutor from writing results to the wrong task |
| `UpdateTaskResult` scoped by ID | Explicit `task_id` parameter | Allows TaskAnalyzer to correct or annotate arbitrary task results |
| Reviewer writes are minimal | `ReviewContextUpdateTool` + `UpdateActiveTaskResult` | Reviewer can guide retry/unfinished-task context without arbitrary structural edits |


---


---


---

## See also

Prev : [InformationDigester Tools](digester.md) | Next : [`BaseCompaction` Strategy](../utility/compaction.md)


## Related

- [Task tree + TaskResult](../state/task.md)
- [Shared Task on Session.task](../state/session.md)
- [READ_ONLY_TASK_TOOLS + WRITE_TASK_TOOLS](../constants/tools.md)
- [Used by TaskCreator, TaskExecutor, QueryAnalyst](../agent_sessions/task_creator.md)
