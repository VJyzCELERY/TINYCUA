"""Regression: task selection by number (post-order index) or UUID.

The roadmap is rendered as a numbered post-order list (root excluded), and
``TaskStateStore.resolve_task_id`` maps either a UUID or a 1-based number to a
task_id so the agent can refer to tasks by short numbers instead of
hallucination-prone UUIDs. The numbering must match the rendered order exactly.
"""

from __future__ import annotations

from tinycua.models.task import TaskStateStore, TaskStatus
from tinycua.loops.task_nodes import _render_task_tree_markdown
from tinycua.tools.task_tools import (
    TaskDecomposeTool,
    TaskInspectTool,
    TaskUpdateTool,
)


def _store() -> TaskStateStore:
    store = TaskStateStore()
    root = store.create_task("Root clock app")
    html = store.create_task("HTML structure", parent_id=root.task_id)
    store.create_task("HTML skeleton", parent_id=html.task_id)
    store.create_task("Clock container", parent_id=html.task_id)
    store.create_task("CSS face", parent_id=root.task_id)
    return store


def test_task_number_map_is_post_order_root_excluded() -> None:
    """Numbering is post-order: left-most leaf is 1; root is absent."""
    store = _store()
    mapping = store.task_number_map()

    # 4 non-root tasks, numbered 1..4.
    assert sorted(mapping) == [1, 2, 3, 4]
    titles = {store.tasks[tid].title for tid in mapping.values()}
    assert "Root clock app" not in titles  # root excluded
    # Post-order: HTML skeleton (left-most leaf) is number 1.
    assert store.tasks[mapping[1]].title == "HTML skeleton"
    # CSS face (right-most subtree leaf) is the highest number among leaves.
    assert store.tasks[mapping[4]].title == "CSS face"


def test_resolve_task_id_accepts_number_or_uuid() -> None:
    """resolve_task_id maps a number string to a UUID and passes UUIDs through."""
    store = _store()
    skeleton_id = store.task_number_map()[1]

    assert store.resolve_task_id("1") == skeleton_id
    assert store.resolve_task_id(skeleton_id) == skeleton_id
    # Empty/None falls back to the active task.
    assert store.resolve_task_id(None) == store.active_task_id
    assert store.resolve_task_id("") == store.active_task_id
    # Unresolvable references return None.
    assert store.resolve_task_id("999") is None
    assert store.resolve_task_id("not-a-uuid-or-number") is None


def test_render_numbering_matches_resolve_map() -> None:
    """The rendered list numbers must match task_number_map exactly."""
    store = _store()
    mapping = store.task_number_map()
    rendered = _render_task_tree_markdown(store.snapshot())

    for number, task_id in mapping.items():
        title = store.tasks[task_id].title
        assert f"{number}. [pending] {title} (id={task_id})" in rendered


def test_task_inspect_accepts_number() -> None:
    """task_inspect resolves a numeric task_id to the right task."""
    store = _store()
    tool = TaskInspectTool()
    tool.bind_task_store(store)
    skeleton_id = store.task_number_map()[1]

    result = tool(task_id="1")
    assert result.get("task_id") == skeleton_id
    assert result.get("title") == "HTML skeleton"


def test_task_update_accepts_number() -> None:
    """task_update resolves a numeric task_id to the right task."""
    store = _store()
    tool = TaskUpdateTool()
    tool.bind_task_store(store)
    container_id = store.task_number_map()[2]

    result = tool(task_id="2", description="updated via number")
    assert result.get("success") is True
    assert store.tasks[container_id].description == "updated via number"


def test_task_decompose_accepts_number() -> None:
    """task_decompose resolves a numeric task_id to the right task."""
    store = _store()
    tool = TaskDecomposeTool()
    tool.bind_task_store(store)
    html_id = store.task_number_map()[3]  # HTML structure (parent of leaves)

    result = tool(task_id="3", subtasks=["New sub"])
    # ponytail: decompose_task is idempotent — HTML structure already has
    # children, so it returns the existing children instead of appending.
    assert result.get("success") is True
    assert result.get("task_id") == html_id


if __name__ == "__main__":
    # ponytail: self-check.
    test_task_number_map_is_post_order_root_excluded()
    test_resolve_task_id_accepts_number_or_uuid()
    test_render_numbering_matches_resolve_map()
    test_task_inspect_accepts_number()
    test_task_update_accepts_number()
    test_task_decompose_accepts_number()
    print("ok")