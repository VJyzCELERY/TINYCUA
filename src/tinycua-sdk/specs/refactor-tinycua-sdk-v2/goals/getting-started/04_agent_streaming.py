"""04 - Agent Streaming

Shows the four streaming modes available when running an agent.

  stream="off"   -> returns a plain str (or JSON dict)
  stream="event" -> yields agent events (tool_call, response, etc.)
  stream="token" -> yields raw LLM token chunks
  stream="all"   -> yields both token chunks and agent events

All modes follow the OpenAI Responses API event shape where applicable.
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
    # 1. stream="off" — default, returns the final response string
    # -----------------------------------------------------------------------
    response = await agent.run("Say hello.", stream="off")
    assert isinstance(response, str)
    print("[off] Final:", response)

    # -----------------------------------------------------------------------
    # 2. stream="token" — raw LLM token generation stream
    # -----------------------------------------------------------------------
    print("\n[token] Tokens:")
    token_stream: AsyncIterator[dict] = await agent.run(
        "Count to 3.", stream="token"
    )
    async for chunk in token_stream:
        # chunk shape (OpenAI-compatible):
        # {
        #   "type": "response.output_text.delta",
        #   "delta": "1",
        #   "item_id": "msg_abc123"
        # }
        print(chunk["delta"], end="", flush=True)
    print()

    # -----------------------------------------------------------------------
    # 3. stream="event" — agent-level events only (no token deltas)
    # -----------------------------------------------------------------------
    print("\n[event] Events:")
    event_stream: AsyncIterator[dict] = await agent.run(
        "What is 2+2?", stream="event"
    )
    async for event in event_stream:
        # Possible event types:
        #   "response.created"
        #   "response.output_item.added"  (tool_call, message, etc.)
        #   "response.completed"
        print(f"  [{event['type']}]: {event.get('item', {}).get('type', '')}")

    # -----------------------------------------------------------------------
    # 4. stream="all" — interleaved token chunks AND agent events
    # -----------------------------------------------------------------------
    print("\n[all] Mixed stream:")
    mixed_stream: AsyncIterator[dict] = await agent.run(
        "Tell me a short fact.", stream="all"
    )
    async for item in mixed_stream:
        if item["type"].endswith(".delta"):
            print(item["delta"], end="", flush=True)
        else:
            print(f"\n  [EVENT: {item['type']}]")
    print()


if __name__ == "__main__":
    asyncio.run(main())
