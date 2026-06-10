"""Unit tests for TinyCUALoop active task lifecycle helpers."""

import pytest
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import Task, TaskResult


def _make_linear_tree() -> Task:
    """Create a linear task tree: root -> [T-1 (done), T-2 (pending), T-3 (pending)]."""
    t1 = Task(task_id="T-1", title="Task 1", status="done")
    t2 = Task(task_id="T-2", title="Task 2", status="pending")
    t3 = Task(task_id="T-3", title="Task 3", status="pending")
    return Task(task_id="ROOT", title="Root", children=[t1, t2, t3])


def _make_nested_tree() -> Task:
    """Create a nested task tree with children-of-children."""
    t1 = Task(task_id="T-1", title="Task 1", status="done")
    t2_1 = Task(task_id="T-2.1", title="Task 2.1", status="pending")
    t2_2 = Task(task_id="T-2.2", title="Task 2.2", status="pending")
    t2 = Task(task_id="T-2", title="Task 2", status="pending", children=[t2_1, t2_2])
    t3 = Task(task_id="T-3", title="Task 3", status="pending")
    return Task(task_id="ROOT", title="Root", children=[t1, t2, t3])


def test_get_active_task_returns_first_unfinished():
    """get_active_task returns the first unfinished task in DFS pre-order."""
    loop = TinyCUALoop()
    loop.root_task = _make_linear_tree()
    active = loop.get_active_task()
    assert active is not None
    assert active.task_id == "T-2"


def test_get_active_task_nested_tree():
    """get_active_task descends into nested children via DFS."""
    loop = TinyCUALoop()
    loop.root_task = _make_nested_tree()
    active = loop.get_active_task()
    assert active is not None
    assert active.task_id == "T-2.1"


def test_get_active_task_all_done_returns_root():
    """get_active_task returns root if all children are done but root not marked done."""
    loop = TinyCUALoop()
    root = Task(
        task_id="ROOT",
        title="Root",
        status="pending",
        children=[
            Task(task_id="T-1", title="Task 1", status="done"),
            Task(task_id="T-2", title="Task 2", status="done"),
        ],
    )
    loop.root_task = root
    active = loop.get_active_task()
    assert active is not None
    assert active.task_id == "ROOT"


def test_get_active_task_all_complete_returns_none():
    """get_active_task returns None when all tasks are complete."""
    loop = TinyCUALoop()
    root = Task(
        task_id="ROOT",
        title="Root",
        status="done",
        children=[
            Task(task_id="T-1", title="Task 1", status="done"),
            Task(task_id="T-2", title="Task 2", status="done"),
        ],
    )
    loop.root_task = root
    active = loop.get_active_task()
    assert active is None


def test_get_active_task_none_tree():
    """get_active_task returns None when root_task is None."""
    loop = TinyCUALoop()
    loop.root_task = None
    active = loop.get_active_task()
    assert active is None


def test_get_active_task_with_traversal_hint():
    """get_active_task uses active_child_id to resume from hinted child."""
    loop = TinyCUALoop()
    tree = _make_nested_tree()
    # Set hint to skip T-2.1 and start at T-2.2
    tree.children[1].active_child_id = "T-2.2"
    loop.root_task = tree
    active = loop.get_active_task()
    assert active is not None
    assert active.task_id == "T-2.2"


def test_get_active_task_updates_hint_during_traversal():
    """FR-010: active_child_id is lazily updated as DFS descends (no initial hint)."""
    loop = TinyCUALoop()
    tree = _make_nested_tree()
    loop.root_task = tree
    # Before traversal, root has no hint
    assert tree.active_child_id is None
    # Get active task triggers DFS traversal
    active = loop.get_active_task()
    assert active is not None
    # After traversal, root's active_child_id should be set to the selected child
    assert tree.active_child_id is not None, "active_child_id should be written back during traversal"
    # Verify the hint points to the correct child
    assert tree.active_child_id == active.task_id or tree.active_child_id in [c.task_id for c in tree.children]


def test_get_active_task_hint_nonexistent_fallback():
    """get_active_task falls back to standard DFS when active_child_id is invalid."""
    loop = TinyCUALoop()
    tree = _make_nested_tree()
    tree.children[1].active_child_id = "NONEXISTENT"
    loop.root_task = tree
    active = loop.get_active_task()
    assert active is not None
    # Should still find T-2.1 via standard DFS
    assert active.task_id == "T-2.1"


def test_set_active_task_valid():
    """set_active_task sets the active task by ID."""
    loop = TinyCUALoop()
    loop.root_task = _make_linear_tree()
    loop.set_active_task("T-3")
    active = loop.get_active_task()
    assert active is not None
    assert active.task_id == "T-3"


def test_set_active_task_unknown_id_raises():
    """set_active_task raises ValueError for unknown task_id."""
    loop = TinyCUALoop()
    loop.root_task = _make_linear_tree()
    with pytest.raises(ValueError, match="Task not found"):
        loop.set_active_task("NONEXISTENT")


def test_update_active_task_result():
    """update_active_task_result updates the active task's result field."""
    loop = TinyCUALoop()
    loop.root_task = _make_linear_tree()
    result = TaskResult(task_id="T-2", execution_status="succeeded", summary="Done")
    loop.update_active_task_result(result)
    active = loop.get_active_task()
    assert active is not None
    assert active.result is not None
    assert active.result.execution_status == "succeeded"


def test_update_active_task_result_no_active_raises():
    """update_active_task_result raises ValueError when no active task."""
    loop = TinyCUALoop()
    loop.root_task = None
    result = TaskResult(task_id="T-2", execution_status="succeeded")
    with pytest.raises(ValueError, match="No active task"):
        loop.update_active_task_result(result)


def test_update_active_task_result_mismatched_task_id():
    """update_active_task_result raises ValueError when result.task_id doesn't match active task."""
    loop = TinyCUALoop()
    loop.root_task = _make_linear_tree()
    loop.set_active_task("T-2")
    result = TaskResult(task_id="T-999", execution_status="succeeded")
    with pytest.raises(ValueError, match="does not match"):
        loop.update_active_task_result(result)


def test_on_reviewer_accept_marks_done():
    """_on_reviewer_accept marks the active task as done and returns False (not root done)."""
    loop = TinyCUALoop()
    loop.root_task = _make_linear_tree()
    active = loop.get_active_task()
    assert active is not None
    assert active.task_id == "T-2"
    # Set up result (as would happen in real flow)
    active.result = TaskResult(task_id="T-2", execution_status="succeeded")
    result = loop._on_reviewer_accept(active)
    assert result is False  # root not done yet
    assert active.status == "done"


def test_on_reviewer_accept_root_done():
    """_on_reviewer_accept returns True when last leaf is accepted and root becomes done."""
    loop = TinyCUALoop()
    root = Task(
        task_id="ROOT",
        title="Root",
        status="pending",
        children=[
            Task(task_id="T-1", title="Task 1", status="pending"),
        ],
    )
    loop.root_task = root
    active = loop.get_active_task()
    assert active is not None
    assert active.task_id == "T-1"  # T-1 is pending → active ✓
    # Simulate execution + result
    active.result = TaskResult(task_id="T-1", execution_status="succeeded")
    active.status = "done"  # execution marks done
    result = loop._on_reviewer_accept(active)
    assert result is True  # T-1 was the last remaining child → root is done


def test_on_reviewer_accept_parent_walk():
    """_on_reviewer_accept walks up parent chain when last child is accepted."""
    loop = TinyCUALoop()
    t1_1 = Task(task_id="T-1.1", title="Child 1.1", status="done")
    t1_2 = Task(task_id="T-1.2", title="Child 1.2", status="pending")
    t1 = Task(task_id="T-1", title="Parent 1", status="pending", children=[t1_1, t1_2])
    root = Task(task_id="ROOT", title="Root", status="pending", children=[t1])
    loop.root_task = root

    active = loop.get_active_task()
    assert active is not None and active.task_id == "T-1.2"
    # Set up result (as would happen in real flow)
    active.result = TaskResult(task_id="T-1.2", execution_status="succeeded")
    result = loop._on_reviewer_accept(active)
    # T-1.2 is done, T-1 has no more unfinished children → T-1 marked done too
    assert t1.status == "done", "Parent should be marked done when all children complete"
    # Root still has no other children, so root is done
    assert result is True


def test_on_reviewer_accept_parent_walk_partial():
    """_on_reviewer_accept walks up but stops when parent still has unfinished siblings."""
    loop = TinyCUALoop()
    t1_1 = Task(task_id="T-1.1", title="Child 1.1", status="done")
    t1_2 = Task(task_id="T-1.2", title="Child 1.2", status="pending")
    t2 = Task(task_id="T-2", title="Sibling", status="pending")
    t1 = Task(task_id="T-1", title="Parent 1", status="pending", children=[t1_1, t1_2])
    root = Task(task_id="ROOT", title="Root", status="pending", children=[t1, t2])
    loop.root_task = root

    active = loop.get_active_task()
    assert active is not None and active.task_id == "T-1.2"
    # Set up result (as would happen in real flow)
    active.result = TaskResult(task_id="T-1.2", execution_status="succeeded")
    result = loop._on_reviewer_accept(active)
    # T-1.2 done, T-1 fully done → T-1 marked done
    assert t1.status == "done"
    # Root has T-2 still pending → root NOT done
    assert result is False, "Root should not be done — T-2 is still pending"
    # Next DFS should find T-2
    next_active = loop.get_active_task()
    assert next_active is not None and next_active.task_id == "T-2"


def test_on_reviewer_retry_preserves_active():
    """_on_reviewer_retry keeps the same active task."""
    loop = TinyCUALoop()
    loop.root_task = _make_linear_tree()
    active = loop.get_active_task()
    assert active is not None
    loop._on_reviewer_retry(active)
    # Same task should still be active
    next_active = loop.get_active_task()
    assert next_active is not None
    assert next_active.task_id == active.task_id


def test_on_reviewer_replan_preserves_active():
    """_on_reviewer_replan keeps the same active task."""
    loop = TinyCUALoop()
    loop.root_task = _make_linear_tree()
    active = loop.get_active_task()
    assert active is not None
    loop._on_reviewer_replan(active)
    next_active = loop.get_active_task()
    assert next_active is not None
    assert next_active.task_id == active.task_id


def test_on_reviewer_open_question_preserves_active():
    """_on_reviewer_open_question keeps the same active task."""
    loop = TinyCUALoop()
    loop.root_task = _make_linear_tree()
    active = loop.get_active_task()
    assert active is not None
    loop._on_reviewer_open_question(active)
    next_active = loop.get_active_task()
    assert next_active is not None
    assert next_active.task_id == active.task_id


def test_task_children_is_append_only():
    """FR-017: Task.children is append-only — no external mutation helpers exist."""
    parent = Task(task_id="T-1", title="Parent")
    child = Task(task_id="T-1.1", title="Child")
    parent.children.append(child)
    assert len(parent.children) == 1
    # Verify Task dataclass does not expose add_child/remove_child methods
    assert not hasattr(Task, "add_child"), "Task should not expose add_child helper"
    assert not hasattr(Task, "remove_child"), "Task should not expose remove_child helper"
    # Verify children list is mutable (append works) but Task doesn't encourage direct mutation
    assert hasattr(parent.children, "append"), "children list must support append"


# IMPORTANT: Update this snapshot when upgrading tinycua_sdk.
# To refresh: run `python -c "import tinycua_sdk; print({n for n in dir(tinycua_sdk) if not n.startswith('_')})"`
SDK_PUBLIC_API_SNAPSHOT = {
    "Agent", "AgentConfig", "AgentExecutor", "AgentPolicy", "BaseLoop",
    "ContentPart", "FileAttachment", "LLMClient", "LanguageModel",
    "Skill", "SkillRegistry", "StreamingFileAttachment", "Tool",
    "agent", "core", "models", "providers", "security", "skills", "tool", "tools",
}


def test_sdk_public_api_unchanged():
    """FR-018: System MUST NOT modify tinycua-sdk public APIs."""
    import tinycua_sdk
    current_api = {name for name in dir(tinycua_sdk) if not name.startswith("_")}
    added = current_api - SDK_PUBLIC_API_SNAPSHOT
    removed = SDK_PUBLIC_API_SNAPSHOT - current_api
    assert not added, f"New public API items added to SDK: {added}"
    assert not removed, f"Public API items removed from SDK: {removed}"


def test_is_root_task_done_all_complete():
    """_is_root_task_done returns True when root and all children are done."""
    loop = TinyCUALoop()
    root = Task(task_id="ROOT", title="Root", status="done",
                children=[Task(task_id="T-1", title="Task 1", status="done")])
    loop.root_task = root
    assert loop._is_root_task_done() is True


def test_is_root_task_done_children_pending():
    """_is_root_task_done returns False when children are still pending."""
    loop = TinyCUALoop()
    root = Task(task_id="ROOT", title="Root", status="pending",
                children=[Task(task_id="T-1", title="Task 1", status="pending")])
    loop.root_task = root
    assert loop._is_root_task_done() is False


def test_is_root_task_done_no_children():
    """_is_root_task_done returns True when root has no children and is done."""
    loop = TinyCUALoop()
    root = Task(task_id="ROOT", title="Root", status="done")
    loop.root_task = root
    assert loop._is_root_task_done() is True
