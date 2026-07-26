"""Phase 0 tests: recovery stages return partial results (FR-063).

When a recovery stage injects a tool call that succeeds but validation
still fails (e.g. task_decompose succeeded but terminate is still missing),
the stage MUST return the partial result — not None. The orchestration loop
accumulates the successful tool call and advances to the next missing
prerequisite. Previously, returning None discarded the successful call and
the loop retried the same tool forever (experiment-2: 23 cycles, pending
5→50, never terminated).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.loops.node_contract import LifecyclePhase
from tinycua.loops.task_nodes import TinyCUATaskAnalyzerNode, TinyCUATaskExecutorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.task import TaskResult
from tinycua.tools.task_tools import (
    TaskDecomposeTool,
    TaskInspectTool,
    TaskResultUpdateTool,
    TerminateTool,
)


def test_lifecycle_phase_scope_is_exclusive() -> None:
    """ACTION includes direct commit while fallback COMMIT stays exclusive."""
    loop = TinyCUALoop()
    node = TinyCUATaskExecutorNode(
        node_id="task_executor",
        config=create_node_config("task_executor"),
    )
    tools = [TaskInspectTool(), TaskResultUpdateTool(), TerminateTool()]

    assert [
        tool.name for tool in loop._phase_tools(node, tools, LifecyclePhase.ACTION)
    ] == [
        "task_inspect",
        "task_result_update",
    ]
    assert [
        tool.name for tool in loop._phase_tools(node, tools, LifecyclePhase.COMMIT)
    ] == [
        "task_result_update",
    ]
    task = loop.root_session.task_store.create_task("Active")
    loop.root_session.task_store.record_result(task.task_id, TaskResult(content="done"))
    node.progress.satisfied_requirements.add("task_result_update")
    assert [
        tool.name for tool in loop._phase_tools(node, tools, LifecyclePhase.TERMINATE)
    ] == [
        "task_inspect",
        "task_result_update",
        "terminate",
    ]


class TestRecoveryRetryReturnsPartialResult:
    """_recovery_retry returns (result, validation) even when validation fails."""

    @pytest.mark.asyncio
    async def test_commit_result_is_valid_without_terminate(self):
        """A successful task mutation finishes recovery without terminate."""
        loop = TinyCUALoop()
        store = loop.root_session.task_store

        # Create root task with no children (so task_decompose is needed).
        root = store.create_task("Research frontier LLMs")
        store.active_task_id = root.task_id

        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)

        # Mock agent: _call_llm returns a task_decompose tool call.
        agent = MagicMock()
        agent.tool_permissions = {}

        async def mock_llm(messages, tools, stream=False, **kwargs):
            return {
                "role": "assistant",
                "content": "Decomposing the task",
                "tool_calls": [
                    {
                        "id": "call_test_decompose",
                        "type": "function",
                        "function": {
                            "name": "task_decompose",
                            "arguments": json.dumps(
                                {
                                    "task_id": root.task_id,
                                    "subtasks": [
                                        "Search for frontier models",
                                        "Write report",
                                    ],
                                }
                            ),
                        },
                    }
                ],
                "metadata": {},
            }

        agent._call_llm = mock_llm

        # Mock _execute_tool_calls to actually run task_decompose.
        decompose_tool = TaskDecomposeTool()
        decompose_tool._store = store  # bind the session's task store

        original_result = LLMResult(
            content="I'll decompose the task",
            metadata={"tool_results": []},
        )
        validation = ValidationResult(
            is_valid=False,
            errors=[
                "task_analyzer must call at least one successful task-state tool from ['task_decompose', 'task_update']; task state cannot be inferred from prose."
            ],
        )

        # Call _recovery_retry directly.
        result = await loop._recovery_retry(
            node,
            agent,
            [decompose_tool, TerminateTool()],
            original_result,
            validation,
            missing_tools=["task_decompose", "terminate"],
        )

        # The successful commit should return directly.
        assert result is not None
        recovery_result, recovery_validation = result
        # task_decompose was called successfully.
        tool_results = recovery_result.metadata.get("tool_results", [])
        successful = {
            tr.get("name")
            for tr in tool_results
            if isinstance(tr.get("output"), dict) and tr["output"].get("success")
        }
        assert "task_decompose" in successful
        assert recovery_validation.is_valid


class TestUnboundedRecoveryAccumulatesPartialResult:
    """_unbounded_recovery accumulates partial results and advances missing."""

    @pytest.mark.asyncio
    async def test_task_decompose_recovery_finishes_without_terminate(self):
        """Recovery returns as soon as task_decompose succeeds."""
        loop = TinyCUALoop()
        store = loop.root_session.task_store

        root = store.create_task("Research frontier LLMs")
        store.active_task_id = root.task_id

        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)

        # Mock agent: _call_llm returns task_decompose on first call.
        # _execute_tool_calls will actually run the tool.
        agent = MagicMock()
        agent.tool_permissions = {}

        call_count = [0]

        async def mock_llm(messages, tools, stream=False, **kwargs):
            call_count[0] += 1
            return {
                "role": "assistant",
                "content": "Decomposing",
                "tool_calls": [
                    {
                        "id": f"call_decompose_{call_count[0]}",
                        "type": "function",
                        "function": {
                            "name": "task_decompose",
                            "arguments": json.dumps(
                                {
                                    "task_id": root.task_id,
                                    "subtasks": [f"Subtask {call_count[0]}"],
                                }
                            ),
                        },
                    }
                ],
                "metadata": {},
            }

        agent._call_llm = mock_llm

        # Build resolved_tools with task_decompose + terminate.
        decompose_tool = TaskDecomposeTool()
        decompose_tool._store = store
        terminate_tool = TerminateTool()
        resolved_tools = [decompose_tool, terminate_tool]

        original_result = LLMResult(
            content="I'll decompose",
            metadata={"tool_results": []},
        )
        validation = ValidationResult(
            is_valid=False,
            errors=[
                "task_analyzer must call at least one successful task-state tool from ['task_decompose', 'task_update']; task state cannot be inferred from prose."
            ],
        )

        # _unbounded_recovery should:
        # 1. structured_output_retry returns None (no LanguageModel in mock)
        # 2. After 15 structured attempts, focused_retry fires
        # 3. focused_retry calls task_decompose → succeeds → returns partial
        # 4. _unbounded_recovery accumulates task_decompose
        # 5. missing becomes ["terminate"] → direct_terminate fires
        # 6. Returns valid result
        recovery = await loop._unbounded_recovery(
            node,
            agent,
            resolved_tools,
            original_result,
            validation,
        )

        # The successful commit is the final lifecycle operation.
        assert recovery is not None
        result, final_validation = recovery
        assert final_validation.is_valid
        assert any(
            tc.get("function", {}).get("name") == "task_decompose"
            for tc in result.tool_calls
        )
        assert not any(
            tc.get("function", {}).get("name") == "terminate"
            for tc in result.tool_calls
        )


class TestNoProgressGuard:
    """Completed commits do not enter no-progress recovery."""

    @pytest.mark.asyncio
    async def test_completed_commit_needs_no_recovery_turn(self):
        """Accumulated commit evidence validates without terminate recovery."""
        loop = TinyCUALoop()
        store = loop.root_session.task_store
        root = store.create_task("Research frontier LLMs")
        store.active_task_id = root.task_id
        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)
        node.progress.satisfied_requirements.add("task_decompose")
        original_result = LLMResult(
            content="Already decomposed",
            metadata={
                "tool_results": [
                    {
                        "name": "task_decompose",
                        "allowed": True,
                        "output": {
                            "success": True,
                            "task_id": root.task_id,
                            "child_task_ids": ["child1"],
                        },
                    }
                ]
            },
        )
        validation = loop._validate_node_result(node, original_result)

        assert validation.is_valid


class TestStageToolHistory:
    """stage_tool_history records what each recovery stage produced (FR-063)."""

    @pytest.mark.asyncio
    async def test_history_records_successful_tool(self):
        """When a stage calls task_decompose successfully, the history records it."""
        loop = TinyCUALoop()
        store = loop.root_session.task_store

        root = store.create_task("Research frontier LLMs")
        store.active_task_id = root.task_id

        node = TinyCUATaskAnalyzerNode(
            node_id="task_analyzer",
            config=create_node_config("task_analyzer"),
        )
        node.ensure_session(loop.root_session)

        agent = MagicMock()
        agent.tool_permissions = {}

        async def mock_llm(messages, tools, stream=False, **kwargs):
            return {
                "role": "assistant",
                "content": "Decomposing",
                "tool_calls": [
                    {
                        "id": "call_hist_test",
                        "type": "function",
                        "function": {
                            "name": "task_decompose",
                            "arguments": json.dumps(
                                {
                                    "task_id": root.task_id,
                                    "subtasks": ["Subtask A"],
                                }
                            ),
                        },
                    }
                ],
                "metadata": {},
            }

        agent._call_llm = mock_llm

        decompose_tool = TaskDecomposeTool()
        decompose_tool._store = store
        terminate_tool = TerminateTool()
        resolved_tools = [decompose_tool, terminate_tool]

        original_result = LLMResult(
            content="I'll decompose",
            metadata={"tool_results": []},
        )
        validation = ValidationResult(
            is_valid=False,
            errors=[
                "task_analyzer must call at least one successful task-state tool from ['task_decompose', 'task_update']; task state cannot be inferred from prose."
            ],
        )

        await loop._unbounded_recovery(
            node,
            agent,
            resolved_tools,
            original_result,
            validation,
        )

        # stage_tool_history should have at least one entry recording
        # the successful task_decompose call.
        history = node.progress.stage_tool_history
        assert len(history) > 0
        # At least one entry should record task_decompose as a successful tool.
        has_decompose = any(
            "task_decompose" in entry.get("successful_tools", []) for entry in history
        )
        assert has_decompose
