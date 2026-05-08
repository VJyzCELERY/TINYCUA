"""Target 3.4: Verify agent.cancel() stops an in-flight run."""

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

    task = asyncio.create_task(a.run("Write a very long essay about cheese."))
    await asyncio.sleep(0.5)  # Let it start
    a.cancel()

    try:
        response = await task
        print(f"Response (may be partial): {response}")
    except asyncio.CancelledError:
        print("Agent run was cancelled.")


asyncio.run(main())
