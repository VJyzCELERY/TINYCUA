"""Tests for task tree snapshot logging + --trace stderr routing (FR-075, FR-076)."""

from __future__ import annotations

import logging

from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore


class TestLogTreeSnapshot:
    """FR-075: _log_tree_snapshot emits multi-line INFO when _enable_trace=True."""

    def test_silent_when_trace_disabled(self, caplog):
        """No log output when _enable_trace=False."""
        store = TaskStateStore()
        store._enable_trace = False
        with caplog.at_level(logging.INFO, logger="tinycua.models.task"):
            store.create_task("Root")
        assert not any("task_tree_mutation" in r.message for r in caplog.records)

    def test_emits_when_trace_enabled(self, caplog):
        """Multi-line INFO when _enable_trace=True."""
        store = TaskStateStore()
        store._enable_trace = True
        with caplog.at_level(logging.INFO, logger="tinycua.models.task"):
            store.create_task("Root")
        assert any("task_tree_mutation" in r.message for r in caplog.records)
        assert any("create_task" in r.message for r in caplog.records)

    def test_snapshot_shows_counts_and_tasks(self, caplog):
        """Snapshot includes completed/pending/in_progress counts + per-task lines."""
        store = TaskStateStore()
        store._enable_trace = True
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        with caplog.at_level(logging.INFO, logger="tinycua.models.task"):
            store.record_result(child.task_id, TaskResult(content="done", success=True))
        messages = [r.message for r in caplog.records if "task_tree_mutation" in r.message]
        # record_result triggers transition (logs) then record_result (logs).
        assert len(messages) >= 2
        # The last record_result log should show the child with a result marker.
        last = messages[-1]
        assert "record_result" in last
        assert "Child" in last
        assert "✓" in last


class TestDecomposeTaskSingleLog:
    """decompose_task logs once, not N+1 for children."""

    def test_decompose_logs_once(self, caplog):
        store = TaskStateStore()
        store._enable_trace = True
        root = store.create_task("Root")
        with caplog.at_level(logging.INFO, logger="tinycua.models.task"):
            store.decompose_task(root.task_id, ["Sub1", "Sub2", "Sub3"])
        mutations = [r for r in caplog.records if "task_tree_mutation" in r.message]
        # create_task for Root logs once, then decompose logs once.
        # The 3 child create_task calls should NOT log (suppressed).
        labels = [r.message.split("method=")[1].split()[0] for r in mutations if "method=" in r.message]
        assert "decompose_task" in labels
        # No create_task entries from the children (only from Root if it was
        # created before the caplog context — but Root was created before, so
        # only decompose_task should appear).
        assert "create_task" not in labels


class TestRecordReviewerDecisionLogs:
    """record_reviewer_decision logs after the decision."""

    def test_approved_logs(self, caplog):
        store = TaskStateStore()
        store._enable_trace = True
        root = store.create_task("Root")
        store.record_result(root.task_id, TaskResult(content="done", success=True))
        with caplog.at_level(logging.INFO, logger="tinycua.models.task"):
            store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)
        mutations = [r for r in caplog.records if "task_tree_mutation" in r.message]
        labels = [r.message.split("method=")[1].split()[0] for r in mutations if "method=" in r.message]
        assert "record_reviewer_decision" in labels

    def test_needs_revision_logs(self, caplog):
        store = TaskStateStore()
        store._enable_trace = True
        root = store.create_task("Root")
        store.record_result(root.task_id, TaskResult(content="needs work", success=True))
        with caplog.at_level(logging.INFO, logger="tinycua.models.task"):
            store.record_reviewer_decision(root.task_id, ReviewerDecision.NEEDS_REVISION)
        mutations = [r for r in caplog.records if "task_tree_mutation" in r.message]
        labels = [r.message.split("method=")[1].split()[0] for r in mutations if "method=" in r.message]
        assert "record_reviewer_decision" in labels


class TestReportPrimingRemoved:
    """FR-076: guidance strings do not assume a report deliverable."""

    def test_analyzer_continuation_no_report_md(self):
        from tinycua.loops.task_nodes import _TASK_ANALYZER_CONTINUATION
        lowered = _TASK_ANALYZER_CONTINUATION.lower()
        assert "report.md" not in lowered
        assert "write report" not in lowered
        assert "report file" not in lowered

    def test_executor_work_order_no_report_md(self):
        from tinycua.loops.task_nodes import TinyCUATaskExecutorNode
        from tinycua.config.node_config import create_node_config
        from tinycua.loops.tinycua_loop import TinyCUALoop
        loop = TinyCUALoop()
        node = TinyCUATaskExecutorNode(
            node_id="task_executor",
            config=create_node_config("task_executor"),
        )
        node.ensure_session(loop.root_session)
        continuation = node.build_continuation(loop.root_session)
        assert "report.md" not in continuation

    def test_reviewer_instruction_no_report_md(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_INSTRUCTION
        assert "report.md" not in _RESULT_REVIEWER_INSTRUCTION

    def test_reviewer_continuation_no_report_md(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_CONTINUATION
        assert "report.md" not in _RESULT_REVIEWER_CONTINUATION

    def test_reviewer_tool_guidance_no_report_md(self):
        from tinycua.loops.node_guidance import build_reviewer_tool_guidance
        class _FakeTool:
            def __init__(self, name):
                self.name = name
        tools = [_FakeTool("read_file"), _FakeTool("run_shell"), _FakeTool("task_review_decision")]
        guidance = build_reviewer_tool_guidance(tools)
        assert "report.md" not in guidance
