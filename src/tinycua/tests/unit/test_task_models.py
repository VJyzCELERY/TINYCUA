"""Unit tests for Task, TaskResult, and ReviewerDecision models."""

from tinycua.models.task import (
    ExecutionStatus,
    ReviewerDecision,
    ReviewerOutcome,
    Task,
    TaskResult,
    TaskStatus,
)


def test_task_construction_defaults():
    """Task constructs with required fields and sensible defaults."""
    task = Task(task_id="T-1", title="My Task")
    assert task.task_id == "T-1"
    assert task.title == "My Task"
    assert task.description == ""
    assert task.status == "pending"
    assert task.children == []
    assert task.active_child_id is None
    assert task.result is None
    assert task.metadata == {}


def test_task_with_children():
    """Task supports nested children."""
    child = Task(task_id="T-1.1", title="Child")
    parent = Task(task_id="T-1", title="Parent", children=[child])
    assert len(parent.children) == 1
    assert parent.children[0].task_id == "T-1.1"


def test_task_result_construction():
    """TaskResult constructs with required fields and defaults."""
    result = TaskResult(task_id="T-1")
    assert result.task_id == "T-1"
    assert result.execution_status == "not_started"
    assert result.reviewer_decision is None
    assert result.summary == ""
    assert result.artifacts == []
    assert result.metadata == {}


def test_reviewer_decision_construction():
    """ReviewerDecision constructs with required outcome field."""
    decision = ReviewerDecision(outcome="accept")
    assert decision.outcome == "accept"
    assert decision.rationale is None
    assert decision.target_task_id is None
    assert decision.metadata == {}


def test_task_status_literal_values():
    """TaskStatus accepts only the defined literal values."""
    valid_statuses: list[TaskStatus] = [
        "pending", "in_progress", "blocked", "done", "failed",
    ]
    assert len(valid_statuses) == 5


def test_execution_status_literal_values():
    """ExecutionStatus accepts only the defined literal values."""
    valid_statuses: list[ExecutionStatus] = [
        "not_started", "running", "succeeded", "failed", "blocked",
    ]
    assert len(valid_statuses) == 5


def test_reviewer_outcome_literal_values():
    """ReviewerOutcome accepts only the defined literal values."""
    valid_outcomes: list[ReviewerOutcome] = [
        "accept", "retry", "replan", "open_question",
    ]
    assert len(valid_outcomes) == 4
