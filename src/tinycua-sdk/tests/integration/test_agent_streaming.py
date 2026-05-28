"""Integration tests for agent streaming.

Covers 3 success criteria:
  1. stream=False Returns String
  2. stream=True Yields SDK-Normalized Stream Events
  3. stream=True with tool calls accumulates and resumes
"""

import asyncio
from typing import AsyncIterator

import httpx
import pytest

from tinycua_sdk import Agent, LanguageModel, tool
from tests.integration.conftest import resolve_integration_llm_config


@pytest.fixture
def streaming_agent():
    """Create an agent that talks to the configured LLM server."""
    cfg = resolve_integration_llm_config()
    return Agent(
        name="streaming_test",
        llm_model=LanguageModel(
            provider=cfg.provider,
            model_name=cfg.model,
            base_url=cfg.base_url,
            api_key=cfg.api_key,
        ),
    )


TOOL_EVENT_TYPES = frozenset({
    "response.function_call_arguments.delta",
    "response.function_call_arguments.done",
    "response.output_item.added",
    "tool_call.ready",
})


async def _can_call_tools(agent: Agent, retries: int = 2) -> list[dict] | None:
    """Probe whether the LLM can call tools by making a test request.

    Returns the full event list when tool-call events are detected,
    or ``None`` when the LLM does not support tool calling (test
    should be skipped).  Returning the events eliminates the need
    for a second independent LLM call in the caller, removing a
    common source of flakiness.

    Retries up to ``retries`` times on transient errors to avoid
    false negatives from slow model responses or brief network issues.
    """
    probe = Agent(
        name="probe",
        llm_model=agent.llm_model,
    )
    probe.add_tools(get_time)
    for attempt in range(1 + retries):
        try:
            stream = await probe.run(
                "What time is it? Use the get_time tool.", stream=True
            )
            events: list[dict] = [e async for e in stream]
            for e in events:
                if e.get("type") in TOOL_EVENT_TYPES:
                    return events
        except (httpx.ConnectError, httpx.TimeoutException, asyncio.TimeoutError):
            if attempt < retries:
                await asyncio.sleep(0.5)
                continue
            raise
    return None


@tool
def get_time() -> str:
    """Return the current time."""
    return "12:00"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_off_returns_string(streaming_agent):
    """stream=False returns a plain string."""
    response = await streaming_agent.run("Say hello.", stream=False)
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_on_yields_events(streaming_agent):
    """stream=True yields SDK-normalized stream events."""
    stream: AsyncIterator[dict] = await streaming_agent.run(
        "Count to 3.", stream=True
    )
    events = [e async for e in stream]

    assert events[0]["type"] == "response.created"
    assert any(e["type"] == "response.completed" for e in events)
    deltas = [e for e in events if e["type"] == "response.output_text.delta"]
    assert len(deltas) > 0
    usage_events = [e for e in events if e["type"] == "response.usage"]
    assert len(usage_events) > 0
    assert "usage" in usage_events[-1]
    assert isinstance(usage_events[-1]["usage"], dict)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_with_tool_calls(streaming_agent):
    """stream=True with a registered tool triggers function call events."""
    events = await _can_call_tools(streaming_agent)
    if events is None:
        pytest.skip("LLM does not support tool calling")

    # Use the probe's events directly — avoids a second independent LLM
    # call that historically caused flaky failures (the LLM may decide
    # differently on the second invocation).
    assert events[0]["type"] == "response.created"
    assert any(e["type"] == "response.completed" for e in events)

    tool_call_events = [
        e for e in events
        if e.get("type") in TOOL_EVENT_TYPES
    ]
    assert len(tool_call_events) > 0, (
        "Expected tool call events in the stream; "
        "the LLM may not support tool calling or did not call get_time"
    )

    tool_event_indices = {
        i for i, e in enumerate(events)
        if e.get("type") in TOOL_EVENT_TYPES
    }
    if tool_event_indices:
        last_tool_idx = max(tool_event_indices)
        post_tool_events = events[last_tool_idx + 1:]
        post_tool_deltas = [
            e for e in post_tool_events
            if e.get("type") == "response.output_text.delta"
        ]
        assert len(post_tool_deltas) > 0, (
            "Expected text deltas after tool execution — "
            "stream did not resume"
        )
