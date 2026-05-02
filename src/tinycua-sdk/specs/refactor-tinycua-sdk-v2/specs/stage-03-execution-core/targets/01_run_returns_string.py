"""Target 3.1: Verify agent.run() returns a string with stream='off'."""

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
    response = await a.run("Say hello.", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
