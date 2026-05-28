"""Target 5.2: Verify stream=True yields raw SSE events."""

import asyncio
from tinycua_sdk import Agent, LanguageModel


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    stream = await a.run("Count to 3.", stream=True)
    print("[stream] Events:")
    async for event in stream:
        print(f"  [{event['type']}]: {event}")


asyncio.run(main())
