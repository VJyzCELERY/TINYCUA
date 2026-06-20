"""Route decision contract guardrails."""

from __future__ import annotations

import pytest

from tinycua.factory import create_tinycua_agent
from tinycua.config.node_config import create_node_config
from tinycua.loops.node import NodeExecutionError
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.worker import TinyCUAWorkerNode


async def test_query_route_does_not_use_keyword_inference_without_tool_call() -> None:
    """Worker-looking keywords are not enough to override model route failure.

    The query_analyst validation gate rejects a response with no
    select_query_route tool call, regardless of keyword content. With the
    unbounded recovery loop, this validation failure would trigger retries
    forever in production. This test verifies the validation gate itself.
    """
    from tinycua.config.types import LLMResult
    from tinycua.loops.tinycua_loop import TinyCUALoop

    loop = TinyCUALoop()
    node = TinyCUAQueryAnalystNode(
        node_id="query_analyst",
        config=create_node_config("query_analyst"),
    )
    result = LLMResult(content="I will plan and execute this task")
    validation = loop._validate_node_result(node, result)

    assert not validation.is_valid
    assert any("select_query_route" in error for error in validation.errors)


async def test_query_route_accepts_strict_structured_tool_protocol() -> None:
    """Local models may emit explicit JSON tool calls when native tools are absent."""
    agent = create_tinycua_agent()

    async def structured_route_response(messages, tools, stream=False):  # noqa: ANN001, ARG001
        if any(tool.name == "select_query_route" for tool in tools):
            return {
                "content": '{"tool_calls":[{"name":"select_query_route","arguments":{"route":"passthrough"}}]}',
                "tool_calls": [],
            }
        return {"content": "Hello.", "tool_calls": []}

    agent._call_llm = structured_route_response  # type: ignore[method-assign]
    await agent.run("Say hello.")

    first_trace = agent.loop.get_execution_trace()[0]
    assert first_trace["node_id"] == "query_analyst"
    assert first_trace["route_label"] == "passthrough"
    assert first_trace["route_source"] == "tool_call"


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
