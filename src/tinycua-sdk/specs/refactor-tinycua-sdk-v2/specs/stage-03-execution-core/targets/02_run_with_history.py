"""Target 3.2: Verify agent.run() respects prior message history."""

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

    history = [
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Nice to meet you!"},
    ]

    response = await a.run("What is my name?", messages=history, stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
