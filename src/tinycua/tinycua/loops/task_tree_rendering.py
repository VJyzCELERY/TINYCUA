"""Readable task-tree rendering helpers."""

from __future__ import annotations

from tinycua.models.task import TaskStateStore


def render_task_tree(
    store: TaskStateStore,
    *,
    max_nodes: int = 100,
) -> str:
    """Render a task tree as a numbered post-order list (user-readable).

    Printed in execution order: line 1 of the list is the first task worked on
    (the DFS left-most leaf). The root is shown as a goal header (no status
    marker — it is the objective, not a work item), then the numbered post-order
    list (root excluded). Numbering matches ``TaskStateStore.task_number_map``
    so users and the agent share one numbering. Uses ``Task [status] title`` to
    stay distinct from the LLM-facing renderer.
    """
    if store.root_task_id is None or store.root_task_id not in store.tasks:
        return "No tasks."

    root = store.tasks[store.root_task_id]
    lines: list[str] = [f"Root (goal): {root.title}"]
    lines.append("Task list (in execution order, numbered):")
    lines.append("")
    visited = 0
    counter = 0

    def visit(task_id: str) -> None:
        nonlocal visited, counter
        if visited >= max_nodes:
            if not lines or lines[-1] != "... [task tree truncated]":
                lines.append("... [task tree truncated]")
            return
        task = store.tasks[task_id]
        # Post-order: children first (left-most leaf becomes list row 1).
        for child_id in task.children:
            if child_id in store.tasks:
                visit(child_id)
        if task_id == store.root_task_id:
            return  # root is the goal header, not a numbered work item
        visited += 1
        counter += 1
        lines.append(f"{counter}. Task [{task.status.value}] {task.title}")

    visit(store.root_task_id)
    return "\n".join(lines)
