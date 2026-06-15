"""Route decision contract guardrails."""

from __future__ import annotations

from tinycua.factory import create_tinycua_agent


async def test_query_route_does_not_use_keyword_inference_without_tool_call() -> None:
    """Worker-looking keywords are not enough to override model route failure."""
    agent = create_tinycua_agent()

    async def invalid_route_response(messages, tools, stream=False):
        return {"content": "I will plan and execute this task", "tool_calls": []}

    agent._call_llm = invalid_route_response  # type: ignore[method-assign]
    await agent.run("Plan and execute a migration task.")

    first_trace = agent.loop.get_execution_trace()[0]
    assert first_trace["node_id"] == "query_analyst"
    assert first_trace["route_label"] == "passthrough"
    assert first_trace["route_source"] == "content_or_fallback"
