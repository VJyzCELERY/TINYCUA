"""Target 5.4: Verify stream='all' yields interleaved token deltas and agent events."""

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

    mixed_stream = await a.run("Tell me a short fact.", stream="all")
    print("\n[all] Mixed stream:")
    async for item in mixed_stream:
        if item["type"].endswith(".delta"):
            delta = item.get("delta", "")
            if delta:
                print(delta, end="", flush=True)
        else:
            print(f"\n  [EVENT: {item['type']}]")
    print()


asyncio.run(main())
