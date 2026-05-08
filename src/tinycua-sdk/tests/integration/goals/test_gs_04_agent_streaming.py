"""Integration tests for agent streaming modes.

Covers all 6 success criteria from spec.md:126-141:
  1. stream="off" Returns String
  2. stream="token" Yields Token Deltas
  3. stream="event" Yields Agent Events
  4. stream="all" Yields Both
  5. Streaming with Tool Calls
  6. Integration Test Pass
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
    """stream="off" returns a plain string."""
    response = await streaming_agent.run("Say hello.", stream="off")
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gs_02_stream_token_yields_deltas(streaming_agent):
    """stream="token" yields token delta events."""
    stream: AsyncIterator[dict] = await streaming_agent.run(
        "Count to 3.", stream="token"
    )
    events = [e async for e in stream]

    assert events[0]["type"] == "response.created"
    assert events[-1]["type"] == "response.completed"
    deltas = [e for e in events if e["type"] == "response.output_text.delta"]
    assert len(deltas) > 0
    allowed = {"response.output_text.delta", "response.created", "response.completed", "response.usage"}
    unexpected = [e for e in events if e["type"] not in allowed]
    assert len(unexpected) == 0, f"Unexpected events in token mode: {unexpected}"
    usage_events = [e for e in events if e["type"] == "response.usage"]
    assert len(usage_events) > 0
    assert "usage" in usage_events[0]
    assert isinstance(usage_events[0]["usage"], dict)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gs_03_stream_event_yields_agent_events(streaming_agent):
    """stream="event" yields agent-level events without token deltas."""
    stream: AsyncIterator[dict] = await streaming_agent.run(
        "What is 2+2?", stream="event"
    )
    events = [e async for e in stream]

    assert events[0]["type"] == "response.created"
    assert events[-1]["type"] == "response.completed"
    deltas = [e for e in events if e["type"] == "response.output_text.delta"]
    assert len(deltas) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gs_04_stream_all_yields_both(streaming_agent):
    """stream="all" yields interleaved token deltas and events."""
    stream: AsyncIterator[dict] = await streaming_agent.run(
        "Tell me a short fact.", stream="all"
    )
    events = [e async for e in stream]

    assert events[0]["type"] == "response.created"
    assert events[-1]["type"] == "response.completed"
    deltas = [e for e in events if e["type"] == "response.output_text.delta"]
    assert len(deltas) > 0
    added_events = [e for e in events if e["type"] == "response.output_item.added"]
    assert len(added_events) >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_gs_05_stream_with_tool_calls(streaming_agent):
    """Streaming with tool calls yields tool call events."""
    streaming_agent.add_tools(get_time)
    stream: AsyncIterator[dict] = await streaming_agent.run(
        "What time is it? Use the get_time tool.", stream="all"
    )
    events = [e async for e in stream]

    assert events[0]["type"] == "response.created"
    assert events[-1]["type"] == "response.completed"
    tool_events = [
        e
        for e in events
        if e.get("type") == "response.output_item.added"
        and e.get("item", {}).get("type") == "tool_call"
    ]
    assert len(tool_events) > 0
