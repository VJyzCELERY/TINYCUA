"""Target 3.3: Verify runtime instruction override works."""

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

    response = await a.run(
        "Tell me a joke.",
        instructions="You are a pirate. Be funny and concise.",
        stream="off",
    )
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
