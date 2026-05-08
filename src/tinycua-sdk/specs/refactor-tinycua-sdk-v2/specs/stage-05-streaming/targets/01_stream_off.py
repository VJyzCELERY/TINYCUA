"""Target 5.1: Verify stream=False returns a plain string."""

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

    response = await a.run("Say hello.", stream=False)
    assert isinstance(response, str)
    print(f"[stream=False] Final: {response}")


asyncio.run(main())
