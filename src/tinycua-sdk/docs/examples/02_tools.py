"""Agent with tools example.

Demonstrates: @tool decorator, add_tools(), tool invocation in loop.
"""

import asyncio

from tinycua_sdk import Agent, LLMModel, tool


@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"


@tool
def summarize(text: str) -> str:
    """Summarize text."""
    return f"Summary: {text[:50]}..."


async def main():
    agent = Agent(
        llm_model=LLMModel(),
        instructions="Use search to find information, then summarize.",
    )
    # Add single tool
    agent.add_tools(search)
    # Add multiple tools
    agent.add_tools([summarize])

    response = await agent.run("What is quantum computing?")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
