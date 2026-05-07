"""Streaming response example.

Demonstrates: stream=True, async iteration over chunks.
"""

import asyncio

from tinycua_sdk import Agent, LLMModel


async def main():
    agent = Agent(llm_model=LLMModel())
    async for chunk in await agent.run("Tell me a story", stream=True):
        print(chunk, end="")
    print()


if __name__ == "__main__":
    asyncio.run(main())
