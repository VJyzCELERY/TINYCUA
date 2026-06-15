"""Example: Tool Calling with LM Studio (qwen3.5-9b)

This example demonstrates:
1. Creating an Agent with tools
2. Running the agent with .run() method
3. Using plan mode for complex tasks
4. Streaming with tool execution

Prerequisites:
- LM Studio running with qwen/qwen3.5-9b model loaded
- LM Studio API accessible at http://localhost:1234/v1
"""

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


async def main():
    # Create an agent
    agent = Agent(
        name="weather-assistant",
        instructions="You are a helpful assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=[get_weather, calculator],
    )

    print(f"Agent: {agent.name}")
    print(f"Tools: {[t.name for t in agent.tools]}")
    print("-" * 50)

    # Test direct mode
    print("\n[1] Direct mode - simple completion...")
    response = await agent.run("Say hello in one sentence.")
    print(f"Assistant: {response}")

    print("\n[2] Direct mode - tool call...")
    response = await agent.run("What's the weather in Tokyo?")
    print(f"Assistant: {response}")

    print("\n[3] Direct mode - calculator...")
    response = await agent.run("What is 15 * 7?")
    print(f"Assistant: {response}")

    # Create a planner agent
    planner_agent = Agent(
        name="planner-assistant",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=[get_weather, calculator],
        plan_mode="plan",
    )

    print("\n" + "=" * 50)
    print("Testing PLAN MODE")
    print("=" * 50)

    print("\n[4] Plan mode - complex task...")
    response = await planner_agent.run(
        "Check weather in Tokyo and New York, then compare"
    )
    print(f"Assistant: {response}")

    # Test with trace
    print("\n[5] Direct mode with trace...")
    result = await agent.run("What's the weather in Tokyo?", trace=True)
    print(f"Response: {result.response}")
    print(f"Tool Calls: {len(result.tool_calls)}")
    print(f"Total Tokens: {result.total_tokens}")

    # Test deploy
    print("\n[6] Testing deploy...")
    deployment = await agent.deploy()
    print(f"Status: {deployment['status']}")
    print(f"Agent ID: {deployment['agent_id']}")
    print(f"Backend URL: {deployment['backend_url']}")
    print(f"Tools deployed: {deployment['tools']}")
    print(f"Agent mode: {agent.mode}")
    print(f"Is deployed: {agent.is_deployed}")

    # Test streaming (now returns StreamEvent objects)
    print("\n[7] Testing stream (text only)...")
    print("Streaming response: ", end="")
    async for event in agent.stream("Say hello in 3 words"):
        if event.type == StreamEventType.CONTENT:
            print(event.data.get("content", ""), end="", flush=True)
    print()

    # Test streaming with tools
    print("\n[8] Testing stream with tools...")
    print("Streaming response: ", end="")
    async for event in agent.stream("What's the weather in Tokyo?"):
        if event.type == StreamEventType.CONTENT:
            print(event.data.get("content", ""), end="", flush=True)
        elif event.type == StreamEventType.TOOL_CALL_START:
            print(f"\n[Tool call: {event.data.get('tool_name')}]", end="", flush=True)
        elif event.type == StreamEventType.TOOL_RESULT_START:
            print(f"\n[Tool result: {event.data.get('tool_name')}]", end="", flush=True)
        elif event.type == StreamEventType.TOOL_RESULT_CHUNK:
            print(event.data.get("content", ""), end="", flush=True)
        elif event.type == StreamEventType.DONE:
            print(f"\n[Done: {event.data.get('finish_reason')}]", flush=True)

    print("\n" + "=" * 50)
    print("Example completed!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
