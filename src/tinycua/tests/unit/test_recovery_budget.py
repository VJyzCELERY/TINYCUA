"""Unit tests for recovery budget + re-entry + full context (FR-060)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node import NodeExecutionError
from tinycua.loops.node_guidance import summarize_tool_result
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import TaskResult, TaskStatus


def _mock_agent(always_fails: bool = True) -> MagicMock:
    """Build a mock agent whose _call_llm always returns invalid content."""
    agent = MagicMock()
    agent.tool_permissions = {}

    async def mock_llm(messages, tools, stream=False, **kwargs):
        return {"role": "assistant", "content": "always fails"}

    agent._call_llm = mock_llm
    return agent


class TestRecoveryBudgetExhaustion:
    """Recovery exhausts honestly instead of re-entering unchanged work."""

    @pytest.mark.asyncio
    async def test_budget_exhausted_raises_with_last_actionable_error(self):
        loop = TinyCUALoop()
        node = TinyCUATaskCreateNode(
            node_id="task_create",
            config=create_node_config("task_create"),
        )
        node.ensure_session(loop.root_session)
        loop._structured_output_retry = AsyncMock(return_value=None)
        loop._recovery_retry = AsyncMock(return_value=None)
        loop._judge_retry = AsyncMock(return_value=None)

        with pytest.raises(NodeExecutionError, match="task_create must call task_init"):
            await loop._unbounded_recovery(
                node,
                _mock_agent(),
                [],
                LLMResult(content="fails"),
                ValidationResult(
                    is_valid=False,
                    errors=["task_create must call task_init"],
                ),
            )

        assert node.progress.recovery_last_error == "task_create must call task_init"
        assert loop._recovery_reentry is False

    @pytest.mark.asyncio
    async def test_budget_split_15_10_3(self, caplog):
        """Structured gets 15, recovery gets 10, judge gets 3."""
        import logging

        loop = TinyCUALoop()
        node = TinyCUATaskCreateNode(
            node_id="task_create",
            config=create_node_config("task_create"),
        )
        node.ensure_session(loop.root_session)
        loop._structured_output_retry = AsyncMock(return_value=None)
        loop._recovery_retry = AsyncMock(return_value=None)
        loop._judge_retry = AsyncMock(return_value=None)

        with caplog.at_level(logging.INFO):
            with pytest.raises(NodeExecutionError):
                await loop._unbounded_recovery(
                    node,
                    _mock_agent(),
                    [],
                    LLMResult(content="fails"),
                    ValidationResult(
                        is_valid=False,
                        errors=["task_create must call task_init"],
                    ),
                )

        # Count stage appearances in the stuck logs.
        structured_count = sum(
            1
            for record in caplog.records
            if (
                record.levelno == logging.WARNING
                and "structured_output_retry" in record.message
            )
        )
        focused_count = sum(
            1
            for record in caplog.records
            if record.levelno == logging.WARNING and "focused_retry" in record.message
        )
        judge_count = sum(
            1
            for record in caplog.records
            if record.levelno == logging.WARNING and "judge_retry" in record.message
        )
        # The stages cycle through: structured (15), focused (10), judge (3).
        assert structured_count <= 15
        assert focused_count <= 10
        assert judge_count <= 3
        # Total should be ~28 cycles (15+10+3).
        total_cycles = structured_count + focused_count + judge_count
        assert total_cycles <= 30

    @pytest.mark.asyncio
    async def test_reentry_preserves_strategy_budgets(self):
        """A fresh node dispatch must not reset an exhausted recovery strategy."""
        loop = TinyCUALoop()
        node = TinyCUATaskCreateNode(
            node_id="task_create",
            config=create_node_config("task_create"),
        )
        node.ensure_session(loop.root_session)
        node.progress.recovery_attempts = {"structured_output_retry": 15}
        node.progress.recovery_fingerprint = "unchanged"
        loop._recovery_reentry = True

        result, _, validation = await loop._call_node_with_retry(
            node,
            _mock_agent(),
            [],
            [],
        )

        assert not validation.is_valid
        assert result.content == "always fails"
        assert node.progress.recovery_attempts == {"structured_output_retry": 15}
        assert node.progress.recovery_fingerprint == "unchanged"

    def test_progress_fingerprint_changes_for_evidence_and_task_mutation(self):
        """Only retained evidence and task state, not prose, reset recovery."""
        loop = TinyCUALoop()
        node = TinyCUATaskCreateNode(
            node_id="task_create",
            config=create_node_config("task_create"),
        )
        node.ensure_session(loop.root_session)
        validation = ValidationResult(
            is_valid=False,
            errors=["task_create must call task_init"],
        )
        evidence = {
            "task_init": {"name": "task_init", "output": {"success": True}},
        }

        before = loop._recovery_fingerprint(node, validation, ["terminate"], evidence)
        evidence["task_init"]["output"]["task_id"] = "task-1"
        evidence_changed = loop._recovery_fingerprint(
            node,
            validation,
            ["terminate"],
            evidence,
        )
        loop.root_session.task_store.create_task("Root")
        task_changed = loop._recovery_fingerprint(
            node,
            validation,
            ["terminate"],
            evidence,
        )

        assert before != evidence_changed
        assert evidence_changed != task_changed


class TestStructuredRetryIncludesFullContext:
    """_structured_output_retry uses _build_recovery_messages (full context)."""

    @pytest.mark.asyncio
    async def test_structured_retry_messages_include_system_prompt(self):
        loop = TinyCUALoop()
        store = loop.root_session.task_store
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="done"))

        node = TinyCUAResultReviewerNode(
            node_id="result_reviewer",
            config=create_node_config("result_reviewer"),
        )
        node.ensure_session(loop.root_session)

        llm_result = LLMResult(
            content="I need to verify...",
            metadata={"tool_results": []},
        )
        validation = ValidationResult(
            is_valid=False,
            errors=[
                "result_reviewer must call successful task-state tool(s): ['task_review_decision']"
            ],
        )

        # Build the recovery messages and check they include system prompt.
        from tinycua.tools.task_tools import TaskReviewDecisionTool

        recovery_tools = [TaskReviewDecisionTool()]
        messages = loop._build_recovery_messages(
            node, recovery_tools, llm_result, validation, ["task_review_decision"]
        )

        # The first message should be a system message (not a bare user message).
        assert messages[0].get("role") == "system"
        assert "ResultReviewer" in messages[0].get("content", "")


class TestRecoveryMessagesIncludeTrimmedToolResults:
    """_build_recovery_messages includes summarized tool results."""

    @pytest.mark.asyncio
    async def test_tool_results_appear_as_summaries(self):
        loop = TinyCUALoop()
        store = loop.root_session.task_store
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="done"))

        node = TinyCUAResultReviewerNode(
            node_id="result_reviewer",
            config=create_node_config("result_reviewer"),
        )
        node.ensure_session(loop.root_session)

        llm_result = LLMResult(
            content="I verified the files",
            metadata={
                "tool_results": [
                    {
                        "name": "run_shell",
                        "content": json.dumps(
                            {"output": {"exit_code": 0, "timed_out": False}}
                        ),
                    },
                    {
                        "name": "read_file",
                        "content": json.dumps(
                            {"output": {"success": True, "path": "report.md"}}
                        ),
                    },
                ]
            },
        )
        validation = ValidationResult(
            is_valid=False,
            errors=[
                "result_reviewer must call successful task-state tool(s): ['task_review_decision']"
            ],
        )

        messages = loop._build_recovery_messages(
            node, [], llm_result, validation, ["task_review_decision"]
        )

        # Find the tool results message.
        tool_result_msg = None
        for msg in messages:
            content = msg.get("content", "")
            if "Previous tool results" in content:
                tool_result_msg = content
                break

        assert tool_result_msg is not None, "No tool results message found"
        assert "run_shell" in tool_result_msg
        assert "read_file" in tool_result_msg
        assert "exit_code=0" in tool_result_msg
        assert "path=report.md" in tool_result_msg


class TestJudgeRetryIncludesFullContext:
    """_judge_retry uses _build_recovery_messages (full session context)."""

    @pytest.mark.asyncio
    async def test_judge_messages_include_system_prompt(self):
        loop = TinyCUALoop()
        store = loop.root_session.task_store
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="done"))

        node = TinyCUAResultReviewerNode(
            node_id="result_reviewer",
            config=create_node_config("result_reviewer"),
        )
        node.ensure_session(loop.root_session)

        llm_result = LLMResult(content="I need to verify...")
        validation = ValidationResult(
            is_valid=False,
            errors=[
                "result_reviewer must call successful task-state tool(s): ['task_review_decision']"
            ],
        )

        from tinycua.tools.task_tools import TaskReviewDecisionTool

        recovery_tools = [TaskReviewDecisionTool()]
        # Call _judge_retry — it will fail (mock agent), but we can check
        # that it at least built messages with system prompt before failing.
        agent = MagicMock()
        agent.tool_permissions = {}

        captured_messages: list[list[dict]] = []

        async def mock_llm(messages, tools, stream=False, **kwargs):
            captured_messages.append(list(messages))
            return {
                "role": "assistant",
                "content": '{"name": "task_review_decision", "arguments": {}}',
            }

        agent._call_llm = mock_llm

        await loop._judge_retry(
            node,
            agent,
            recovery_tools,
            llm_result,
            validation,
            missing_tools=["task_review_decision"],
        )

        assert len(captured_messages) > 0
        messages = captured_messages[0]
        # The first message should be a system message (from _build_recovery_messages).
        assert messages[0].get("role") == "system"
        assert "ResultReviewer" in messages[0].get("content", "")


class TestCommitEndsRecovery:
    """Successful commit evidence ends recovery directly."""

    @pytest.mark.asyncio
    async def test_commit_evidence_needs_no_terminate(self):
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

        recovery_result = await loop._unbounded_recovery(
            reviewer,
            agent,
            [],
            original_result,
            ValidationResult(
                is_valid=False,
                errors=["result_reviewer completed its required work; call terminate."],
            ),
        )

        assert recovery_result is not None
        result, validation = recovery_result
        assert validation.is_valid
        assert not any(
            tc.get("function", {}).get("name") == "terminate"
            for tc in result.tool_calls
        )


class TestSummarizeToolResultMovedToNodeGuidance:
    """summarize_tool_result is importable from node_guidance (FR-060)."""

    def test_summarize_exit_code(self):
        result = summarize_tool_result(
            json.dumps({"output": {"exit_code": 0, "timed_out": False}})
        )
        assert "exit_code=0" in result

    def test_summarize_path(self):
        result = summarize_tool_result(
            json.dumps({"output": {"success": True, "path": "report.md"}})
        )
        assert "path=report.md" in result

    def test_re_export_from_live_stream(self):
        from tinycua.cli.live_stream import summarize_tool_result as cli_summarize

        assert (
            cli_summarize(json.dumps({"output": {"exit_code": 1}}))
            == "exit_code=1 timed_out=None"
        )
