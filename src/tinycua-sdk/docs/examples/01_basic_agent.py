"""Basic agent example.

Demonstrates: Agent construction with LLMModel, simple run().
"""

import asyncio

from tinycua_sdk import Agent, LLMModel


async def main():
    agent = Agent(
        llm_model=LLMModel(
            base_url="http://localhost:1234/v1",
            model_name="qwen3.5-9b",
            system_prompt="You are a helpful assistant.",
        ),
        instructions="Answer questions concisely.",
    )
    response = await agent.run("What is quantum computing?")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
