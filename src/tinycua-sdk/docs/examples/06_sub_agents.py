"""Agent with sub-agents example.

Demonstrates: Agent composition, sub-agent delegation.
"""

import asyncio

from tinycua_sdk import Agent, LLMModel


async def main():
    coordinator = Agent(
        name="coordinator",
        llm_model=LLMModel(),
        instructions="Coordinate tasks between sub-agents.",
    )

    researcher = Agent(
        name="researcher",
        llm_model=LLMModel(),
        instructions="Research topics thoroughly.",
    )

    writer = Agent(
        name="writer",
        llm_model=LLMModel(),
        instructions="Write clear, engaging content.",
    )

    # Compose: coordinator delegates to sub-agents
    coordinator.add_sub_agent(researcher)
    coordinator.add_sub_agent(writer)

    response = await coordinator.run("Write a blog post about quantum computing")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
