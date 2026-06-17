"""Readable task-tree rendering helpers."""

from __future__ import annotations

from tinycua.models.task import TaskStateStore


def render_task_tree(
    store: TaskStateStore,
    *,
    max_depth: int = 8,
    max_nodes: int = 100,
) -> str:
    """Render a task tree as bounded user-readable text."""
    if store.root_task_id is None or store.root_task_id not in store.tasks:
        return "No tasks."

    lines: list[str] = []
    visited = 0

    def visit(task_id: str, prefix: str, depth: int) -> None:
        nonlocal visited
        if visited >= max_nodes:
            if not lines or lines[-1] != "... [task tree truncated]":
                lines.append("... [task tree truncated]")
            return
        task = store.tasks[task_id]
        connector = "" if depth == 0 else "|- "
        lines.append(f"{prefix}{connector}Task [{task.status.value}] {task.title}")
        visited += 1
        if depth >= max_depth:
            if task.children:
                lines.append(f"{prefix}|  ... [max depth reached]")
            return
        child_prefix = "" if depth == 0 else f"{prefix}|  "
        for child_id in task.children:
            if child_id in store.tasks:
                visit(child_id, child_prefix, depth + 1)

    visit(store.root_task_id, "", 0)
    return "\n".join(lines)
