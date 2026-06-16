"""End-to-end deterministic tests for the finalized TinyCUA prototype runtime."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua_sdk.tools.decorators import tool


@tool(name="write_file")
def fake_write_file(path: str, content: str) -> dict[str, Any]:
    """Return successful file-write evidence without touching disk."""
    return {
        "success": True,
        "path": path,
        "chars_written": len(content),
        "error": None,
    }


class ScriptedAgentResponses:
    """Deterministic model script exercising route, worker, tools, and final response."""

    def __init__(self) -> None:
        self.calls = 0
        self.executor_write_done_by_task: set[str] = set()

    def _task_id(self, messages, key: str = "active_task_id") -> str:
        """Extract a task id from serialized task snapshots."""
        text = "\n".join(str(message.get("content", "")) for message in messages)
        match = re.search(rf"'{key}': '([^']+)'", text) or re.search(
            rf'"{key}": "([^"]+)"',
            text,
        )
        if match:
            return match.group(1)
        match = re.search(r"'root_task_id': '([^']+)'", text) or re.search(
            r'"root_task_id": "([^"]+)"',
            text,
        )
        return match.group(1) if match else ""

    async def __call__(self, messages, tools, stream=False):
        self.calls += 1
        tool_names = {tool.name for tool in tools}
        if "select_query_route" in tool_names:
            return {
                "content": "routing to worker",
                "tool_calls": [{"function": {"name": "select_query_route", "arguments": '{"route":"worker"}'}}],
            }
        if "select_worker_route" in tool_names:
            return {
                "content": "creating tasks",
                "tool_calls": [{"function": {"name": "select_worker_route", "arguments": '{"route":"task_creation"}'}}],
            }
        if "task_init" in tool_names:
            if any(
                message.get("role") == "tool"
                and "task_init" in str(message.get("content", ""))
                for message in messages
            ):
                return {"content": "initialized task tree", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_init",
                            "arguments": '{"title":"Plan and execute a two-step migration"}',
                        }
                    }
                ],
            }
        if "task_decompose" in tool_names:
            task_id = self._task_id(messages, "root_task_id")
            if any(
                message.get("role") == "tool"
                and "task_decompose" in str(message.get("content", ""))
                for message in messages
            ):
                return {"content": "root task is decomposed", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_decompose",
                            "arguments": (
                                '{"task_id":"'
                                + task_id
                                + '","subtasks":["Plan migration","Execute migration"]}'
                            ),
                        }
                    }
                ],
            }
        if "task_update" in tool_names:
            task_id = self._task_id(messages)
            if any(
                message.get("role") == "tool"
                and "task_update" in str(message.get("content", ""))
                for message in messages
            ):
                return {"content": "assessment recorded", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_update",
                            "arguments": (
                                '{"task_id":"'
                                + task_id
                                + '","assessment":"ready"}'
                            ),
                        }
                    }
                ],
            }
        if "task_result_update" in tool_names:
            task_id = self._task_id(messages)
            if "write_file" in tool_names and task_id not in self.executor_write_done_by_task:
                self.executor_write_done_by_task.add(task_id)
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "write_file",
                                "arguments": (
                                    '{"path":"migration-'
                                    + task_id
                                    + '.txt",'
                                    '"content":"Executed migration steps.\\n"}'
                                ),
                            }
                        }
                    ],
                }
            if any(
                message.get("role") == "tool"
                and "task_result_update" in str(message.get("content", ""))
                for message in messages
            ):
                return {"content": "execution recorded", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_result_update",
                            "arguments": '{"content":"Executed migration steps deterministically.","success":true}',
                        }
                    }
                ],
            }
        if "task_review_decision" in tool_names:
            if "task_inspect" in tool_names and not any(
                message.get("role") == "tool"
                and "task_inspect" in str(message.get("content", ""))
                for message in messages
            ):
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "task_inspect",
                                "arguments": "{}",
                            }
                        }
                    ],
                }
            if any(
                message.get("role") == "tool"
                and "task_review_decision" in str(message.get("content", ""))
                for message in messages
            ):
                return {"content": "approved", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_review_decision",
                            "arguments": '{"decision":"approved","rationale":"Execution result is present."}',
                        }
                    }
                ],
            }
        return {"content": "final runtime answer", "tool_calls": []}


async def test_worker_prompt_creates_executes_reviews_and_aggregates_task_tree(
    tmp_path: Path,
) -> None:
    """Complex prompts produce task state and final response, not a linear shell."""
    agent = create_tinycua_agent(
        session_config=SessionConfig(workspace_dir=tmp_path),
        enable_native_tools=False,
        tools=[fake_write_file],
    )
    script = ScriptedAgentResponses()
    agent._call_llm = script  # type: ignore[method-assign]

    result = await agent.run("Plan and execute a two-step migration.")

    trace = agent.loop.get_execution_trace()
    node_ids = [entry["node_id"] for entry in trace]
    snapshot = agent.loop.get_state_snapshot()
    assert result.strip()
    assert "worker" in node_ids
    assert "result_aggregation" in node_ids
    assert snapshot["task_tree"]["root_task_id"] is not None
    assert any(entry.get("task_tree") for entry in trace)
