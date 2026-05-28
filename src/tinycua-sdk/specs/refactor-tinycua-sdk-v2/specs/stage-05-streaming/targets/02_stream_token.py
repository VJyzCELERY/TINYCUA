"""Target 5.2: Verify stream='token' yields token delta events."""

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

    token_stream = await a.run("Count to 3.", stream="token")
    print("\n[token] Tokens:")
    async for chunk in token_stream:
        assert chunk["type"] == "response.output_text.delta"
        delta = chunk.get("delta", "")
        if delta:
            print(delta, end="", flush=True)
    print()


asyncio.run(main())
