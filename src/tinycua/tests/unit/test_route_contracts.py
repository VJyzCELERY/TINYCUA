"""Route decision contract guardrails."""

from __future__ import annotations

from tinycua.factory import create_tinycua_agent
from tinycua.config.node_config import create_node_config
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.worker import TinyCUAWorkerNode


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


def test_required_route_prompts_do_not_offer_tools_unavailable_fallback() -> None:
    """Required-tool nodes must not teach the model to answer without tools."""
    query_node = TinyCUAQueryAnalystNode(
        node_id="query_analyst",
        config=create_node_config("query_analyst"),
    )
    worker_node = TinyCUAWorkerNode(
        node_id="worker",
        config=create_node_config("worker"),
    )

    prompts = [query_node.build_instruction(), worker_node.build_instruction()]

    assert all("If tools are unavailable" not in prompt for prompt in prompts)
    assert all("MUST call" in prompt for prompt in prompts)
