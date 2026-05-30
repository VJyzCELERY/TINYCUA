"""Unit tests for each tinycua.state object type and validation rule."""

from __future__ import annotations

import dataclasses
import json
import typing

import pytest

from tinycua.state import (
    AcceptedResult,
    AgentState,
    ContextEnhancedQuery,
    ContextUpdate,
    DigestedInformation,
    ExecutionLog,
    ExecutionLogEntry,
    ModeDecision,
    ReviewerDecision,
    Session,
    Task,
    TaskResult,
    WorkerConfig,
    WorkerResult,
)
from tinycua.state.base import StateObject


# =========================================================================
# Session
# =========================================================================


class TestSessionUnit:
    """Unit tests for Session."""

    def test_minimal_construction(self):
        """Session can be constructed with required fields only."""
        session = Session(
            session_id="s-1",
            owner_type="primary",
            owner_name="user",
            chat_history=[],
            context="",
        )
        assert session.session_id == "s-1"
        assert session.owner_type == "primary"
        assert session.owner_name == "user"
        assert session.chat_history == []
        assert session.context == ""
        assert session.execution_log is None

    def test_with_execution_log(self):
        """Session with execution_log is constructed correctly."""
        log = ExecutionLog(entries=[])
        session = Session(
            session_id="s-2",
            owner_type="child",
            owner_name="worker",
            chat_history=[{"role": "user", "content": "hi"}],
            context="ctx",
            execution_log=log,
        )
        assert session.execution_log is not None
        assert session.execution_log.entries == []

    def test_invalid_owner_type(self):
        """Session rejects invalid owner_type."""
        with pytest.raises(ValueError, match="owner_type"):
            Session(
                session_id="s-3",
                owner_type="invalid",
                owner_name="test",
                chat_history=[],
                context="",
            )

    def test_to_dict_basic(self):
        """Session.to_dict returns expected structure."""
        session = Session(
            session_id="s-4",
            owner_type="primary",
            owner_name="user",
            chat_history=[{"role": "user", "content": "hello"}],
            context="## Context",
        )
        d = session.to_dict()
        assert d["session_id"] == "s-4"
        assert d["owner_type"] == "primary"
        assert d["execution_log"] is None

    def test_to_json_is_valid_json(self):
        """Session.to_json produces valid JSON."""
        session = Session(
            session_id="s-5",
            owner_type="primary",
            owner_name="user",
            chat_history=[],
            context="",
        )
        parsed = json.loads(session.to_json())
        assert parsed["session_id"] == "s-5"

    def test_from_dict_missing_required(self):
        """Session.from_dict raises error for missing required field."""
        with pytest.raises(ValueError, match="session_id"):
            Session.from_dict({
                "owner_type": "primary",
                "owner_name": "user",
                "chat_history": [],
                "context": "",
            })


# =========================================================================
# ContextEnhancedQuery
# =========================================================================


class TestContextEnhancedQueryUnit:
    """Unit tests for ContextEnhancedQuery."""

    def test_construction(self):
        """ContextEnhancedQuery can be constructed."""
        q = ContextEnhancedQuery(enhanced_query="What is AI?")
        assert q.enhanced_query == "What is AI?"

    def test_round_trip(self):
        """ContextEnhancedQuery round-trips through dict."""
        q = ContextEnhancedQuery(enhanced_query="Query")
        assert ContextEnhancedQuery.from_dict(q.to_dict()) == q


# =========================================================================
# ModeDecision
# =========================================================================


class TestModeDecisionUnit:
    """Unit tests for ModeDecision."""

    def test_all_modes(self):
        """All valid mode values are accepted."""
        for mode in ("primary_agent", "worker", "uncertain"):
            kwargs = {
                "mode": mode,
                "score": 0.5,
                "confidence": 0.5,
                "reasons": ["test"],
            }
            if mode == "uncertain":
                kwargs["uncertain_next_action"] = "ask_user"
            decision = ModeDecision(**kwargs)
            assert decision.mode == mode

    def test_mode_case_sensitive(self):
        """Mode validation is case-sensitive."""
        with pytest.raises(ValueError, match="mode"):
            ModeDecision(
                mode="Primary_Agent",
                score=0.5,
                confidence=0.5,
                reasons=["test"],
            )

    def test_uncertain_next_action_validation(self):
        """Uncertain next action is validated when provided."""
        with pytest.raises(ValueError, match="uncertain_next_action"):
            ModeDecision(
                mode="worker",
                score=0.5,
                confidence=0.5,
                reasons=["test"],
                uncertain_next_action="bad_action",
            )

    def test_to_dict_with_uncertain(self):
        """ModeDecision.to_dict with uncertain mode includes uncertain_next_action."""
        decision = ModeDecision(
            mode="uncertain",
            score=0.6,
            confidence=0.4,
            reasons=["unsure"],
            uncertain_next_action="ask_user",
        )
        d = decision.to_dict()
        assert d["uncertain_next_action"] == "ask_user"

    def test_from_dict_missing_uncertain_next_action(self):
        """from_dict raises for uncertain mode without next_action."""
        with pytest.raises(ValueError, match="uncertain_next_action is required"):
            ModeDecision.from_dict({
                "mode": "uncertain",
                "score": 0.5,
                "confidence": 0.5,
                "reasons": ["unsure"],
            })


# =========================================================================
# DigestedInformation
# =========================================================================


class TestDigestedInformationUnit:
    """Unit tests for DigestedInformation."""

    def test_required_only(self):
        """DigestedInformation with only required fields."""
        info = DigestedInformation(
            context_summary="Summary",
            key_points=["p1"],
        )
        assert info.context_summary == "Summary"
        assert info.key_points == ["p1"]
        assert info.advisory_instructions is None
        assert info.constraints is None
        assert info.known_gaps is None

    def test_all_fields(self):
        """DigestedInformation with all fields populated."""
        info = DigestedInformation(
            context_summary="Summary",
            key_points=["p1", "p2"],
            advisory_instructions="Do X",
            constraints=["c1"],
            known_gaps=["g1"],
        )
        assert info.advisory_instructions == "Do X"
        assert info.constraints == ["c1"]
        assert info.known_gaps == ["g1"]

    def test_empty_key_points(self):
        """DigestedInformation allows empty key_points."""
        info = DigestedInformation(
            context_summary="Summary",
            key_points=[],
        )
        assert info.key_points == []


# =========================================================================
# WorkerConfig
# =========================================================================


class TestWorkerConfigUnit:
    """Unit tests for WorkerConfig."""

    @pytest.mark.parametrize("effort", ["none", "high"])
    def test_valid_effort(self, effort):
        """Valid effort values are accepted."""
        config = WorkerConfig(effort=effort)
        assert config.effort == effort

    def test_invalid_effort(self):
        """WorkerConfig rejects invalid effort value."""
        with pytest.raises(ValueError, match="effort"):
            WorkerConfig(effort="medium")


# =========================================================================
# Task
# =========================================================================


class TestTaskUnit:
    """Unit tests for Task tree node."""

    def test_leaf_task_defaults(self):
        """A leaf task defaults to task_result=None, parent_task_id=None."""
        task = Task(
            task_id="t-1",
            task_name="Test",
            task_description="A test task",
            task_context="ctx",
            success_criteria=["done"],
            confidence=0.9,
        )
        assert task.child_tasks is None
        assert task.task_result is None
        assert task.parent_task_id is None
        assert task.task_id == "t-1"
        assert not task.is_completed

    def test_container_task(self):
        """A container task has child_tasks and auto-sets parent_task_id."""
        child = Task(
            task_id="t-1.1",
            task_name="Child",
            task_description="Child task",
            task_context="ctx",
            success_criteria=["done"],
            confidence=0.8,
        )
        parent = Task(
            task_id="t-1",
            task_name="Parent",
            task_description="Parent task",
            task_context="ctx",
            success_criteria=["all done"],
            confidence=0.7,
            child_tasks=[child],
        )
        assert parent.child_tasks is not None
        assert len(parent.child_tasks) == 1
        assert parent.child_tasks[0].task_id == "t-1.1"
        # parent_task_id auto-set on child
        assert child.parent_task_id == "t-1"

    def test_deeply_nested(self):
        """Task supports deep nesting with auto parent_task_id propagation."""
        level3 = Task(
            task_id="l3", task_name="L3", task_description="d", task_context="c",
            success_criteria=["x"], confidence=0.9,
        )
        level2 = Task(
            task_id="l2", task_name="L2", task_description="d", task_context="c",
            success_criteria=["x"], confidence=0.9,
            child_tasks=[level3],
        )
        level1 = Task(
            task_id="l1", task_name="L1", task_description="d", task_context="c",
            success_criteria=["x"], confidence=0.9,
            child_tasks=[level2],
        )
        assert level1.child_tasks[0].child_tasks[0].task_id == "l3"
        assert level3.parent_task_id == "l2"
        assert level2.parent_task_id == "l1"

    def test_parent_task_id_explicit_match(self):
        """Explicit parent_task_id matching child_tasks is accepted."""
        child = Task(
            task_id="c1", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            parent_task_id="p1",
        )
        parent = Task(
            task_id="p1", task_name="Parent", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        assert child.parent_task_id == "p1"
        assert parent.child_tasks[0].task_id == "c1"

    def test_parent_task_id_mismatch_raises(self):
        """Conflicting parent_task_id in child raises ValueError."""
        child = Task(
            task_id="c1", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            parent_task_id="wrong_parent",
        )
        with pytest.raises(ValueError, match="parent_task_id"):
            Task(
                task_id="p1", task_name="Parent", task_description="d",
                task_context="c", success_criteria=["x"], confidence=0.5,
                child_tasks=[child],
            )


# =========================================================================
# Task Status
# =========================================================================


class TestTaskStatus:
    """Tests for task_result-based status on Task tree nodes."""

    def test_leaf_not_started(self):
        """Leaf with task_result=None is not_started."""
        task = Task(
            task_id="t-1", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        assert task.task_result is None
        assert not task.is_completed
        assert task._status_marker() == " "

    def test_leaf_inprogress(self):
        """Leaf with inprogress result is not completed."""
        result = TaskResult(task_id="t-1", status="inprogress", result="working...")
        task = Task(
            task_id="t-1", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=result,
        )
        assert not task.is_completed
        assert task._status_marker() == "*"

    def test_leaf_completed(self):
        """Leaf with completed result is completed."""
        result = TaskResult(task_id="t-1", status="completed", result="done")
        task = Task(
            task_id="t-1", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=result,
        )
        assert task.is_completed
        assert task._status_marker() == "x"

    def test_leaf_failed(self):
        """Leaf with failed result."""
        result = TaskResult(task_id="t-1", status="failed", result="error")
        task = Task(
            task_id="t-1", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=result,
        )
        assert not task.is_completed
        assert task._status_marker() == "-"

    def test_leaf_blocked(self):
        """Leaf with blocked result."""
        result = TaskResult(task_id="t-1", status="blocked", result="waiting")
        task = Task(
            task_id="t-1", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=result,
        )
        assert not task.is_completed
        assert task._status_marker() == "/"

    def test_container_completed_when_children_completed(self):
        """Container is_completed is True when all children are completed."""
        child = Task(
            task_id="c1", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="c1", status="completed", result="ok"),
        )
        parent = Task(
            task_id="p1", task_name="Parent", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        assert parent.is_completed

    def test_container_not_completed_when_child_not_completed(self):
        """Container is_completed is False when a child is not completed."""
        child = Task(
            task_id="c1", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        parent = Task(
            task_id="p1", task_name="Parent", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        assert not parent.is_completed

    def test_container_marker_aggregates_children(self):
        """Container marker reflects most severe child status."""
        child_a = Task(
            task_id="a", task_name="A", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="a", status="failed", result="x"),
        )
        child_b = Task(
            task_id="b", task_name="B", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="b", status="completed", result="x"),
        )
        parent = Task(
            task_id="p1", task_name="Parent", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child_a, child_b],
        )
        assert parent._status_marker() == "-"


# =========================================================================
# Task Display
# =========================================================================


class TestTaskDisplay:
    """Tests for the Task.display() DFS pre-order traversal method."""

    def test_leaf_display(self):
        """A leaf task displays as a single line. Root hides UUID."""
        task = Task(
            task_id="uuid-1", task_name="Research", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        result = task.display()
        assert result == "[ ] - Research"

    def test_finished_leaf_display(self):
        """A completed leaf task shows [x]."""
        result = TaskResult(task_id="uuid-2", status="completed", result="done")
        task = Task(
            task_id="uuid-2", task_name="Done task", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=result,
        )
        assert task.display() == "[x] - Done task"

    def test_container_display(self):
        """A container task displays with indented children."""
        child = Task(
            task_id="T-0", task_name="Gather sources", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        parent = Task(
            task_id="uuid-root", task_name="Research", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        expected = (
            "[ ] - Research\n"
            "  [ ] - Gather sources - T-0"
        )
        assert parent.display() == expected

    def test_deeply_nested_display(self):
        """Deeply nested tree displays with correct indentation levels."""
        grandchild = Task(
            task_id="T-0.0", task_name="Read paper", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="T-0.0", status="completed", result="ok"),
        )
        child = Task(
            task_id="T-0", task_name="Gather sources", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[grandchild],
        )
        parent = Task(
            task_id="uuid-root", task_name="Research", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        expected = (
            "[x] - Research\n"
            "  [x] - Gather sources - T-0\n"
            "    [x] - Read paper - T-0.0"
        )
        assert parent.display() == expected

    def test_multiple_children_display(self):
        """Tree with multiple children at same level displays correctly."""
        child_a = Task(
            task_id="T-0", task_name="Gather", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="T-0", status="completed", result="ok"),
        )
        child_b = Task(
            task_id="T-1", task_name="Analyze", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        parent = Task(
            task_id="uuid-root", task_name="Research", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child_a, child_b],
        )
        expected = (
            "[ ] - Research\n"
            "  [x] - Gather - T-0\n"
            "  [ ] - Analyze - T-1"
        )
        assert parent.display() == expected

    def test_empty_child_tasks(self):
        """Task with empty child_tasks list is container — all children completed."""
        task = Task(
            task_id="uuid-empty", task_name="Empty", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[],
        )
        assert task.is_completed
        result = task.display()
        assert result == "[x] - Empty"

    def test_display_with_custom_indent(self):
        """Display respects a custom initial indent level."""
        task = Task(
            task_id="uuid-1", task_name="Task", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        result = task.display(indent=2)
        assert result == "    [ ] - Task"

    def test_display_from_child_shows_full_tree(self):
        """display() from a child task still shows the full tree from root."""
        grandchild = Task(
            task_id="T-0.0", task_name="Deep", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        child = Task(
            task_id="T-0", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[grandchild],
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        # Calling display from the deepest grandchild should still show full tree
        result = grandchild.display()
        expected = (
            "[ ] - Root\n"
            "  [ ] - Child - T-0\n"
            "    [ ] - Deep - T-0.0"
        )
        assert result == expected
        # Verify the root is accessible from anywhere
        assert grandchild.root() is root

    def test_display_trim_shows_subtree_only(self):
        """display(trim=True) shows only the subtree from the current node."""
        grandchild = Task(
            task_id="T-0.0", task_name="Deep", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        child = Task(
            task_id="T-0", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[grandchild],
        )
        Task(  # root — only used implicitly via _parent
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        # trim=True from child → only child's subtree
        result = child.display(trim=True)
        expected = (
            "[ ] - Child - T-0\n"
            "  [ ] - Deep - T-0.0"
        )
        assert result == expected


# =========================================================================
# Task Navigation
# =========================================================================


class TestTaskNavigation:
    """Tests for Task tree navigation: parent, root, traverse, at_id."""

    def test_parent_none_for_root(self):
        """Root task has parent=None."""
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        assert root.parent is None
        assert root.is_root()

    def test_parent_set_on_child(self):
        """Child task has parent object reference set."""
        child = Task(
            task_id="T-0", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        parent = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        assert child.parent is parent
        assert not child.is_root()

    def test_root_from_nested_child(self):
        """root() returns top-most task from deeply nested child."""
        leaf = Task(
            task_id="T-2.0", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        mid = Task(
            task_id="T-2", task_name="Mid", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf],
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[mid],
        )
        assert leaf.root() is root
        assert mid.root() is root
        assert root.root() is root

    def test_parent_chain_mutation_visible(self):
        """Changing task_result via parent reference is visible from child."""
        child = Task(
            task_id="T-0", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="T-0", status="completed", result="ok"),
        )
        parent = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        # Mutate child via parent reference
        child.parent.child_tasks[0].task_result = TaskResult(
            task_id="T-0", status="failed", result="error",
        )
        assert child.task_result.status == "failed"
        assert parent.child_tasks[0].task_result.status == "failed"


class TestTaskTraverse:
    """Tests for Task.traverse() DFS pre-order next-executable-leaf."""

    def test_leaf_not_completed_returns_self(self):
        """traverse on a non-completed leaf returns itself."""
        task = Task(
            task_id="uuid-1", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        assert task.traverse() is task

    def test_leaf_completed_goes_to_ancestor(self):
        """traverse on a completed leaf goes up to non-completed ancestor."""
        leaf_a = Task(
            task_id="T-0", task_name="A", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="T-0", status="completed", result="ok"),
        )
        leaf_b = Task(
            task_id="T-1", task_name="B", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf_a, leaf_b],
        )
        assert leaf_a.traverse() is leaf_b
        assert leaf_a.parent is root

    def test_goes_to_deepest_non_completed(self):
        """traverse descends to deepest non-completed leaf."""
        grandchild = Task(
            task_id="T-0.0", task_name="Deep", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        child = Task(
            task_id="T-0", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[grandchild],
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        assert root.traverse() is grandchild

    def test_skips_completed_children(self):
        """traverse skips completed children to find non-completed one."""
        leaf_a = Task(
            task_id="T-0", task_name="A", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="T-0", status="completed", result="ok"),
        )
        leaf_b = Task(
            task_id="T-1", task_name="B", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf_a, leaf_b],
        )
        assert root.traverse() is leaf_b

    def test_all_completed_returns_root(self):
        """traverse returns root when everything is completed."""
        leaf = Task(
            task_id="T-0", task_name="Done", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="T-0", status="completed", result="ok"),
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf],
        )
        assert root.traverse() is root

    def test_completed_child_goes_up_then_down(self):
        """Completed child → up past completed parent → down to non-completed sibling."""
        leaf_a = Task(
            task_id="T-0", task_name="A", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="T-0", status="completed", result="ok"),
        )
        leaf_b = Task(
            task_id="T-1", task_name="B", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            task_result=TaskResult(task_id="T-1", status="completed", result="ok"),
        )
        leaf_c = Task(
            task_id="T-2", task_name="C", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf_a, leaf_b, leaf_c],
        )
        assert leaf_b.traverse() is leaf_c
        assert leaf_b.parent is root


class TestTaskAtId:
    """Tests for Task.at_id() structured ID navigation."""

    def test_at_id_root(self):
        """at_id returns root when given root's ID."""
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        assert root.at_id("uuid-root") is root

    def test_at_id_child(self):
        """at_id navigates to child by T-{idx}."""
        child = Task(
            task_id="T-2", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[
                Task(task_id="T-0", task_name="A", task_description="d",
                     task_context="c", success_criteria=["x"], confidence=0.5),
                Task(task_id="T-1", task_name="B", task_description="d",
                     task_context="c", success_criteria=["x"], confidence=0.5),
                child,
            ],
        )
        assert root.at_id("T-2") is child

    def test_at_id_deeply_nested(self):
        """at_id navigates to deeply nested task by T-{idx}.{subidx}...."""
        target = Task(
            task_id="T-0.1.2", task_name="Target", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        deep_child = Task(
            task_id="T-0.1", task_name="L2", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[
                Task(task_id="T-0.1.0", task_name="X", task_description="d",
                     task_context="c", success_criteria=["x"], confidence=0.5),
                Task(task_id="T-0.1.1", task_name="Y", task_description="d",
                     task_context="c", success_criteria=["x"], confidence=0.5),
                target,
            ],
        )
        top_child = Task(
            task_id="T-0", task_name="L1", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[
                Task(task_id="T-0.0", task_name="Z", task_description="d",
                     task_context="c", success_criteria=["x"], confidence=0.5),
                deep_child,
            ],
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[top_child],
        )
        assert root.at_id("T-0.1.2") is target
        # Also works from anywhere in the tree
        assert top_child.at_id("T-0.1.2") is target
        assert target.at_id("T-0.1.2") is target

    def test_at_id_from_child(self):
        """at_id works from a non-root task by navigating to root first."""
        child = Task(
            task_id="T-0", task_name="Child", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[child],
        )
        assert child.at_id("uuid-root") is root
        assert child.at_id("T-0") is child

    def test_at_id_invalid_format_raises(self):
        """at_id raises ValueError for unknown ID format."""
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        with pytest.raises(ValueError, match="Unknown task ID format"):
            root.at_id("bad-format")

    def test_at_id_index_out_of_range_raises(self):
        """at_id raises ValueError when index exceeds child count."""
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[
                Task(task_id="T-0", task_name="Only", task_description="d",
                     task_context="c", success_criteria=["x"], confidence=0.5),
            ],
        )
        with pytest.raises(ValueError, match="No child at index"):
            root.at_id("T-5")


class TestTaskSetParents:
    """Tests for set_parents() re-establishing references after deserialization."""

    def test_set_parents_after_from_dict(self):
        """from_dict auto-calls set_parents, parent references work."""
        leaf = Task(
            task_id="T-0", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf],
        )
        restored = Task.from_dict(root.to_dict())
        # Parent references should work
        assert restored.child_tasks[0].parent is restored
        assert restored.child_tasks[0].root() is restored
        assert restored.child_tasks[0].is_root() is False

    def test_set_parents_after_from_json(self):
        """from_json auto-calls set_parents, navigation works."""
        leaf = Task(
            task_id="T-0", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf],
        )
        restored = Task.from_json(root.to_json())
        assert restored.child_tasks[0].parent is restored
        assert restored.traverse() is restored.child_tasks[0]

    def test_parent_not_in_serialized_dict(self):
        """_parent is not in the serialized dict."""
        leaf = Task(
            task_id="T-0", task_name="Leaf", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
        )
        root = Task(
            task_id="uuid-root", task_name="Root", task_description="d",
            task_context="c", success_criteria=["x"], confidence=0.5,
            child_tasks=[leaf],
        )
        d = root.to_dict()
        assert "_parent" not in d
        assert "_parent" not in d["child_tasks"][0]


# =========================================================================
# TaskResult
# =========================================================================


class TestTaskResultUnit:
    """Unit tests for TaskResult."""

    @pytest.mark.parametrize("status", ["not_started", "inprogress", "completed", "failed", "blocked"])
    def test_valid_status(self, status):
        """Valid status values are accepted."""
        result = TaskResult(task_id="t-1", status=status, result="ok")
        assert result.status == status

    def test_invalid_status(self):
        """TaskResult rejects invalid status."""
        with pytest.raises(ValueError, match="status"):
            TaskResult(task_id="t-1", status="invalid", result="x")

    def test_optional_fields(self):
        """TaskResult with all optional fields."""
        result = TaskResult(
            task_id="t-1",
            status="completed",
            result="Done",
            discovered_sequence_issues=["ordering"],
            uncertainty_notes=["unclear"],
        )
        assert result.discovered_sequence_issues == ["ordering"]
        assert result.uncertainty_notes == ["unclear"]


# =========================================================================
# ContextUpdate
# =========================================================================


class TestContextUpdateUnit:
    """Unit tests for ContextUpdate."""

    def test_construction(self):
        """ContextUpdate can be constructed with required fields."""
        cu = ContextUpdate(target_task_id="t-1", update="New context")
        assert cu.target_task_id == "t-1"
        assert cu.update == "New context"


# =========================================================================
# ReviewerDecision
# =========================================================================


class TestReviewerDecisionUnit:
    """Unit tests for ReviewerDecision."""

    @pytest.mark.parametrize("status", ["accepted", "retry", "replan", "escalate_user"])
    def test_valid_status(self, status):
        """Valid status values are accepted."""
        decision = ReviewerDecision(
            task_id="t-1", status=status, reason="ok", confidence=0.8,
        )
        assert decision.status == status

    def test_invalid_status(self):
        """ReviewerDecision rejects invalid status."""
        with pytest.raises(ValueError, match="status"):
            ReviewerDecision(
                task_id="t-1", status="invalid", reason="x", confidence=0.5,
            )

    def test_with_context_updates(self):
        """ReviewerDecision with context updates."""
        updates = [
            ContextUpdate(target_task_id="t-2", update="Update 1"),
        ]
        decision = ReviewerDecision(
            task_id="t-1",
            status="retry",
            reason="Needs more info",
            confidence=0.6,
            context_updates=updates,
            retry_instructions="Check sources",
        )
        assert len(decision.context_updates) == 1
        assert decision.retry_instructions == "Check sources"


# =========================================================================
# WorkerResult / AcceptedResult
# =========================================================================


class TestWorkerResultUnit:
    """Unit tests for WorkerResult and AcceptedResult."""

    def test_empty_accepted_results(self):
        """WorkerResult can have empty accepted_results."""
        wr = WorkerResult(accepted_results=[])
        assert wr.accepted_results == []

    def test_with_results(self):
        """WorkerResult with accepted results."""
        ar = AcceptedResult(task_id="t-1", name="Task 1", result="Output")
        wr = WorkerResult(accepted_results=[ar])
        assert len(wr.accepted_results) == 1
        assert wr.accepted_results[0].task_id == "t-1"


# =========================================================================
# AgentState
# =========================================================================


class TestAgentStateUnit:
    """Unit tests for AgentState."""

    def test_default_values(self):
        """AgentState uses default values correctly."""
        state = AgentState(active_agent="analyst")
        assert state.status == "idle"
        assert state.consecutive_failures == 0
        assert state.active_task_id is None
        assert state.resume_target is None

    def test_all_fields(self):
        """AgentState with all fields populated."""
        state = AgentState(
            active_agent="analyst",
            active_task_id="t-1",
            status="running",
            resume_target="continue",
            consecutive_failures=3,
        )
        assert state.active_agent == "analyst"
        assert state.active_task_id == "t-1"
        assert state.status == "running"
        assert state.consecutive_failures == 3

    def test_zero_failures(self):
        """AgentState allows zero consecutive_failures."""
        state = AgentState(active_agent="test", consecutive_failures=0)
        assert state.consecutive_failures == 0

    def test_negative_failures_rejected(self):
        """AgentState rejects negative consecutive_failures."""
        with pytest.raises(ValueError, match="consecutive_failures must be non-negative"):
            AgentState(active_agent="test", consecutive_failures=-1)

    @pytest.mark.parametrize(
        "status", ["idle", "running", "blocked", "terminated"],
    )
    def test_valid_statuses(self, status):
        """All valid AgentState statuses are accepted."""
        state = AgentState(active_agent="test", status=status)
        assert state.status == status

    def test_invalid_status(self):
        """AgentState rejects invalid status."""
        with pytest.raises(ValueError, match="status"):
            AgentState(active_agent="test", status="unknown")


# =========================================================================
# ExecutionLog / ExecutionLogEntry
# =========================================================================


class TestExecutionLogUnit:
    """Unit tests for ExecutionLog and ExecutionLogEntry."""

    def test_empty_log(self):
        """ExecutionLog can be empty."""
        log = ExecutionLog(entries=[])
        assert log.entries == []

    def test_with_entries(self):
        """ExecutionLog with entries."""
        entry = ExecutionLogEntry(
            action="run_task",
            outcome="success",
            decision="chose path A",
        )
        log = ExecutionLog(entries=[entry])
        assert log.entries[0].action == "run_task"
        assert log.entries[0].decision == "chose path A"

    def test_entry_without_decision(self):
        """ExecutionLogEntry can omit decision."""
        entry = ExecutionLogEntry(action="query", outcome="failure")
        assert entry.decision is None


# =========================================================================
# Serialization Edge Cases
# =========================================================================


class TestSerializationEdgeCases:
    """Edge case tests for serialization."""

    def test_empty_string_fields(self):
        """Empty string fields are preserved in round-trip."""
        task = Task(
            task_id="", task_name="", task_description="", task_context="",
            success_criteria=[], confidence=0.0,
        )
        restored = Task.from_dict(task.to_dict())
        assert restored == task

    def test_special_characters_in_strings(self):
        """Special characters in string fields survive JSON round-trip."""
        info = DigestedInformation(
            context_summary="Line1\nLine2\nTab\there",
            key_points=["Quote: \"hello\"", "Unicode: ñoño"],
        )
        restored = DigestedInformation.from_json(info.to_json())
        assert restored == info

    def test_very_nested_task_tree(self):
        """Very deeply nested Task tree survives round-trip."""
        # Build 5 levels of nesting
        current = Task(
            task_id="l5", task_name="deep", task_description="d", task_context="c",
            success_criteria=["x"], confidence=0.5,
        )
        for i in range(4, 0, -1):
            current = Task(
                task_id=f"l{i}", task_name=f"L{i}", task_description="d", task_context="c",
                success_criteria=["x"], confidence=0.5,
                child_tasks=[current],
            )
        restored = Task.from_json(current.to_json())
        assert restored == current
        # Verify nesting depth preserved
        assert restored.child_tasks[0].child_tasks[0].child_tasks[0].child_tasks[0].task_id == "l5"

    def test_boolean_in_chat_history(self):
        """Booleans in chat_history dicts survive round-trip."""
        session = Session(
            session_id="s-1",
            owner_type="primary",
            owner_name="user",
            chat_history=[
                {"role": "user", "content": "hello", "is_final": True},
            ],
            context="",
        )
        restored = Session.from_json(session.to_json())
        assert restored == session
        assert restored.chat_history[0]["is_final"] is True

    def test_numeric_values_precision(self):
        """Float precision is maintained through JSON round-trip."""
        decision = ModeDecision(
            mode="worker",
            score=0.123456789,
            confidence=0.987654321,
            reasons=["test"],
        )
        restored = ModeDecision.from_json(decision.to_json())
        assert abs(restored.score - 0.123456789) < 1e-9

    def test_empty_list_fields(self):
        """Empty lists in various fields survive round-trip."""
        result = TaskResult(
            task_id="t-1",
            status="failed",
            result="Error",
            discovered_sequence_issues=[],
            uncertainty_notes=[],
        )
        restored = TaskResult.from_dict(result.to_dict())
        assert restored == result

    def test_none_vs_empty_list_optional_fields(self):
        """Optional list fields: None vs empty list are distinguished."""
        info_with_none = DigestedInformation(
            context_summary="S", key_points=["p"],
            constraints=None,
        )
        info_with_empty = DigestedInformation(
            context_summary="S", key_points=["p"],
            constraints=[],
        )
        assert info_with_none.constraints is None
        assert info_with_empty.constraints == []

        restored_none = DigestedInformation.from_dict(info_with_none.to_dict())
        restored_empty = DigestedInformation.from_dict(info_with_empty.to_dict())
        assert restored_none.constraints is None
        assert restored_empty.constraints == []


# =========================================================================
# StateObject Base Edge Cases
# =========================================================================


@dataclasses.dataclass
class _TestWithDefaultFactory(StateObject):
    name: str
    tags: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class _TestWithNoneType(StateObject):
    name: str
    metadata: None = None


@dataclasses.dataclass
class _TestWithDictField(StateObject):
    name: str
    config: dict = dataclasses.field(default_factory=dict)


class TestBaseEdgeCases:
    """Edge case tests for the StateObject base class."""

    def test_from_dict_omits_optional_with_default_factory(self):
        """from_dict handles optional fields with default_factory omitted."""
        obj = _TestWithDefaultFactory.from_dict({"name": "test"})
        assert obj.name == "test"
        assert obj.tags == []

    def test_from_dict_none_type_hint(self):
        """from_dict handles fields with None type hint (resolved_type is None).

        When the annotation resolves to None (singleton), resolved_type is None
        and the raw value is passed through directly.
        """
        obj = _TestWithNoneType.from_dict({"name": "test", "metadata": "through"})
        assert obj.name == "test"
        assert obj.metadata == "through"

    def test_convert_value_union_non_none(self):
        """_convert_value handles Union with non-None args correctly."""
        value = _TestWithDefaultFactory._convert_value(
            {"name": "nested"}, _TestWithDefaultFactory,
        )
        assert isinstance(value, _TestWithDefaultFactory)
        assert value.name == "nested"

    def test_convert_value_list_fallback_non_list(self):
        """_convert_value returns non-list value as-is when origin is list but value is not a list."""
        value = _TestWithDictField._convert_value(42, list[str])
        assert value == 42

    def test_convert_value_dict_fallback(self):
        """_convert_value returns dict value as-is when origin is dict."""
        value = _TestWithDictField._convert_value({"raw": "data"}, dict[str, str])
        assert value == {"raw": "data"}

    def test_convert_value_union_all_none_type(self):
        """_convert_value returns value as-is when Union has only NoneType args.

        Covers the fallthrough path in _convert_value where non_none_args
        is empty (line 91). Constructed via _GenericAlias since Python's
        type system simplifies Union[None, None] to NoneType.
        """
        try:
            from typing import _GenericAlias
        except ImportError:
            pytest.skip("_GenericAlias not available — skip edge case test")

        union_only_none = _GenericAlias(typing.Union, (type(None),))
        value = _TestWithDefaultFactory._convert_value("fallthrough", union_only_none)
        assert value == "fallthrough"

    def test_is_state_object_type_non_type(self):
        """_is_state_object_type returns False for non-type arguments."""
        assert not StateObject._is_state_object_type(None)
        assert not StateObject._is_state_object_type("string")
        assert not StateObject._is_state_object_type(42)
        assert not StateObject._is_state_object_type([1, 2, 3])
