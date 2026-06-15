"""Example: Tool Streaming

This example demonstrates the streaming tool execution feature:
1. Stream LLM response token-by-token
2. See tool calls as they're detected
3. See tool results streaming in real-time

Prerequisites:
- LM Studio running with qwen/qwen3.5-9b model loaded
- LM Studio API accessible at http://localhost:1234/v1
"""

import asyncio

from tinycua_sdk.tools import tool
from tinycua_sdk.agent import Agent
from tinycua_sdk.models import StreamEventType


@tool()
def get_weather(location: str) -> dict:
    """Get current weather for a location.

    Args:
        location: City name (e.g., "Tokyo", "New York")

    Returns:
        Weather information dict
    """
    weather_db = {
        "tokyo": {"weather": "sunny", "temp": 22, "humidity": 65},
        "new york": {"weather": "cloudy", "temp": 18, "humidity": 72},
        "london": {"weather": "rainy", "temp": 12, "humidity": 85},
    }
    location_lower = location.lower()
    if location_lower in weather_db:
        return weather_db[location_lower]
    return {
        "weather": "unknown",
        "temp": 0,
        "humidity": 0,
        "note": f"No data for {location}",
    }


@tool()
def calculator(expression: str) -> dict:
    """Evaluate a math expression.

    Args:
        expression: Math expression (e.g., "2 + 2", "10 * 5")

    Returns:
        Result dict
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return {"expression": expression, "result": result, "success": True}
    except Exception as e:
        return {
            "expression": expression,
            "result": None,
            "error": str(e),
            "success": False,
        }


async def stream_text_only(agent: Agent):
    """Example 1: Stream text only (no tool calls)."""
    print("\n" + "=" * 50)
    print("Example 1: Text-only streaming")
    print("=" * 50)

    print("Prompt: 'Say hello in 2 words'")
    print("Streaming: ", end="")

    async for event in agent.stream("Say hello in 2 words"):
        if event.type == StreamEventType.CONTENT:
            print(event.data.get("content", ""), end="", flush=True)
        elif event.type == StreamEventType.DONE:
            print(f"\n[Done: {event.data.get('finish_reason')}]")


async def stream_with_tool_call(agent: Agent):
    """Example 2: Stream with tool execution."""
    print("\n" + "=" * 50)
    print("Example 2: Streaming with tool call")
    print("=" * 50)

    print("Prompt: 'What's the weather in Tokyo?'")
    print("Streaming: ")

    async for event in agent.stream("What's the weather in Tokyo?"):
        if event.type == StreamEventType.CONTENT:
            content = event.data.get("content", "")
            if content:
                print(content, end="", flush=True)
        elif event.type == StreamEventType.TOOL_CALL_START:
            print(f"\n>>> Tool call detected: {event.data.get('tool_name')}")
            print(f"    Arguments: {event.data.get('arguments', '')}")
        elif event.type == StreamEventType.TOOL_CALL_CHUNK:
            print(event.data.get("arguments", ""), end="", flush=True)
        elif event.type == StreamEventType.TOOL_RESULT_START:
            print(f"\n>>> Executing tool: {event.data.get('tool_name')}")
            print("    Result: ", end="")
        elif event.type == StreamEventType.TOOL_RESULT_CHUNK:
            print(event.data.get("content", ""), end="", flush=True)
        elif event.type == StreamEventType.TOOL_RESULT_END:
            print(f"\n    [Tool {event.data.get('tool_name')} complete]")
        elif event.type == StreamEventType.DONE:
            print(f"\n[Stream done: {event.data.get('finish_reason')}]")


async def stream_multiple_tools(agent: Agent):
    """Example 3: Stream with multiple tool calls."""
    print("\n" + "=" * 50)
    print("Example 3: Multiple tool calls")
    print("=" * 50)

    print("Prompt: 'What is 5 + 3? What about 10 * 6?'")
    print("Streaming: ")

    async for event in agent.stream("What is 5 + 3? What about 10 * 6?"):
        if event.type == StreamEventType.CONTENT:
            content = event.data.get("content", "")
            if content:
                print(content, end="", flush=True)
        elif event.type == StreamEventType.TOOL_CALL_START:
            print(f"\n>>> Tool: {event.data.get('tool_name')}")
        elif event.type == StreamEventType.TOOL_RESULT_CHUNK:
            print(event.data.get("content", ""), end="", flush=True)
        elif event.type == StreamEventType.TOOL_RESULT_END:
            print()
        elif event.type == StreamEventType.DONE:
            print("\n[Done]")


async def main():
    # Create agent
    agent = Agent(
        name="streaming-agent",
        instructions="You are a helpful assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=[get_weather, calculator],
    )

    print("Tool Streaming Example")
    print(f"Agent: {agent.name}")
    print(f"Tools: {[t.name for t in agent.tools]}")

    await stream_text_only(agent)
    await stream_with_tool_call(agent)
    await stream_multiple_tools(agent)

    print("\n" + "=" * 50)
    print("All examples completed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
