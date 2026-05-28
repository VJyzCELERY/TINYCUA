"""Target 8.6: Verify the default BaseLoop stream injects lifecycle events.

Validates R-8.4: the default loop MUST emit response.created, response.in_progress,
response.usage, and response.completed even when the raw provider stream only
emits content deltas.

This is a standalone deterministic verification target that injects a synthetic
stream. The same contract is verified against a real LLM endpoint by
test_integration_streaming_lifecycle_real_llm (in
tests/integration/goals/test_adv_01_custom_agent_loop.py, @pytest.mark.integration).
"""

import asyncio
from collections.abc import AsyncIterator

from tinycua_sdk import Agent, LanguageModel


async def deterministic_call_llm(messages, tools=None, stream: bool = False):
    """Return a stream that emits only content deltas (no lifecycle events).

    This lets us verify the default BaseLoop._run_stream() injects the
    missing response.created, response.in_progress, response.usage, and
    response.completed events required by R-8.4.
    """

    async def chunks() -> AsyncIterator[dict]:
        yield {"type": "response.output_text.delta", "delta": "Hello", "item_id": "msg_1"}

    return chunks()


async def main():
    a = Agent(llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"))
    a._call_llm = deterministic_call_llm  # type: ignore[method-assign]

    stream = await a.run("Hello", stream=True)
    events = [event async for event in stream]
    event_types = [e["type"] for e in events]

    assert "response.created" in event_types, f"Missing response.created in {event_types}"
    assert "response.in_progress" in event_types, f"Missing response.in_progress in {event_types}"
    assert "response.usage" in event_types, f"Missing response.usage in {event_types}"
    assert "response.completed" in event_types, f"Missing response.completed in {event_types}"

    # Verify order: created -> in_progress -> first content delta
    assert event_types.index("response.created") < event_types.index("response.in_progress"), \
        f"response.created should come before response.in_progress: {event_types}"
    assert event_types.index("response.in_progress") < event_types.index("response.output_text.delta"), \
        f"response.in_progress should come before first delta: {event_types}"

    print(f"Streaming lifecycle events correctly ordered: {event_types}")


asyncio.run(main())
