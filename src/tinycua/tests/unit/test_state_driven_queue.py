"""Tests for Phase A-E: state-driven queue, multi-task reporting, tool fixes (FR-067..FR-074)."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any
from unittest.mock import MagicMock

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.loops.worker_runtime import WorkerRuntimeController
from tinycua.models.task import ReviewerDecision, TaskResult, TaskStateStore, TaskStatus


class TestStateDrivenQueue:
    """FR-067: queue is state-driven, not static."""

    def test_no_result_spawns_executor_and_reviewer(self):
        """Task with no result → [executor, reviewer]."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        queue = NodeQueue()
        WorkerRuntimeController(store).schedule_next(queue)
        ids = [n.node_id for n in queue.items]
        assert ids == ["task_executor", "result_reviewer"]

    def test_result_no_review_spawns_reviewer_only(self):
        """Task with result, no negative review → [reviewer] only (skip executor)."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="done", success=True))
        queue = NodeQueue()
        WorkerRuntimeController(store).schedule_next(queue)
        ids = [n.node_id for n in queue.items]
        assert ids == ["result_reviewer"]

    def test_result_with_needs_revision_spawns_executor_and_reviewer(self):
        """Task with result + needs_revision → [executor, reviewer] (rework)."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="done", success=True))
        store.record_reviewer_decision(child.task_id, ReviewerDecision.NEEDS_REVISION)
        queue = NodeQueue()
        WorkerRuntimeController(store).schedule_next(queue)
        ids = [n.node_id for n in queue.items]
        assert ids == ["task_executor", "result_reviewer"]

    def test_failed_result_spawns_executor_and_reviewer(self):
        """Task with failed result → [executor, reviewer] (retry)."""
        store = TaskStateStore()
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.record_result(child.task_id, TaskResult(content="failed", success=False))
        store.record_reviewer_decision(child.task_id, ReviewerDecision.APPROVED)
        queue = NodeQueue()
        WorkerRuntimeController(store).schedule_next(queue)
        ids = [n.node_id for n in queue.items]
        assert ids == ["task_executor", "result_reviewer"]

    def test_all_done_spawns_aggregation(self):
        """All tasks done → [result_aggregation]."""
        store = TaskStateStore()
        root = store.create_task("Root")
        store.record_result(root.task_id, TaskResult(content="done", success=True))
        store.record_reviewer_decision(root.task_id, ReviewerDecision.APPROVED)
        queue = NodeQueue()
        WorkerRuntimeController(store).schedule_next(queue)
        ids = [n.node_id for n in queue.items]
        assert ids == ["result_aggregation"]

    def test_executor_reports_sibling_result_skips_executor(self):
        """When executor reports results for siblings, siblings skip executor."""
        store = TaskStateStore()
        root = store.create_task("Root")
        first = store.create_task("First", parent_id=root.task_id)
        second = store.create_task("Second", parent_id=root.task_id)
        # Executor completes first AND reports result for second.
        store.record_result(first.task_id, TaskResult(content="did both", success=True))
        store.record_result(second.task_id, TaskResult(content="completed as part of task 1", success=True))
        # Reviewer approves first → active moves to second.
        store.record_reviewer_decision(first.task_id, ReviewerDecision.APPROVED)
        # Now second is active and has a result → schedule_next should spawn [reviewer] only.
        queue = NodeQueue()
        WorkerRuntimeController(store).schedule_next(queue)
        ids = [n.node_id for n in queue.items]
        assert ids == ["result_reviewer"]  # no executor — work already done


class TestReviewerTestingGuidance:
    """FR-070: reviewer instruction tells the model to test the result."""

    def test_instruction_says_test_the_result(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_INSTRUCTION
        assert "test the result" in _RESULT_REVIEWER_INSTRUCTION.lower()

    def test_instruction_allows_re_running_code(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_INSTRUCTION
        assert "verification" in _RESULT_REVIEWER_INSTRUCTION.lower()
        assert "re-execution" in _RESULT_REVIEWER_INSTRUCTION.lower()

    def test_instruction_mentions_sibling_propagation(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_INSTRUCTION
        assert "sibling" in _RESULT_REVIEWER_INSTRUCTION.lower()
        assert "satisfies sibling tasks" in _RESULT_REVIEWER_INSTRUCTION.lower()

    def test_continuation_mentions_python_import_check(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_CONTINUATION
        assert "python -c" in _RESULT_REVIEWER_CONTINUATION.lower()

    def test_continuation_mentions_tab_corruption_check(self):
        from tinycua.loops.node_guidance import _RESULT_REVIEWER_CONTINUATION
        assert "grep" in _RESULT_REVIEWER_CONTINUATION.lower()
        assert "tab" in _RESULT_REVIEWER_CONTINUATION.lower()

    def test_tool_guidance_says_testf_not_sufficient(self):
        from tinycua.loops.node_guidance import build_reviewer_tool_guidance
        class _FakeTool:
            def __init__(self, name):
                self.name = name
        tools = [_FakeTool("read_file"), _FakeTool("run_shell"), _FakeTool("task_review_decision")]
        guidance = build_reviewer_tool_guidance(tools)
        assert "not sufficient" in guidance.lower()
        assert "actually works" in guidance.lower() or "functional" in guidance.lower()


class TestTaskResultUpdateClarity:
    """FR-071: tool description + retry message mention success=true/false."""

    def test_tool_description_mentions_success_true(self):
        from tinycua.tools.task_tools import TaskResultUpdateTool
        tool = TaskResultUpdateTool()
        assert "success=true" in tool.description.lower()
        assert "success=false" in tool.description.lower()

    def test_retry_message_mentions_success_true(self):
        from tinycua.loops.validation_retry_mixin import ValidationRetryMixin
        from tinycua.loops.task_nodes import TinyCUATaskExecutorNode
        loop = TinyCUALoop()
        node = TinyCUATaskExecutorNode(
            node_id="task_executor",
            config=create_node_config("task_executor"),
        )
        node.ensure_session(loop.root_session)
        from tinycua.config.types import ValidationError
        error = ValidationError("task_executor must call task_result_update")
        llm_result = LLMResult(content="", metadata={"tool_results": []})
        msg = loop._retry_message_for_validation(error, node, [], llm_result)
        assert "success=true" in msg.lower()


class TestFetchUrlEmptyBody:
    """FR-072: fetch_url returns failure for empty body."""

    def test_empty_html_body_returns_failure(self):
        """Empty HTML body → success=false with diagnostic error."""
        try:
            import httpx
            from pytest_httpx import HTTPXMock
        except ImportError:
            pytest.skip("httpx not available")
        # We test _process_response directly to avoid network calls.
        from tinycua.agent.tools.native.web import _process_response

        class _FakeResponse:
            status_code = 200
            reason_phrase = "OK"
            text = ""
            content = b""
            headers = {"content-type": "text/html"}

        result = _process_response(_FakeResponse(), 100000, "https://example.com/empty")
        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_nonempty_body_returns_success(self):
        """Non-empty HTML body → success=true."""
        from tinycua.agent.tools.native.web import _process_response

        class _FakeResponse:
            status_code = 200
            reason_phrase = "OK"
            text = "<html><body>Hello</body></html>"
            content = b"<html><body>Hello</body></html>"
            headers = {"content-type": "text/html"}

        result = _process_response(_FakeResponse(), 100000, "https://example.com/ok")
        assert result["success"] is True
        assert "Hello" in result["content"]


class TestResponseNoDuplication:
    """FR-074: response output is not duplicated."""

    def test_record_node_output_clear_prior(self):
        """clear_prior=True removes prior output entries from the same node."""
        loop = TinyCUALoop()
        from tinycua.loops.response_node import ResponseNode

        node = ResponseNode(
            node_id="response",
            config=create_node_config("response"),
        )
        node.ensure_session(loop.root_session)

        # Record output once.
        loop._record_node_output(node, "first output")
        # Record again with clear_prior=True.
        loop._record_node_output(node, "second output", clear_prior=True)

        # Should have only ONE output entry from this node, not two.
        # Output is recorded on node.session (child session), not root.
        output_entries = [
            e for e in node.session.session_context
            if getattr(e, "segment", None) == "output"
            and getattr(e, "source_node_id", None) == "response"
        ]
        assert len(output_entries) == 1
        assert output_entries[0].content == "second output"
