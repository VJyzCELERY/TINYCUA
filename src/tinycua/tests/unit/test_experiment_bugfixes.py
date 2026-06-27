"""Tests for experiment-analysis bug fixes: FR-077..FR-081."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


class TestReviewerApprovalAutoResult:
    """FR-079: APPROVED with no result auto-generates and transitions."""

    def test_leaf_task_auto_generates_result(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        # FR-5a: approving a never-dispatched PENDING leaf is rejected.
        # Simulate the executor having picked up the task first.
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        assert child.result is not None
        assert child.result.metadata.get("auto_generated") is True
        assert child.status == TaskStatus.COMPLETED

    def test_parent_task_with_completed_children_auto_generates(self):
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="done", success=True))
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        # Root has no result but all children done → auto-generate
        store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)
        assert root.result is not None
        assert root.result.metadata.get("aggregated") is True
        assert root.status == TaskStatus.COMPLETED


class TestUnicodeEscapeDecode:
    """FR-080: _normalize_newlines decodes \\uXXXX sequences."""

    def test_decode_u2208(self):
        from tinycua.agent.tools.native.files import _normalize_newlines
        result = _normalize_newlines(r"Q \u2208 \u210e")
        assert "∈" in result
        assert "ℎ" in result  # \u210e is PLANCK CONSTANT ℎ

    def test_decode_u03a3(self):
        from tinycua.agent.tools.native.files import _normalize_newlines
        result = _normalize_newlines(r"\u03a3_d")
        assert "Σ" in result

    def test_decode_multiple_bmp_escapes(self):
        from tinycua.agent.tools.native.files import _normalize_newlines
        # Multiple BMP escapes in one string.
        result = _normalize_newlines(r"\u2208 \u03a3 \u00b7 \u00d7")
        assert "∈" in result
        assert "Σ" in result
        assert "·" in result
        assert "×" in result

    def test_preserves_latex_top(self):
        from tinycua.agent.tools.native.files import _normalize_newlines
        result = _normalize_newlines(r"$x^\top$")
        assert r"\top" in result

    def test_combined_latex_and_unicode(self):
        from tinycua.agent.tools.native.files import _normalize_newlines
        text = r"$x^\top$ \u2208 \u03a3"
        result = _normalize_newlines(text)
        assert r"\top" in result
        assert "∈" in result
        assert "Σ" in result


class TestSiblingReportingStrengthened:
    """FR-077: sibling reporting guidance is explicit about timing + guards."""

    def test_executor_says_after_completing(self):
        from tinycua.loops.task_nodes import _TASK_EXECUTOR_INSTRUCTION
        assert "after completing the active task" in _TASK_EXECUTOR_INSTRUCTION.lower()

    def test_executor_says_only_report_completed(self):
        from tinycua.loops.task_nodes import _TASK_EXECUTOR_INSTRUCTION
        assert "only report siblings you actually completed" in _TASK_EXECUTOR_INSTRUCTION.lower()

    def test_reviewer_says_after_reviewing(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_INSTRUCTION
        assert "after reviewing" in _RESULT_REVIEWER_INSTRUCTION.lower()

    def test_reviewer_says_no_task_review_decision_for_siblings(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_INSTRUCTION
        assert "do not call task_review_decision for siblings" in _RESULT_REVIEWER_INSTRUCTION.lower()


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