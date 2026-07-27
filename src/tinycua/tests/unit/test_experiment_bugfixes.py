"""Tests for experiment-analysis bug fixes: FR-077..FR-081."""

from __future__ import annotations

import pytest

from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


class TestReviewerApprovalEvidence:
    """Approval requires an executor report rather than generated fallback state."""

    def test_leaf_task_without_result_is_rejected(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        with pytest.raises(
            ValueError, match="requires a successful non-empty executor report"
        ):
            store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        assert child.result is None
        assert child.status == TaskStatus.IN_PROGRESS

    def test_parent_task_without_its_own_result_is_rejected(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="done", success=True))
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        # Root has no independent executor result and cannot aggregate one.
        with pytest.raises(
            ValueError, match="requires a successful non-empty executor report"
        ):
            store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)
        assert root.result is None
        assert root.status == TaskStatus.IN_PROGRESS


class TestExecutorTaskOwnership:
    """TaskExecutor reports its active task and never sibling completion."""

    def test_executor_reports_only_the_active_task(self):
        from tinycua.loops.task_nodes import _TASK_EXECUTOR_INSTRUCTION

        assert (
            "report only the active task's outcome"
            in _TASK_EXECUTOR_INSTRUCTION.lower()
        )
        assert "do not intentionally implement pending sibling" in (
            _TASK_EXECUTOR_INSTRUCTION.lower()
        )

    def test_reviewer_decides_only_the_active_task(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_INSTRUCTION

        assert "only the active task" in _RESULT_REVIEWER_INSTRUCTION.lower()
        assert "do not edit files" in _RESULT_REVIEWER_INSTRUCTION.lower()


class TestReviewerTestGuidanceGeneric:
    """FR-081: reviewer guidance stays acceptance-driven and generic."""

    def test_guidance_says_actually_works(self):
        from tinycua.loops.node_guidance import build_reviewer_tool_guidance

        class _FakeTool:
            def __init__(self, name):
                self.name = name

        tools = [
            _FakeTool("read_file"),
            _FakeTool("run_shell"),
            _FakeTool("task_review_decision"),
        ]
        guidance = build_reviewer_tool_guidance(tools)
        assert "actually works" in guidance.lower() or "functional" in guidance.lower()

    def test_guidance_avoids_historical_corruption_checks(self):
        from tinycua.loops.node_guidance import build_reviewer_tool_guidance

        class _FakeTool:
            def __init__(self, name):
                self.name = name

        tools = [
            _FakeTool("read_file"),
            _FakeTool("run_shell"),
            _FakeTool("task_review_decision"),
        ]
        guidance = build_reviewer_tool_guidance(tools)
        assert "acceptance criteria" in guidance.lower()
        assert "unicode escape" not in guidance.lower()
        assert "markdown with math" not in guidance.lower()

    def test_continuation_avoids_fixed_command_recipes(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_CONTINUATION

        lowered = _RESULT_REVIEWER_CONTINUATION.lower()
        assert "acceptance criteria" in lowered
        assert "grep -c" not in lowered
        assert "python -c" not in lowered
