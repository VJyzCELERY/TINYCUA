"""Final response contracts: no synthetic success and observable final stream."""

from __future__ import annotations

import pytest

from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.tinycua_loop import TinyCUALoop


class EmptyResponseAgent:
    """Agent double that returns an empty terminal response."""

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        if not stream:
            return {"role": "assistant", "content": ""}

        async def events():
            if False:
                yield {}

        return events()


class StreamingResponseAgent:
    """Agent double that streams terminal response deltas."""

    async def _call_llm(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        if not stream:
            return {"role": "assistant", "content": "done"}

        async def events():
            yield {"type": "response.output_text.delta", "delta": "hel"}
            yield {"type": "response.output_text.delta", "delta": "lo"}
            yield {"type": "response.usage", "usage": {"output_tokens": 1}}

        return events()


@pytest.mark.asyncio
async def test_empty_terminal_response_is_not_synthetic_success() -> None:
    """An empty ResponseNode result remains empty unless fallback is configured."""
    loop = TinyCUALoop(queue=NodeQueue(items=[ResponseNode()]))

    result = await loop.run(
        EmptyResponseAgent(),
        messages=[{"role": "user", "content": "do work"}],
        tools=[],
    )

    assert result == ""
    assert "Processed request" not in result


@pytest.mark.asyncio
async def test_final_response_events_capture_only_terminal_user_visible_stream() -> None:
    """Final response events expose terminal text deltas without debug events."""
    loop = TinyCUALoop(queue=NodeQueue(items=[ResponseNode()]))

    stream = await loop.run(
        StreamingResponseAgent(),
        messages=[{"role": "user", "content": "hello"}],
        tools=[],
        stream=True,
    )
    events = [event async for event in stream]

    assert "hello" == "".join(
        event["delta"] for event in loop.get_final_response_events()
    )
    assert all(
        event["type"] == "response.output_text.delta"
        for event in loop.get_final_response_events()
    )
    assert any(event["type"] == "node.completed" for event in events)
