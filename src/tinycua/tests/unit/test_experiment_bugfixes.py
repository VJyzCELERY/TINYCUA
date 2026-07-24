"""Tests for experiment-analysis bug fixes: FR-077..FR-081."""

from __future__ import annotations

import pytest

from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


class TestReviewerApprovalEvidence:
    """Approval requires executor evidence rather than generated fallback state."""

    def test_leaf_task_without_result_is_rejected(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        with pytest.raises(ValueError, match="requires successful executor evidence"):
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
        with pytest.raises(ValueError, match="requires successful executor evidence"):
            store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)
        assert root.result is None
        assert root.status == TaskStatus.IN_PROGRESS


class TestExecutorTaskOwnership:
    """TaskExecutor reports its active task and never sibling completion."""

    def test_executor_reports_only_the_active_task(self):
        from tinycua.loops.task_nodes import _TASK_EXECUTOR_INSTRUCTION

        assert "report only the active task's outcome" in _TASK_EXECUTOR_INSTRUCTION.lower()
        assert "sibling" not in _TASK_EXECUTOR_INSTRUCTION.lower()

    def test_reviewer_decides_only_the_active_task(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_INSTRUCTION

        assert "only the active task" in _RESULT_REVIEWER_INSTRUCTION.lower()
        assert "sibling" not in _RESULT_REVIEWER_INSTRUCTION.lower()
        assert "do not edit files" in _RESULT_REVIEWER_INSTRUCTION.lower()


class TestReviewerTestGuidanceGeneric:
    """FR-081: reviewer guidance is generic + includes unicode escape check."""

    def test_guidance_says_actually_works(self):
        from tinycua.loops.node_guidance import build_reviewer_tool_guidance
        class _FakeTool:
            def __init__(self, name):
                self.name = name
        tools = [_FakeTool("read_file"), _FakeTool("run_shell"), _FakeTool("task_review_decision")]
        guidance = build_reviewer_tool_guidance(tools)
        assert "actually works" in guidance.lower() or "functional" in guidance.lower()

    def test_guidance_includes_unicode_escape_check(self):
        from tinycua.loops.node_guidance import build_reviewer_tool_guidance
        class _FakeTool:
            def __init__(self, name):
                self.name = name
        tools = [_FakeTool("read_file"), _FakeTool("run_shell"), _FakeTool("task_review_decision")]
        guidance = build_reviewer_tool_guidance(tools)
        assert "u[0-9a-f]" in guidance.lower() or "unicode escape" in guidance.lower()

    def test_continuation_includes_unicode_escape_check(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_CONTINUATION
        assert "u[0-9a-f]" in _RESULT_REVIEWER_CONTINUATION.lower() or "unicode escape" in _RESULT_REVIEWER_CONTINUATION.lower()
