"""Unit tests for TaskStateStore.delete_task and merge_tasks (Milestone 4)."""

from __future__ import annotations

import pytest

from tinycua.models.task import TaskResult, TaskStateStore, TaskStatus


class TestDeleteTask:
    """delete_task removes only untouched unfinished leaves."""

    def test_delete_pending_leaf_removes_it(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.delete_task(child.task_id, rationale="planning duplicate")
        assert child.task_id not in store.tasks
        assert child.task_id not in store.tasks[root.task_id].children

    def test_delete_completed_task_raises(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.transition(child.task_id, TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="immutable"):
            store.delete_task(child.task_id, rationale="no longer needed")

    def test_delete_rejects_child_of_completed_parent_without_mutating_tree(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(root.task_id, TaskStatus.IN_PROGRESS)
        store.transition(root.task_id, TaskStatus.COMPLETED)
        before = store.snapshot()

        with pytest.raises(ValueError, match="immutable"):
            store.delete_task(child.task_id, rationale="no longer needed")

        assert store.snapshot() == before

    def test_delete_root_raises(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        with pytest.raises(ValueError, match="root"):
            store.delete_task(root.task_id, rationale="no longer needed")

    def test_delete_active_leaf_advances_to_next_task(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        next_child = store.create_task("Next", parent_id=root.task_id)
        store.delete_task(child.task_id, rationale="duplicate planning leaf")
        assert child.task_id not in store.tasks
        assert store.active_task_id == next_child.task_id

    def test_delete_not_found_raises(self):
        store = TaskStateStore()
        with pytest.raises(ValueError, match="not found"):
            store.delete_task("nonexistent", rationale="no longer needed")

    def test_delete_rejects_task_with_descendants(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.create_task("GC", parent_id=child.task_id)
        with pytest.raises(ValueError, match="descendants"):
            store.delete_task(child.task_id, rationale="no longer needed")

    def test_delete_bumps_version(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        store.create_task("C1", parent_id=root.task_id)
        child2 = store.create_task("C2", parent_id=root.task_id)
        v = store.version
        # child1 is active — delete child2 (not active).
        store.delete_task(child2.task_id, rationale="planning duplicate")
        assert store.version > v


class TestSupersedeTask:
    """supersede_task retains lineage without changing terminal history."""

    def test_supersede_rejects_child_of_completed_parent_without_mutating_tree(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(root.task_id, TaskStatus.IN_PROGRESS)
        store.transition(root.task_id, TaskStatus.COMPLETED)
        before = store.snapshot()

        with pytest.raises(ValueError, match="immutable"):
            store.supersede_task(child.task_id, "Replacement", "new plan")

        assert store.snapshot() == before


class TestMergeTasks:
    """merge_tasks collapses a child into its parent, preserving work."""

    def test_merge_preserves_child_result_on_parent(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="child work"))
        store.merge_tasks(child.task_id, root.task_id, rationale="combine work")
        assert child.task_id not in store.tasks
        assert root.result is not None
        assert root.result.content == "child work"

    def test_merge_both_have_results_concatenates(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        store.record_result(root.task_id, TaskResult(content="root work"))
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="child work"))
        store.merge_tasks(child.task_id, root.task_id, rationale="combine work")
        assert "root work" in root.result.summary
        assert "child work" in root.result.summary

    def test_merge_child_no_result(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        # Child has no result, parent has no result.
        store.merge_tasks(child.task_id, root.task_id, rationale="combine work")
        assert child.task_id not in store.tasks
        assert root.result is None

    def test_merge_self_raises(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        with pytest.raises(ValueError, match="itself"):
            store.merge_tasks(root.task_id, root.task_id, rationale="combine work")

    def test_merge_completed_raises(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.transition(child.task_id, TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="immutable"):
            store.merge_tasks(child.task_id, root.task_id, rationale="combine work")

    def test_merge_removes_child_from_parent_children(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child1 = store.create_task("C1", parent_id=root.task_id)
        child2 = store.create_task("C2", parent_id=root.task_id)
        store.merge_tasks(child1.task_id, root.task_id, rationale="combine work")
        assert child1.task_id not in store.tasks[root.task_id].children
        assert child2.task_id in store.tasks[root.task_id].children

    def test_merge_bumps_version(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        store.create_task("C1", parent_id=root.task_id)
        child2 = store.create_task("C2", parent_id=root.task_id)
        v = store.version
        # child1 is active — merge child2 (not active).
        store.merge_tasks(child2.task_id, root.task_id, rationale="combine work")
        assert store.version > v

    def test_merge_rejects_non_parent_without_mutating_tree(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        parent = store.create_task("Parent", parent_id=root.task_id)
        child = store.create_task("Child", parent_id=parent.task_id)
        before = store.snapshot()

        with pytest.raises(ValueError, match="direct parent"):
            store.merge_tasks(child.task_id, root.task_id, rationale="combine work")

        assert store.snapshot() == before


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
