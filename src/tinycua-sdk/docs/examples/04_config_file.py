"""Agent from YAML config example.

Demonstrates: Agent.from_config(), YAML-based agent definition.
"""

import asyncio

from tinycua_sdk import Agent


async def main():
    agent = Agent.from_config("agent.yaml")
    response = await agent.run("What is quantum computing?")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
