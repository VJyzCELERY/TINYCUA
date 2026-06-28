"""Unit tests for reverse-order aggregation and child verification gate (Milestone 6, Streams B+C)."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.loops.task_nodes import TinyCUAResultAggregationNode, TinyCUATaskExecutorNode
from tinycua.models.session import Session
from tinycua.models.task import TaskResult, TaskStateStore, TaskStatus


class TestReverseOrderAggregation:
    """Aggregation lists tasks in reverse execution order (last-completed first)."""

    def test_aggregation_reverse_order(self):
        """Aggregation continuation lists last-executed leaf first, root last."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child1 = store.create_task("Child1", parent_id=root.task_id)
        child2 = store.create_task("Child2", parent_id=root.task_id)
        grandchild1 = store.create_task("GC1", parent_id=child1.task_id)

        # Complete all in execution order: GC1, Child1, Child2, Root
        for tid in [grandchild1.task_id, child1.task_id, child2.task_id, root.task_id]:
            store.record_result(tid, TaskResult(content=f"result-{tid[:4]}", success=True))
            store.record_reviewer_decision(tid, "approved")

        session = Session()
        session.task_store = store
        node = TinyCUAResultAggregationNode(
            node_id="result_aggregation",
            config=create_node_config("result_aggregation"),
        )
        node.session = session
        continuation = node.build_continuation(session)

        # In reverse execution order: GC1 was last executed leaf before Child1,
        # but post-order is GC1, Child1, Child2, Root. Reversed: Root, Child2,
        # Child1, GC1. Wait — _ordered_ids is post-order (children before parent,
        # root excluded). So ordered = [GC1, Child1, Child2]. Reversed = [Child2,
        # Child1, GC1]. Then root appended last: [Child2, Child1, GC1, Root].
        # The most-recently-completed task (Root) is last, the first-executed
        # leaf (GC1) is near the end, and the last-executed leaf (Child2) is first.
        lines = continuation.split("\n")
        # Find the positions of each task title in the evidence block.
        pos_child2 = next(i for i, ln in enumerate(lines) if "Child2" in ln)
        pos_child1 = next(i for i, ln in enumerate(lines) if "Child1" in ln)
        pos_gc1 = next(i for i, ln in enumerate(lines) if "GC1" in ln)
        pos_root = next(i for i, ln in enumerate(lines) if "Root" in ln)
        # Reverse execution order: Child2 first, then Child1, then GC1, then Root
        assert pos_child2 < pos_child1
        assert pos_child1 < pos_gc1
        assert pos_gc1 < pos_root


class TestChildVerificationGate:
    """Executor and reviewer continuations surface direct children for parent tasks."""

    def test_executor_continuation_includes_child_gate(self):
        """Active parent task → executor continuation includes 'Child Task Verification Gate'."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child1 = store.create_task("Sub1", parent_id=root.task_id)
        child2 = store.create_task("Sub2", parent_id=root.task_id)
        # Complete children so root becomes active for verification
        for tid in [child1.task_id, child2.task_id]:
            store.record_result(tid, TaskResult(content="done", success=True))
            store.record_reviewer_decision(tid, "approved")
        # Root should now be the active task (all children completed)
        session = Session()
        session.task_store = store
        node = TinyCUATaskExecutorNode(
            node_id="task_executor",
            config=create_node_config("task_executor"),
        )
        node.session = session
        continuation = node.build_continuation(session)

        assert "Child Task Verification Gate" in continuation
        assert "Sub1" in continuation
        assert "Sub2" in continuation
        assert "must remain completed" in continuation

    def test_leaf_task_no_child_gate(self):
        """Active leaf task (no children) → no child verification gate."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Leaf", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        session = Session()
        session.task_store = store
        node = TinyCUATaskExecutorNode(
            node_id="task_executor",
            config=create_node_config("task_executor"),
        )
        node.session = session
        continuation = node.build_continuation(session)

        assert "Child Task Verification Gate" not in continuation

    def test_child_gate_only_direct_children(self):
        """Parent with grandchildren → gate shows only direct children, not grandchildren."""
        store = TaskStateStore()
        root = store.create_task("Root")
        sub1 = store.create_task("Sub1", parent_id=root.task_id)
        sub3 = store.create_task("Sub3", parent_id=root.task_id)
        sub3_1 = store.create_task("Sub3.1", parent_id=sub3.task_id)
        sub3_2 = store.create_task("Sub3.2", parent_id=sub3.task_id)
        sub4 = store.create_task("Sub4", parent_id=root.task_id)
        # Complete all descendants so root becomes active
        for tid in [sub3_1.task_id, sub3_2.task_id, sub1.task_id, sub3.task_id, sub4.task_id]:
            store.record_result(tid, TaskResult(content="done", success=True))
            store.record_reviewer_decision(tid, "approved")

        session = Session()
        session.task_store = store
        node = TinyCUATaskExecutorNode(
            node_id="task_executor",
            config=create_node_config("task_executor"),
        )
        node.session = session
        continuation = node.build_continuation(session)

        assert "Child Task Verification Gate" in continuation
        # Direct children should be listed in the gate
        assert "Sub1" in continuation
        assert "Sub3" in continuation
        assert "Sub4" in continuation
        # Grandchildren should NOT be listed in the gate section — they appear
        # in the full roadmap render, but not in the "Child tasks" gate block.
        # Extract the gate section and check it doesn't contain grandchildren.
        gate_start = continuation.find("Child Task Verification Gate")
        gate_end = continuation.find("\n## ", gate_start + 1)
        if gate_end == -1:
            gate_section = continuation[gate_start:]
        else:
            gate_section = continuation[gate_start:gate_end]
        assert "Sub3.1" not in gate_section
        assert "Sub3.2" not in gate_section
