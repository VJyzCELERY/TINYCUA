"""Target 8.6: Verify streaming events include all required event types."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop


class StreamingEventCollector(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        assert stream, "Target 8.6 requires stream=True"
        events: list[dict] = []
        async for event in agent._call_llm(messages, tools, stream=True):
            events.append(event)
        return events


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        loop=StreamingEventCollector(),
    )

    # Use a mock LLM server that emits the standard event sequence
    events = await a.run("Hello", stream=True)

    event_types = [e.get("type") for e in events]
    assert "response.created" in event_types, f"Missing response.created in {event_types}"
    assert "response.in_progress" in event_types, f"Missing response.in_progress in {event_types}"
    assert "response.usage" in event_types, f"Missing response.usage in {event_types}"
    assert "response.completed" in event_types, f"Missing response.completed in {event_types}"
    print(f"Streaming event types OK: {event_types}")


asyncio.run(main())
