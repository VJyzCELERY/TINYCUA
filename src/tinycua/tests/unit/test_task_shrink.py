"""Unit tests for TaskStateStore.delete_task and merge_tasks (Milestone 4)."""

from __future__ import annotations

import pytest

from tinycua.models.task import TaskResult, TaskStateStore, TaskStatus


class TestDeleteTask:
    """delete_task removes a task and its pending subtree."""

    def test_delete_pending_task_removes_subtree(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        grandchild = store.create_task("GC", parent_id=child.task_id)
        store.delete_task(child.task_id)
        assert child.task_id not in store.tasks
        assert grandchild.task_id not in store.tasks
        assert child.task_id not in store.tasks[root.task_id].children

    def test_delete_completed_task_raises(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.transition(child.task_id, TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="immutable"):
            store.delete_task(child.task_id)

    def test_delete_root_raises(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        with pytest.raises(ValueError, match="root"):
            store.delete_task(root.task_id)

    def test_delete_active_task_raises(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.active_task_id = child.task_id
        with pytest.raises(ValueError, match="active"):
            store.delete_task(child.task_id)

    def test_delete_not_found_raises(self):
        store = TaskStateStore()
        with pytest.raises(ValueError, match="not found"):
            store.delete_task("nonexistent")

    def test_delete_preserves_completed_children(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        completed_gc = store.create_task("DoneGC", parent_id=child.task_id)
        store.transition(completed_gc.task_id, TaskStatus.IN_PROGRESS)
        store.transition(completed_gc.task_id, TaskStatus.COMPLETED)
        pending_gc = store.create_task("PendingGC", parent_id=child.task_id)
        store.delete_task(child.task_id)
        # Completed grandchild is re-parented to root.
        assert completed_gc.task_id in store.tasks
        assert store.tasks[completed_gc.task_id].parent_id == root.task_id
        assert completed_gc.task_id in store.tasks[root.task_id].children
        # Pending grandchild is removed.
        assert pending_gc.task_id not in store.tasks

    def test_delete_bumps_version(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        store.create_task("C1", parent_id=root.task_id)
        child2 = store.create_task("C2", parent_id=root.task_id)
        v = store.version
        # child1 is active — delete child2 (not active).
        store.delete_task(child2.task_id)
        assert store.version > v


class TestMergeTasks:
    """merge_tasks collapses a child into its parent, preserving work."""

    def test_merge_preserves_child_result_on_parent(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="child work"))
        store.merge_tasks(child.task_id, root.task_id)
        assert child.task_id not in store.tasks
        assert root.result is not None
        assert root.result.content == "child work"

    def test_merge_both_have_results_concatenates(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        store.record_result(root.task_id, TaskResult(content="root work"))
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="child work"))
        store.merge_tasks(child.task_id, root.task_id)
        assert "root work" in root.result.summary
        assert "child work" in root.result.summary

    def test_merge_child_no_result(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        # Child has no result, parent has no result.
        store.merge_tasks(child.task_id, root.task_id)
        assert child.task_id not in store.tasks
        assert root.result is None

    def test_merge_self_raises(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        with pytest.raises(ValueError, match="itself"):
            store.merge_tasks(root.task_id, root.task_id)

    def test_merge_completed_raises(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.transition(child.task_id, TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="immutable"):
            store.merge_tasks(child.task_id, root.task_id)

    def test_merge_removes_child_from_parent_children(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child1 = store.create_task("C1", parent_id=root.task_id)
        child2 = store.create_task("C2", parent_id=root.task_id)
        store.merge_tasks(child1.task_id, root.task_id)
        assert child1.task_id not in store.tasks[root.task_id].children
        assert child2.task_id in store.tasks[root.task_id].children

    def test_merge_bumps_version(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        store.create_task("C1", parent_id=root.task_id)
        child2 = store.create_task("C2", parent_id=root.task_id)
        v = store.version
        # child1 is active — merge child2 (not active).
        store.merge_tasks(child2.task_id, root.task_id)
        assert store.version > v


class TestEffortProfiledThreshold:
    """Shrink thresholds are effort-profiled."""

    def test_low_effort_higher_threshold(self):
        from tinycua.loops.task_nodes import shrink_threshold_for_effort

        low = shrink_threshold_for_effort("low")
        high = shrink_threshold_for_effort("high")
        assert high < low

    def test_medium_effort_between(self):
        from tinycua.loops.task_nodes import shrink_threshold_for_effort

        low = shrink_threshold_for_effort("low")
        medium = shrink_threshold_for_effort("medium")
        high = shrink_threshold_for_effort("high")
        assert high <= medium <= low
