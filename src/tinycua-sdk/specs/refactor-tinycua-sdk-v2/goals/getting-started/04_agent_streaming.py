"""04 - Agent Streaming

Shows the two streaming modes available when running an agent:

  stream=False -> returns a plain str (default)
  stream=True  -> yields raw SSE events

Both modes follow the OpenAI Responses API event shape where applicable.
"""

import asyncio
from typing import AsyncIterator

from tinycua_sdk import Agent, LanguageModel


async def main() -> None:
    agent = Agent(
        name="streaming_assistant",
        llm_model=LanguageModel(
            provider="openai-compatible",
            model_name="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        ),
    )

    # -----------------------------------------------------------------------
    # 1. stream=False — default, returns the final response string
    # -----------------------------------------------------------------------
    response = await agent.run("Say hello.", stream=False)
    assert isinstance(response, str)
    print("[stream=False] Final:", response)

    # -----------------------------------------------------------------------
    # 2. stream=True — raw SSE events from the Responses API stream
    # -----------------------------------------------------------------------
    print("\n[stream=True] Events:")
    event_stream: AsyncIterator[dict] = await agent.run(
        "Count to 3.", stream=True
    )
    async for event in event_stream:
        print(f"  [{event['type']}]: {event}")


if __name__ == "__main__":
    asyncio.run(main())
