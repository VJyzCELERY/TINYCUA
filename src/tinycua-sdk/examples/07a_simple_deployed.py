"""Example: Simple Deployed Agent

Minimal example showing how to deploy and run an agent.

Prerequisites:
- PostgreSQL (make docker-up)
- Backend running
- Runner running
- OpenAI-compatible server with model
- .env file with credentials

Usage:
    cp .env.example .env
    # Edit .env with your backend URL and API key
    python examples/07a_simple_deployed.py
"""

import asyncio
import os

# Import to load .env file

from tinycua_sdk.tools import tool
from tinycua_sdk.agent import Agent


BACKEND_URL = os.getenv("TINYCUA_BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("TINYCUA_API_KEY", "")


@tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


async def main():
    print(f"Backend: {BACKEND_URL}")

    # Create agent
    agent = Agent(
        name="calc-bot",
        instructions="You are a calculator assistant.",
        provider=os.getenv("TINYCUA_PROVIDER", "openai-compatible"),
        model=os.getenv("TINYCUA_MODEL", "qwen/qwen3.5-9b"),
        base_url=os.getenv("TINYCUA_BASE_URL", "http://127.0.0.1:1234/v1"),
        tools=[add],
        backend_url=BACKEND_URL,
        backend_api_key=API_KEY,
    )

    # Deploy
    await agent.deploy()
    print(f"Deployed: {agent.is_deployed}")

    # Run via backend
    result = await agent.run("What is 5 + 3?")
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
