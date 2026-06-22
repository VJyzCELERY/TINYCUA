"""Tests for the unbounded recovery loop and LLM judge stage.

Covers:
- _parse_judge_tool_call: JSON parsing of judge output
- _judge_retry: LLM judge injects a tool call when the model is stuck
- _unbounded_recovery: cycles through focused → tightening → judge stages
- on_complete fires after recovery (queue integrity invariant)
- OPEN_QUESTION disabled: schedule_after_review doesn't route to ResponseNode
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.recovery_stages_mixin import RecoveryStagesMixin
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import ReviewerDecision, TaskResult
from tinycua.tools.task_tools import TerminateTool


class TestParseJudgeToolCall:
    """Tests for _parse_judge_tool_call static method."""

    def test_clean_json(self) -> None:
        """Clean JSON with correct name parses successfully."""
        raw = '{"name": "task_inspect", "arguments": {}}'
        result = RecoveryStagesMixin._parse_judge_tool_call(raw, "task_inspect")
        assert result is not None
        assert result["function"]["name"] == "task_inspect"
        assert json.loads(result["function"]["arguments"]) == {}

    def test_markdown_fenced_json(self) -> None:
        """Markdown-fenced JSON parses successfully."""
        raw = '```json\n{"name": "task_inspect", "arguments": {"task_id": "5"}}\n```'
        result = RecoveryStagesMixin._parse_judge_tool_call(raw, "task_inspect")
        assert result is not None
        args = json.loads(result["function"]["arguments"])
        assert args["task_id"] == "5"

    def test_wrong_name_rejected(self) -> None:
        """JSON with wrong tool name is rejected."""
        raw = '{"name": "terminate", "arguments": {}}'
        result = RecoveryStagesMixin._parse_judge_tool_call(raw, "task_inspect")
        assert result is None

    def test_invalid_json_rejected(self) -> None:
        """Non-JSON text is rejected."""
        result = RecoveryStagesMixin._parse_judge_tool_call("not json", "task_inspect")
        assert result is None

    def test_json_embedded_in_prose(self) -> None:
        """JSON embedded in prose is extracted."""
        raw = 'Here is the call: {"name": "terminate", "arguments": {}} done.'
        result = RecoveryStagesMixin._parse_judge_tool_call(raw, "terminate")
        assert result is not None
        assert result["function"]["name"] == "terminate"

    def test_missing_braces_rejected(self) -> None:
        """Text without JSON braces is rejected."""
        result = RecoveryStagesMixin._parse_judge_tool_call("no braces here", "terminate")
        assert result is None


class TestUnboundedRecovery:
    """Tests for the _unbounded_recovery loop."""

    @pytest.mark.asyncio
    async def test_recovery_succeeds_on_focused_retry(self) -> None:
        """The unbounded loop exits when focused retry produces valid output."""
        loop = TinyCUALoop()
        node = TinyCUATaskCreateNode(
            node_id="task_create",
            config=create_node_config("task_create"),
        )
        node.ensure_session(loop.root_session)

        agent = MagicMock()
        agent.tool_permissions = {}
        call_count = 0

        async def mock_llm(messages, tools, stream=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Focused retry succeeds — return task_init + terminate.
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "task_init",
                                "arguments": '{"title":"test task"}',
                            },
                        },
                        {
                            "type": "function",
                            "function": {
                                "name": "terminate",
                                "arguments": "{}",
                            },
                        },
                    ],
                }
            return {"role": "assistant", "content": "fallback"}

        agent._call_llm = mock_llm

        # Provide task_init + terminate tools so they can execute.
        from tinycua.tools.task_tools import TaskInitTool, TerminateTool
        task_init_tool = TaskInitTool()
        task_init_tool.bind_task_store(loop.root_session.task_store)
        terminate_tool = TerminateTool()

        result, validation = await loop._unbounded_recovery(
            node,
            agent,
            [task_init_tool, terminate_tool],
            LLMResult(content="planner-only response"),
            ValidationResult(
                is_valid=False,
                errors=["task_create must call task_init"],
            ),
        )

        assert validation.is_valid

    @pytest.mark.asyncio
    async def test_recovery_logs_state_on_cycle_failure(self) -> None:
        """The recovery loop logs system state and signals re-entry after budget exhaustion.

        FR-060: the loop is no longer truly unbounded — it has a per-method
        budget (15/10/3 = 30 total). When all budgets are exhausted, it returns
        None to signal node re-entry. This test verifies the re-entry signal.
        """
        loop = TinyCUALoop()
        node = TinyCUATaskCreateNode(
            node_id="task_create",
            config=create_node_config("task_create"),
        )
        node.ensure_session(loop.root_session)

        agent = MagicMock()
        agent.tool_permissions = {}

        async def mock_llm(messages, tools, stream=False):
            import asyncio as _asyncio
            await _asyncio.sleep(0)  # yield to event loop so timeout can fire
            return {"role": "assistant", "content": "always fails"}

        agent._call_llm = mock_llm

        # FR-060: after 30 cycles (15+10+3), the loop returns None (re-entry).
        result = await loop._unbounded_recovery(
            node,
            agent,
            [],
            LLMResult(content="fails"),
            ValidationResult(
                is_valid=False,
                errors=["task_create must call task_init"],
            ),
        )
        assert result is None  # re-entry signal
        assert loop._recovery_reentry is True


class TestOnCompleteFiresAfterRecovery:
    """Tests that on_complete fires after recovery, enqueuing next nodes."""

    @pytest.mark.asyncio
    async def test_direct_terminate_when_only_missing(self) -> None:
        """When terminate is the only missing prerequisite, call it directly.

        terminate has no meaningful parameters — there is nothing for the
        model to decide. The recovery loop calls it without an LLM round-trip.
        """
        loop = TinyCUALoop()
        task = loop.root_session.task_store.create_task("test task")
        loop.root_session.task_store.record_result(
            task.task_id,
            TaskResult(content="done", success=True),
        )
        loop.root_session.task_store.active_task_id = task.task_id

        reviewer = TinyCUAResultReviewerNode(
            node_id="result_reviewer",
            config=create_node_config("result_reviewer"),
        )
        reviewer.ensure_session(loop.root_session)

        agent = MagicMock()
        agent.tool_permissions = {}

        # The original result already has task_review_decision + task_inspect
        # successful — only terminate is missing.
        original_result = LLMResult(
            content="reviewed",
            metadata={
                "tool_results": [
                    {
                        "name": "task_review_decision",
                        "allowed": True,
                        "output": {
                            "success": True,
                            "decision": "approved",
                            "task_id": task.task_id,
                        },
                    },
                    {
                        "name": "task_inspect",
                        "allowed": True,
                        "output": {"success": True},
                    },
                ]
            },
        )

        result, validation = await loop._unbounded_recovery(
            reviewer,
            agent,
            [],
            original_result,
            ValidationResult(
                is_valid=False,
                errors=["result_reviewer completed its required work; call terminate."],
            ),
        )

        # The direct terminate shortcut should have fired — no LLM call needed.
        assert validation.is_valid
        assert any(
            tc.get("function", {}).get("name") == "terminate"
            for tc in result.tool_calls
        )

    @pytest.mark.asyncio
    async def test_reviewer_on_complete_enqueues_next_after_recovery(self) -> None:
        """After recovery, the reviewer's on_complete enqueues executor+reviewer."""
        loop = TinyCUALoop()
        # Set up a task with a result that needs review.
        task = loop.root_session.task_store.create_task("test task")
        loop.root_session.task_store.record_result(
            task.task_id,
            TaskResult(content="done", success=True),
        )
        loop.root_session.task_store.active_task_id = task.task_id

        reviewer = TinyCUAResultReviewerNode(
            node_id="result_reviewer",
            config=create_node_config("result_reviewer"),
        )
        reviewer.ensure_session(loop.root_session)
        loop.queue = NodeQueue(items=[reviewer])

        agent = MagicMock()
        agent.tool_permissions = {}
        call_count = 0

        async def mock_llm(messages, tools, stream=False):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Fail: call task_review_decision but not task_inspect.
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "task_review_decision",
                                "arguments": json.dumps(
                                    {
                                        "task_id": task.task_id,
                                        "decision": "approved",
                                        "rationale": "looks good",
                                    }
                                ),
                            },
                        }
                    ],
                }
            # Recovery retry: call task_inspect then terminate.
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "task_inspect",
                            "arguments": "{}",
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "terminate",
                            "arguments": "{}",
                        },
                    },
                ],
            }

        agent._call_llm = mock_llm

        from tinycua.tools.task_tools import (
            TaskInspectTool,
            TaskReviewDecisionTool,
            TaskUpdateTool,
        )
        review_tool = TaskReviewDecisionTool()
        review_tool.bind_task_store(loop.root_session.task_store)
        inspect_tool = TaskInspectTool()
        inspect_tool.bind_task_store(loop.root_session.task_store)
        update_tool = TaskUpdateTool()
        update_tool.bind_task_store(loop.root_session.task_store)
        terminate_tool = TerminateTool()

        async for _event in loop._stream_node_events(
            reviewer,
            agent,
            [review_tool, inspect_tool, update_tool, terminate_tool],
            None,
            loop.queue.input_for_current(),
        ):
            pass

        # on_complete should have fired, enqueuing the next nodes.
        queue_ids = [n.node_id for n in loop.queue.items]
        # The task was approved → schedule_after_review → schedule_next →
        # all_done() is true → result_aggregation enqueued.
        assert "result_aggregation" in queue_ids


class TestOpenQuestionDisabled:
    """Tests that OPEN_QUESTION is configurable and disabled by default."""

    def test_open_question_present_in_enum_but_disabled_by_default(self) -> None:
        """OPEN_QUESTION is in the enum (configurable) but disabled by default."""
        values = [d.value for d in ReviewerDecision]
        assert "open_question" in values
        assert "approved" in values
        assert "needs_revision" in values
        assert "rejected" in values
        assert "replan" in values
        # Disabled by default in SessionConfig
        from tinycua.config.session_config import SessionConfig

        assert SessionConfig().enable_open_question_review is False

    def test_schedule_after_review_does_not_route_to_response_for_open_question(self) -> None:
        """schedule_after_review falls through to schedule_next when flag disabled."""
        from tinycua.loops.worker_runtime import WorkerRuntimeController

        loop = TinyCUALoop()
        task = loop.root_session.task_store.create_task("test")
        loop.root_session.task_store.active_task_id = task.task_id

        # With the flag disabled (default), an open_question decision should
        # fall through to schedule_next — not route to ResponseNode.
        task.reviewer_decisions.append({"decision": "open_question"})
        queue = NodeQueue(items=[])
        WorkerRuntimeController(
            loop.root_session.task_store,
            enable_open_question_review=False,
        ).schedule_after_review(queue)

        # Should not contain a response node — should fall through to schedule_next.
        assert not any(n.node_id == "response" for n in queue.items)
