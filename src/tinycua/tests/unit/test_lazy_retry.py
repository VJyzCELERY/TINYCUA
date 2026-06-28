"""Unit tests for _maybe_lazy_recovery (FR-087..FR-093).

Covers: success path, garbage markdown, unresolvable task_id, tool-exec error,
gate-off (standard mode), non-state-tool validation failure, no-template node,
budget cap, and the None-doesn't-burn-slot rule.

Written BEFORE implementation (TDD RED phase). The method does not exist yet.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode, TinyCUATaskExecutorNode
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import TaskResult, TaskStatus
from tinycua.tools.task_tools import TaskResultUpdateTool, TaskReviewDecisionTool


def _set_lazy_mode(loop: TinyCUALoop, mode: str = "markdown_synthesis") -> None:
    """Enable markdown_synthesis mode on the loop's session config."""
    loop.session_config = SessionConfig(recovery_strategy=mode)


def _make_agent(llm_response: dict[str, Any] | None = None) -> MagicMock:
    """Build a mock agent whose _call_llm returns the given response dict."""
    agent = MagicMock()
    agent.tool_permissions = {}
    response = llm_response if llm_response is not None else {
        "role": "assistant",
        "content": "",
    }

    async def mock_llm(messages, tools, stream=False, **kwargs):  # noqa: ARG001
        return response

    agent._call_llm = mock_llm
    return agent


def _reviewer_valid_markdown(task_id: str) -> str:
    return (
        "# Review Assessment : approved\n"
        "# Review Summary\n"
        "The evidence confirms the task is done.\n"
        "# Task ID\n"
        f"{task_id}\n"
    )


def _executor_valid_markdown(task_id: str) -> str:
    return (
        "# Status : completed\n"
        "# Summary\n"
        "Implemented and verified the feature.\n"
        "# Task ID\n"
        f"{task_id}\n"
    )


class TestLazyRetrySuccess:
    """Valid markdown → synthesized tool call → passes validation → returns result."""

    @pytest.mark.asyncio
    async def test_reviewer_lazy_succeeds(self):
        loop = TinyCUALoop()
        _set_lazy_mode(loop)
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

        agent = _make_agent({"role": "assistant", "content": _reviewer_valid_markdown(child.task_id)})
        last_result = LLMResult(content="reviewing", metadata={"tool_results": []})
        validation = ValidationResult(
            is_valid=False,
            errors=["result_reviewer must call successful task-state tool(s): ['task_review_decision']"],
        )
        tool = TaskReviewDecisionTool()

        result = await loop._maybe_lazy_recovery(
            node, agent, [tool], last_result, validation,
        )
        assert result is not None
        lazy_result, lazy_validation = result
        # Lazy returns a partial result: the state tool was synthesized and
        # executed successfully, but terminate may still be missing (standard
        # recovery handles that after the caller accumulates this result).
        tool_results = lazy_result.metadata.get("tool_results", [])
        names = {tr.get("name") for tr in tool_results if isinstance(tr, dict)}
        assert "task_review_decision" in names
        successful = {
            tr.get("name") for tr in tool_results
            if isinstance(tr, dict) and isinstance(tr.get("output"), dict) and tr["output"].get("success")
        }
        assert "task_review_decision" in successful

    @pytest.mark.asyncio
    async def test_executor_lazy_succeeds(self):
        loop = TinyCUALoop()
        _set_lazy_mode(loop)
        store = loop.root_session.task_store

        root = store.create_task("Build feature")
        store.active_task_id = root.task_id
        store.transition(root.task_id, TaskStatus.IN_PROGRESS)

        node = TinyCUATaskExecutorNode(
            node_id="task_executor",
            config=create_node_config("task_executor"),
        )
        node.ensure_session(loop.root_session)

        agent = _make_agent({"role": "assistant", "content": _executor_valid_markdown(root.task_id)})
        last_result = LLMResult(content="working", metadata={"tool_results": []})
        validation = ValidationResult(
            is_valid=False,
            errors=["TaskExecutor must call task_result_update with an outcome report"],
        )
        tool = TaskResultUpdateTool()

        result = await loop._maybe_lazy_recovery(
            node, agent, [tool], last_result, validation,
        )
        assert result is not None
        lazy_result, lazy_validation = result
        # Lazy returns a partial result: task_result_update was synthesized,
        # but terminate may still be missing (standard recovery handles it).
        tool_results = lazy_result.metadata.get("tool_results", [])
        successful = {
            tr.get("name") for tr in tool_results
            if isinstance(tr, dict) and isinstance(tr.get("output"), dict) and tr["output"].get("success")
        }
        assert "task_result_update" in successful


class TestLazyRetryGarbageMarkdown:
    """Garbage markdown → returns None (falls back to standard)."""

    @pytest.mark.asyncio
    async def test_garbage_returns_none(self):
        loop = TinyCUALoop()
        _set_lazy_mode(loop)
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

        agent = _make_agent({"role": "assistant", "content": "I don't understand the template."})
        last_result = LLMResult(content="reviewing", metadata={"tool_results": []})
        validation = ValidationResult(
            is_valid=False,
            errors=["result_reviewer must call successful task-state tool(s): ['task_review_decision']"],
        )

        result = await loop._maybe_lazy_recovery(
            node, agent, [TaskReviewDecisionTool()], last_result, validation,
        )
        assert result is None


class TestUnresolvableTaskId:
    """Markdown valid but task_id doesn't exist → returns None."""

    @pytest.mark.asyncio
    async def test_unknown_task_id_returns_none(self):
        loop = TinyCUALoop()
        _set_lazy_mode(loop)
        store = loop.root_session.task_store
        # All tasks completed → active_task_id is None (no unfinished leaf).
        # A bad UUID then cannot resolve via active fallback or roadmap number.
        root = store.create_task("Root")
        child = store.create_task("Child", parent_id=root.task_id)
        store.transition(child.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(child.task_id, TaskResult(content="done"))
        store.transition(child.task_id, TaskStatus.COMPLETED)
        # Complete the root too so _refresh_active_task leaves active=None.
        store.transition(root.task_id, TaskStatus.IN_PROGRESS)
        store.record_result(root.task_id, TaskResult(content="root done"))
        store.transition(root.task_id, TaskStatus.COMPLETED)
        assert store.active_task_id is None

        node = TinyCUAResultReviewerNode(
            node_id="result_reviewer",
            config=create_node_config("result_reviewer"),
        )
        node.ensure_session(loop.root_session)

        bad_md = _reviewer_valid_markdown("nonexistent-uuid")
        agent = _make_agent({"role": "assistant", "content": bad_md})
        last_result = LLMResult(content="reviewing", metadata={"tool_results": []})
        validation = ValidationResult(
            is_valid=False,
            errors=["result_reviewer must call successful task-state tool(s): ['task_review_decision']"],
        )

        result = await loop._maybe_lazy_recovery(
            node, agent, [TaskReviewDecisionTool()], last_result, validation,
        )
        assert result is None


class TestToolExecError:
    """Tool execution raises → returns None."""

    @pytest.mark.asyncio
    async def test_tool_exec_error_returns_none(self, monkeypatch):
        loop = TinyCUALoop()
        _set_lazy_mode(loop)
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

        agent = _make_agent({"role": "assistant", "content": _reviewer_valid_markdown(child.task_id)})

        # Force _execute_tool_calls to raise.
        async def boom(*args, **kwargs):  # noqa: ARG001
            raise RuntimeError("exec failed")
        monkeypatch.setattr(loop, "_execute_tool_calls", boom)

        last_result = LLMResult(content="reviewing", metadata={"tool_results": []})
        validation = ValidationResult(
            is_valid=False,
            errors=["result_reviewer must call successful task-state tool(s): ['task_review_decision']"],
        )

        result = await loop._maybe_lazy_recovery(
            node, agent, [TaskReviewDecisionTool()], last_result, validation,
        )
        assert result is None


class TestGateStandardMode:
    """recovery_strategy='standard' → _maybe_lazy_recovery returns None without LLM call."""

    @pytest.mark.asyncio
    async def test_standard_mode_skips_llm_call(self):
        loop = TinyCUALoop()
        # Default mode is standard — TinyCUALoop() leaves session_config None,
        # which the gate treats as "standard". Set it explicitly to be safe.
        loop.session_config = SessionConfig(recovery_strategy="standard")
        assert loop.session_config.recovery_strategy == "standard"

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

        call_count = 0

        def mock_llm(messages, tools, stream=False, **kwargs):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            return {"role": "assistant", "content": _reviewer_valid_markdown(child.task_id)}

        agent = MagicMock()
        agent.tool_permissions = {}
        agent._call_llm = mock_llm

        last_result = LLMResult(content="reviewing", metadata={"tool_results": []})
        validation = ValidationResult(
            is_valid=False,
            errors=["result_reviewer must call successful task-state tool(s): ['task_review_decision']"],
        )

        result = await loop._maybe_lazy_recovery(
            node, agent, [TaskReviewDecisionTool()], last_result, validation,
        )
        assert result is None
        assert call_count == 0, "LLM must not be called in standard mode"


class TestGateNonStateToolOrNonLazyNode:
    """Validation failure on a non-lazy node (response) → returns None even in lazy mode."""

    @pytest.mark.asyncio
    async def test_response_node_skips_lazy(self):
        from tinycua.loops.response_node import ResponseNode

        loop = TinyCUALoop()
        _set_lazy_mode(loop)

        node = ResponseNode(config=create_node_config("response"))
        node.ensure_session(loop.root_session)

        call_count = 0

        def mock_llm(messages, tools, stream=False, **kwargs):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            return {"role": "assistant", "content": "anything"}

        agent = MagicMock()
        agent.tool_permissions = {}
        agent._call_llm = mock_llm

        last_result = LLMResult(content="", metadata={"tool_results": []})
        # Non-state-tool validation error: empty final response.
        validation = ValidationResult(
            is_valid=False,
            errors=["Final response must be non-empty."],
        )

        result = await loop._maybe_lazy_recovery(
            node, agent, [], last_result, validation,
        )
        assert result is None
        assert call_count == 0


class TestGateNoTemplateNode:
    """task_analyzer has no v1 template → returns None even in lazy mode."""

    @pytest.mark.asyncio
    async def test_task_analyzer_no_template(self):
        from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode

        loop = TinyCUALoop()
        _set_lazy_mode(loop)

        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)

        call_count = 0

        def mock_llm(messages, tools, stream=False, **kwargs):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            return {"role": "assistant", "content": "x"}

        agent = MagicMock()
        agent.tool_permissions = {}
        agent._call_llm = mock_llm

        last_result = LLMResult(content="analyzing", metadata={"tool_results": []})
        validation = ValidationResult(
            is_valid=False,
            errors=["task_analyzer must call task_decompose or task_update"],
        )

        result = await loop._maybe_lazy_recovery(
            node, agent, [], last_result, validation,
        )
        assert result is None
        assert call_count == 0


class TestLazyDoesNotBurnSlot:
    """Empty LLM response → parse fails → returns None before counting lazy_attempts.

    This is tested at the _maybe_lazy_recovery level. The wire-in site in
    _call_node_with_retry tracks lazy_attempts and only increments after a
    non-None return. We assert the method itself returns None on empty content.
    """

    @pytest.mark.asyncio
    async def test_empty_llm_response_returns_none(self):
        loop = TinyCUALoop()
        _set_lazy_mode(loop)
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

        agent = _make_agent({"role": "assistant", "content": ""})
        last_result = LLMResult(content="reviewing", metadata={"tool_results": []})
        validation = ValidationResult(
            is_valid=False,
            errors=["result_reviewer must call successful task-state tool(s): ['task_review_decision']"],
        )

        result = await loop._maybe_lazy_recovery(
            node, agent, [TaskReviewDecisionTool()], last_result, validation,
        )
        assert result is None