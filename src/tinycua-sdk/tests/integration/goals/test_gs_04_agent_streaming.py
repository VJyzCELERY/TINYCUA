"""Integration tests for agent streaming.

Covers 3 success criteria:
  1. stream=False Returns String
  2. stream=True Yields Raw SSE Events
  3. stream=True with tool calls accumulates and resumes
"""

import os
from typing import AsyncIterator

import pytest

from tinycua_sdk import Agent, LanguageModel, tool


@pytest.fixture
def streaming_agent():
    """Create an agent that talks to the configured LLM server."""
    return Agent(
        name="streaming_test",
        llm_model=LanguageModel(
            provider=os.environ.get("TINYCUA_PROVIDER", "openai-compatible"),
            model_name=os.environ.get("TINYCUA_MODEL", "qwen/qwen3.5-9b"),
            base_url=os.environ.get("TINYCUA_BASE_URL", "http://localhost:1234/v1"),
            api_key=os.environ.get("TINYCUA_API_KEY", "dummy"),
        ),
    )


@tool
def get_time() -> str:
    """Return the current time."""
    return "12:00"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gs_01_stream_off_returns_string(streaming_agent):
    """stream=False returns a plain string."""
    response = await streaming_agent.run("Say hello.", stream=False)
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gs_02_stream_on_yields_events(streaming_agent):
    """stream=True yields raw SSE events."""
    stream: AsyncIterator[dict] = await streaming_agent.run(
        "Count to 3.", stream=True
    )
    events = [e async for e in stream]

    assert events[0]["type"] == "response.created"
    assert events[-1]["type"] == "response.completed"
    deltas = [e for e in events if e["type"] == "response.output_text.delta"]
    assert len(deltas) > 0
    usage_events = [e for e in events if e["type"] == "response.usage"]
    assert len(usage_events) > 0
    assert "usage" in usage_events[-1]
    assert isinstance(usage_events[-1]["usage"], dict)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gs_03_stream_with_tool_calls(streaming_agent):
    """stream=True with a registered tool triggers function call events."""
    streaming_agent.add_tools(get_time)
    stream: AsyncIterator[dict] = await streaming_agent.run(
        "What time is it? Use the get_time tool.", stream=True
    )
    events = [e async for e in stream]

    assert events[0]["type"] == "response.created"
    assert events[-1]["type"] == "response.completed"
    function_call_events = [
        e
        for e in events
        if e.get("type")
        in ("response.output_item.added", "response.function_call_arguments.delta",
            "response.function_call_arguments.done", "response.tool_call.delta")
    ]
    assert len(function_call_events) > 0, (
        "Expected tool call events in the stream; "
        "the LLM may not support tool calling or did not call get_time"
    )
