"""End-to-end deterministic tests for the finalized TinyCUA prototype runtime."""

from __future__ import annotations

import re

from tinycua.factory import create_tinycua_agent


class ScriptedAgentResponses:
    """Deterministic model script exercising route, worker, tools, and final response."""

    def __init__(self) -> None:
        self.calls = 0

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


async def test_worker_prompt_creates_executes_reviews_and_aggregates_task_tree() -> None:
    """Complex prompts produce task state and final response, not a linear shell."""
    agent = create_tinycua_agent()
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
