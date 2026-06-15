"""End-to-end deterministic tests for the finalized TinyCUA prototype runtime."""

from __future__ import annotations

from tinycua.factory import create_tinycua_agent


class ScriptedAgentResponses:
    """Deterministic model script exercising route, worker, tools, and final response."""

    def __init__(self) -> None:
        self.calls = 0

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
        if "task_decompose" in tool_names:
            root_id = ""
            for message in messages:
                if message.get("role") == "tool" and "task_id" in message.get("content", ""):
                    root_id = "ignored"
            return {"content": "decompose and execute", "tool_calls": []}
        return {"content": "final runtime answer", "tool_calls": []}


async def test_worker_prompt_creates_executes_reviews_and_aggregates_task_tree() -> None:
    """Complex prompts produce task state and final response, not a linear shell."""
    agent = create_tinycua_agent()
    script = ScriptedAgentResponses()
    agent._call_llm = script  # type: ignore[method-assign]

    result = await agent.run("Use worker mode to plan and execute a two-step migration.")

    trace = agent.loop.get_execution_trace()
    node_ids = [entry["node_id"] for entry in trace]
    snapshot = agent.loop.get_state_snapshot()
    assert result.strip()
    assert "worker" in node_ids
    assert "result_aggregation" in node_ids
    assert snapshot["task_tree"]["root_task_id"] is not None
    assert any(entry.get("task_tree") for entry in trace)
