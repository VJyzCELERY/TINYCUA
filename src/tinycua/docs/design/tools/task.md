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
| **Write** | `TaskInit`, `SetSubTask`, `AddSubTask`, `DeleteSubTask`, `EditSubTask`, `SwapTask` | Mutate the task tree with atomic re-indexing |

All write tools follow a **safe re-indexing pattern** to prevent malformed indices on
partial failures.

---

## Re-Indexing Helper

Every write tool uses the same internal mechanism:

```python
def _apply_task_mutation(
    session: Session,
    mutator: Callable[[Task], Task],
) -> Task:
    """Apply a mutation to the task tree with re-indexing.

    1. Clone the root task (keep reference in memory).
    2. Apply the mutator to produce a modified copy.
    3. Re-index the entire tree (DFS).
    4. Atomically replace session.task with the re-indexed tree.

    This ensures:
    - If the mutator fails, the original tree is untouched.
    - After mutation, all task IDs follow T-{idx}.{subidx}... format.
    - No broken indices from partial updates.
    """
    root = session.task.root()           # 1. Keep root in memory
    mutated = mutator(root)              # 2. Apply changes (on a copy)
    _reindex_tree(mutated)               # 3. Re-index
    session.task = mutated               # 4. Atomic replace
    return mutated


def _reindex_tree(root: Task) -> None:
    """Re-index the entire task tree with DFS order.

    Root keeps its UUID. Children get T-0, T-0.0, T-0.1, T-1, ...
    in DFS pre-order. Updates task_id and parent_task_id on every node.
    """
    if root.parent_task_id is not None:
        root.parent_task_id = None  # root must have no parent

    _reindex_children(root, prefix="T")


def _reindex_children(parent: Task, prefix: str) -> None:
    """Re-index all children of parent with DFS enumeration."""
    if parent.child_tasks is None:
        return

    for idx, child in enumerate(parent.child_tasks):
        child.task_id = f"{prefix}-{idx}"
        child.parent_task_id = parent.task_id

        # Recurse into grandchildren
        _reindex_children(child, child.task_id)
```

**Why re-index?** Task IDs encode position (`T-0.1` = root's second child's first
grandchild). After any mutation (insert, delete, swap), the indices must be recalculated.
Re-indexing before committing ensures no stale or broken IDs exist.

---

## Read Tools

Read tools are **read-only** — no mutation, no re-indexing. They can be given to any
agent that needs to inspect the task tree (e.g., QueryAnalyst for routing decisions).

### `ReadActiveTask`

```python
from tinycua_sdk.tools.decorators import tool


@tool
def ReadActiveTask() -> dict | None:
    """Retrieve the currently active (executable) task in the session.

    Returns the next non-completed leaf task via DFS pre-order traversal
    (session.task.traverse()). Returns None if no active task exists.

    The returned dict contains:
        task_id, task_name, task_description, task_context,
        success_criteria, confidence, parent_task_id, status
    """
    # session captured via closure
    task = session.task
    if task is None:
        return None

    active = task.traverse()
    if active is None:
        return None

    return _task_to_dict(active)
```

### `ReadTask`

```python
@tool
def ReadTask(task_id: str) -> dict | None:
    """Read a specific task by its ID from the current session task tree.

    Args:
        task_id: The task ID to look up (e.g., "T-0", "T-0.1").

    Returns:
        The task as a dict, or None if not found.
    """
    task = session.task
    if task is None:
        return None

    found = task.at_id(task_id)
    if found is None:
        return None

    return _task_to_dict(found)
```

### `ListTask`

```python
@tool
def ListTask() -> str:
    """Display the current session task tree.

    Returns a markdown tree view with status markers:
      [ ] not_started
      [*] inprogress
      [x] completed
      [-] failed
      [/] blocked

    Example output:
      Task Tree:
      [*] T-0: Set up nginx
       ├── [x] T-0.0: Install nginx
       └── [*] T-0.1: Configure virtual hosts
            └── [ ] T-0.1.0: Test configuration
    """
    task = session.task
    if task is None:
        return "No active task tree."

    return task.display()
```

### Shared helper

```python
def _task_to_dict(task: Task) -> dict:
    """Convert a Task to a tool-friendly dict."""
    return {
        "task_id": task.task_id,
        "task_name": task.task_name,
        "task_description": task.task_description,
        "task_context": task.task_context,
        "success_criteria": task.success_criteria,
        "confidence": task.confidence,
        "parent_task_id": task.parent_task_id,
        "status": task.task_result.status if task.task_result else "not_started",
        "child_count": len(task.child_tasks) if task.child_tasks else 0,
    }
```

---

## Write Tools

All write tools follow the `_apply_task_mutation` pattern. The tool receives arguments,
constructs a `mutator` function, and the helper handles cloning + re-indexing + atomic
swap.

### Task Init Data Format

Tools that create tasks accept dictionaries with these fields:

```python
# primary_task_data (root task):
{
    "name": str,               # short label
    "description": str,        # agent-readable prose
    "success_criteria": list[str],
    "confidence": float,
    "task_context": str,       # task-specific markdown (e.g., DigestedInformation)
}

# sub_task / SubTask (child task):
{
    "task_name": str,
    "task_description": str,
    "task_context": str,
    "success_criteria": list[str],
    "confidence": float,
}
```

Note: `task_id`, `parent_task_id`, `child_tasks` are assigned internally by the tool.

---

### `TaskInit`

Replaces the **entire** session task tree with a new root + optional immediate children.

```python
@tool
def TaskInit(
    primary_task_data: dict,
    sub_task: list[dict] | None = None,
) -> dict:
    """Initialize a new task tree, replacing any existing tasks.

    Args:
        primary_task_data: The root task definition. Contains:
            name, description, success_criteria, confidence, task_context.
            parent_task_id is automatically set to None (root).
        sub_task: Optional list of immediate child task definitions.
            Each dict contains: task_name, task_description, task_context,
            success_criteria, confidence.

    Returns:
        Summary dict: {"root_id": str, "child_ids": list[str], "total": int}
    """
    def mutator(_root: Task | None) -> Task:
        root = Task(
            task_id="uuid",     # placeholder, re-indexer will replace
            task_name=primary_task_data["name"],
            task_description=primary_task_data["description"],
            task_context=primary_task_data["task_context"],
            success_criteria=primary_task_data["success_criteria"],
            confidence=primary_task_data["confidence"],
            parent_task_id=None,
            child_tasks=[],
        )

        if sub_task:
            for st in sub_task:
                child = Task(
                    task_id="placeholder",
                    task_name=st["task_name"],
                    task_description=st["task_description"],
                    task_context=st["task_context"],
                    success_criteria=st["success_criteria"],
                    confidence=st["confidence"],
                    parent_task_id=root.task_id,
                    child_tasks=[],
                )
                root.child_tasks.append(child)

        return root

    new_root = _apply_task_mutation(session, mutator)
    return {
        "root_id": new_root.task_id,
        "child_ids": [c.task_id for c in (new_root.child_tasks or [])],
        "total": 1 + len(new_root.child_tasks or []),
    }
```

---

### `SetSubTask`

Replaces a parent's **entire** `child_tasks` list. If the parent already has children,
they are removed and replaced.

```python
@tool
def SetSubTask(
    parent_task_id: str,
    sub_task: list[dict],
) -> dict:
    """Replace a parent task's children with a new set of subtasks.

    Args:
        parent_task_id: The ID of the parent task.
        sub_task: List of child task definitions (task_name, task_description, etc.).

    Returns:
        Summary: {"parent_id": str, "child_ids": list[str], "count": int}
    """
    def mutator(root: Task) -> Task:
        parent = root.at_id(parent_task_id)
        if parent is None:
            raise ValueError(f"Task '{parent_task_id}' not found.")

        # Convert from container to leaf on empty
        if not sub_task:
            parent.child_tasks = None
            return root

        parent.child_tasks = []
        for st in sub_task:
            child = Task(
                task_id="placeholder",
                task_name=st["task_name"],
                task_description=st["task_description"],
                task_context=st["task_context"],
                success_criteria=st["success_criteria"],
                confidence=st["confidence"],
                parent_task_id=parent.task_id,
                child_tasks=[],
            )
            parent.child_tasks.append(child)

        return root

    new_root = _apply_task_mutation(session, mutator)
    parent = new_root.at_id(parent_task_id)
    return {
        "parent_id": parent.task_id,
        "child_ids": [c.task_id for c in (parent.child_tasks or [])],
        "count": len(parent.child_tasks or []),
    }
```

---

### `AddSubTask`

Appends new children to the parent's existing `child_tasks` list (preserves existing).

```python
@tool
def AddSubTask(
    parent_task_id: str,
    sub_task: list[dict],
) -> dict:
    """Append new subtasks to a parent's existing child list.

    Args:
        parent_task_id: The ID of the parent task.
        sub_task: List of child task definitions to append.

    Returns:
        Summary: {"parent_id": str, "new_child_ids": list[str], "total_children": int}
    """
    def mutator(root: Task) -> Task:
        parent = root.at_id(parent_task_id)
        if parent is None:
            raise ValueError(f"Task '{parent_task_id}' not found.")

        if parent.child_tasks is None:
            parent.child_tasks = []

        existing_count = len(parent.child_tasks)
        for st in sub_task:
            child = Task(
                task_id="placeholder",
                task_name=st["task_name"],
                task_description=st["task_description"],
                task_context=st["task_context"],
                success_criteria=st["success_criteria"],
                confidence=st["confidence"],
                parent_task_id=parent.task_id,
                child_tasks=[],
            )
            parent.child_tasks.append(child)

        return root

    new_root = _apply_task_mutation(session, mutator)
    parent = new_root.at_id(parent_task_id)
    children = parent.child_tasks or []
    new_ids = [c.task_id for c in children[existing_count:]]
    return {
        "parent_id": parent.task_id,
        "new_child_ids": new_ids,
        "total_children": len(children),
    }
```

---

### `DeleteSubTask`

Deletes one or more subtasks by ID. If a deleted task has children, they are also
removed.

```python
@tool
def DeleteSubTask(task_id: str | list[str]) -> dict:
    """Delete one or more subtasks from the task tree.

    Deleting a task also removes all its descendants.

    Args:
        task_id: A single task ID or list of task IDs to delete.
            Root task cannot be deleted.

    Returns:
        Summary: {"deleted_ids": list[str], "count": int}
    """
    ids = [task_id] if isinstance(task_id, str) else task_id
    deleted: list[str] = []

    def mutator(root: Task) -> Task:
        for tid in ids:
            if tid == root.task_id:
                raise ValueError("Cannot delete the root task.")
            _collect_deleted = []
            _remove_by_id(root, tid, _collect_deleted)
            deleted.extend(_collect_deleted)
        return root

    def _remove_by_id(parent: Task, target_id: str, collect: list[str]) -> bool:
        """Remove child with target_id from parent. Returns True if found."""
        if parent.child_tasks is None:
            return False
        for i, child in enumerate(parent.child_tasks):
            if child.task_id == target_id:
                _collect_ids(child, collect)
                parent.child_tasks.pop(i)
                if not parent.child_tasks:
                    parent.child_tasks = None  # leaf again
                return True
            if _remove_by_id(child, target_id, collect):
                return True
        return False

    def _collect_ids(task: Task, collect: list[str]) -> None:
        """Collect a task's ID and all descendant IDs."""
        collect.append(task.task_id)
        if task.child_tasks:
            for child in task.child_tasks:
                _collect_ids(child, collect)

    _apply_task_mutation(session, mutator)
    return {"deleted_ids": deleted, "count": len(deleted)}
```

---

### `EditSubTask`

Edits metadata and success criteria of an existing task. Structural fields
(`task_id`, `parent_task_id`, `child_tasks`, `task_result`) are not editable
through this tool — they are managed internally.

```python
@tool
def EditSubTask(task_id: str, task_data: dict) -> dict:
    """Edit a task's metadata and success criteria.

    Args:
        task_id: The ID of the task to edit.
        task_data: Dict with any of: task_name, task_description,
            task_context, success_criteria, confidence.
            Omitted fields are left unchanged.

    Returns:
        The updated task as a dict.
    """
    def mutator(root: Task) -> Task:
        target = root.at_id(task_id)
        if target is None:
            raise ValueError(f"Task '{task_id}' not found.")

        if "task_name" in task_data:
            target.task_name = task_data["task_name"]
        if "task_description" in task_data:
            target.task_description = task_data["task_description"]
        if "task_context" in task_data:
            target.task_context = task_data["task_context"]
        if "success_criteria" in task_data:
            target.success_criteria = task_data["success_criteria"]
        if "confidence" in task_data:
            target.confidence = task_data["confidence"]

        return root

    new_root = _apply_task_mutation(session, mutator)
    updated = new_root.at_id(task_id)
    return _task_to_dict(updated)
```

---

### `SwapTask`

Swaps the positions of two tasks in the tree. Can swap sibling tasks, cross-parent
tasks, or a child with an ancestor (reorganizing the tree). Re-indexing after swap
ensures IDs are consistent.

```python
@tool
def SwapTask(task_id_1: str, task_id_2: str) -> dict:
    """Swap the positions of two tasks in the tree.

    This can reorganize the tree structure — tasks can swap with siblings,
    tasks under different parents, or ancestors. The root task cannot
    be swapped.

    Re-indexing after swap guarantees all IDs remain consistent.

    Args:
        task_id_1: First task ID.
        task_id_2: Second task ID.

    Returns:
        Summary: {"swapped": [str, str], "new_id_1": str, "new_id_2": str}
    """

    # Capture references for post-reindex ID reading
    captured_task_1: Task | None = None
    captured_task_2: Task | None = None

    def mutator(root: Task) -> Task:
        nonlocal captured_task_1, captured_task_2
        if task_id_1 == root.task_id or task_id_2 == root.task_id:
            raise ValueError("Cannot swap the root task.")

        # Find both tasks and their parents
        parent_1, task_1 = _find_parent_and_child(root, task_id_1)
        parent_2, task_2 = _find_parent_and_child(root, task_id_2)

        if parent_1 is None or task_1 is None:
            raise ValueError(f"Task '{task_id_1}' not found.")
        if parent_2 is None or task_2 is None:
            raise ValueError(f"Task '{task_id_2}' not found.")

        # Prevent circular: task_1 cannot be an ancestor of task_2 (or vice versa)
        if _is_ancestor(task_1, task_id_2) or _is_ancestor(task_2, task_id_1):
            raise ValueError(
                "Cannot swap a task with its own ancestor — "
                "would create a circular reference."
            )

        # Find indices in parent child_tasks lists
        idx_1 = parent_1.child_tasks.index(task_1)
        idx_2 = parent_2.child_tasks.index(task_2)

        # Swap in parent lists
        parent_1.child_tasks[idx_1] = task_2
        parent_2.child_tasks[idx_2] = task_1

        # Update parent references
        task_1.parent_task_id = parent_2.task_id
        task_2.parent_task_id = parent_1.task_id

        # Capture for post-reindex ID reading
        captured_task_1 = task_1
        captured_task_2 = task_2

        return root

    def _find_parent_and_child(
        parent: Task, target_id: str
    ) -> tuple[Task | None, Task | None]:
        """Find a task and its parent in the tree."""
        if parent.child_tasks is None:
            return (None, None)
        for child in parent.child_tasks:
            if child.task_id == target_id:
                return (parent, child)
            p, c = _find_parent_and_child(child, target_id)
            if p is not None:
                return (p, c)
        return (None, None)

    def _is_ancestor(ancestor: Task, target_id: str) -> bool:
        """Check if a task is an ancestor of target_id."""
        if ancestor.child_tasks is None:
            return False
        for child in ancestor.child_tasks:
            if child.task_id == target_id:
                return True
            if _is_ancestor(child, target_id):
                return True
        return False

    new_root = _apply_task_mutation(session, mutator)

    # After re-indexing, task objects still exist — read their new IDs
    # via the captured references (task_1 and task_2 were mutated in-place)
    return {
        "swapped": [task_id_1, task_id_2],
        "new_id_1": task_1.task_id,
        "new_id_2": task_2.task_id,
    }
```

---

## Read-Only Task Tools Constant

```python
# In constants/tools.py:
READ_ONLY_TASK_TOOLS: list[Tool] = [
    ReadActiveTask,
    ReadTask,
    ListTask,
]
```

These are injected into agents that need task inspection (e.g., QueryAnalyst when
an active task exists).

## Write Task Tools Constant

```python
WRITE_TASK_TOOLS: list[Tool] = [
    TaskInit,
    SetSubTask,
    AddSubTask,
    DeleteSubTask,
    EditSubTask,
    SwapTask,
]
```

Injected into agents that create and manage tasks (e.g., TaskCreator, TaskExecutor).

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


---


---


---

## See also

Prev : [InformationDigester Tools](digester.md) | Next : [`BaseCompaction` Strategy](../utility/compaction.md)


## Related

- [Task tree + TaskResult](../state/task.md)
- [Shared Task on Session.task](../state/session.md)
- [READ_ONLY_TASK_TOOLS + WRITE_TASK_TOOLS](../constants/tools.md)
- [Used by TaskCreator, TaskExecutor, QueryAnalyst](../agents/task_creator.md)
