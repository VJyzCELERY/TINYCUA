"""Target 5.3: Verify stream='event' yields agent events without token deltas."""

import asyncio
from tinycua_sdk import Agent, LanguageModel


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    event_stream = await a.run("What is 2+2?", stream="event")
    print("\n[event] Events:")
    async for event in event_stream:
        # Should NOT contain .delta events
        assert not event["type"].endswith(".delta"), f"Unexpected delta event: {event['type']}"
        item_type = event.get("item", {}).get("type", "")
        print(f"  [{event['type']}]: {item_type}")


asyncio.run(main())
