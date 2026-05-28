"""Example: Memory and Session Tools

This example demonstrates:
1. Memory tools used by an LLM agent
2. Session utilities for persistence
3. Cancel mechanism for interrupting execution

Prerequisites:
- LM Studio running with qwen/qwen3.5-9b model loaded
- LM Studio API accessible at http://localhost:1234/v1

Usage:
    python examples/03_memory_and_session.py
"""

import asyncio

from tinycua_sdk.agent import Agent
from tinycua_sdk.models import StreamEventType
from tinycua_sdk.tools import remember, recall, forget, list_memory
from tinycua_sdk.tools.memory import LocalMemoryBackend
from tinycua_sdk.tools.memory_tools import set_memory_backend, reset_memory_backend
from tinycua_sdk.utils import (
    create_session,
    save_session,
    load_session,
    list_sessions,
    delete_session,
)


async def demo_llm_with_memory():
    """Demonstrate LLM using memory tools."""
    print("\n" + "=" * 60)
    print("LLM with Memory Tools Demo")
    print("=" * 60)
    print("\nThis demonstrates the LLM actually using memory tools.")

    reset_memory_backend()

    agent = Agent(
        name="memory-agent",
        instructions="You are a helpful assistant. Use the remember tool to store important information.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=[remember, recall, forget, list_memory],
    )

    print("\n1. Tell the agent your name...")
    print("   Prompt: 'My name is Bob Smith'")
    print("\n   Response:")
    response = await agent.run("My name is Bob Smith")
    print(f"   {response[:200]}...")

    print("\n2. Ask the agent what your name is...")
    print("   Prompt: 'What is my name?'")
    print("\n   Response:")
    response = await agent.run("What is my name?")
    print(f"   {response[:200]}...")

    print("\n3. Verify memory was stored...")
    result = list_memory.invoke()
    print(f"   Keys in memory: {result['keys']}")

    if "name" in result["keys"]:
        result = recall.invoke(key="name")
        print(f"   Stored value: {result}")


async def demo_stream_with_memory():
    """Demonstrate streaming with memory tools."""
    print("\n" + "=" * 60)
    print("Streaming with Memory Tools Demo")
    print("=" * 60)

    reset_memory_backend()

    agent = Agent(
        name="streaming-agent",
        instructions="You are a helpful assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=[remember, recall, forget, list_memory],
    )

    print("\n1. Stream a response with memory tool call...")
    print("   Prompt: 'Remember my favorite color is blue'")
    print("\n   Streaming:")

    async for event in agent.stream("Remember my favorite color is blue"):
        if event.type == StreamEventType.CONTENT:
            print(event.data.get("content", ""), end="", flush=True)
        elif event.type == StreamEventType.TOOL_CALL_START:
            print(f"\n>>> Tool call: {event.data.get('tool_name')}")
        elif event.type == StreamEventType.TOOL_RESULT_CHUNK:
            print(event.data.get("content", ""), end="", flush=True)

    print("\n\n2. Verify memory was stored...")
    result = list_memory.invoke()
    print(f"   Keys: {result['keys']}")


async def demo_cancel_execution():
    """Demonstrate canceling execution mid-stream."""
    print("\n" + "=" * 60)
    print("Cancel Execution Demo")
    print("=" * 60)
    print("\nThis demonstrates canceling execution programmatically.")

    agent = Agent(
        name="cancel-test-agent",
        instructions="You are a helpful assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
    )

    print("\n1. Check initial state...")
    print(f"   is_cancelled: {agent.is_cancelled}")

    print("\n2. Cancel execution...")
    agent.cancel()
    print(f"   Cancelled: {agent.is_cancelled}")

    print("\n3. Reset cancel state...")
    agent.reset_cancel()
    print(f"   After reset: {agent.is_cancelled}")

    print(
        "\nNote: To cancel during streaming, call agent.cancel() from another task/thread"
    )


async def demo_session_persistence():
    """Demonstrate session save/load."""
    print("\n" + "=" * 60)
    print("Session Persistence Demo")
    print("=" * 60)

    print("\n1. Create a new session...")
    result = create_session(name="Chat with Bob")
    session_id = result["session_id"]
    print(f"   Created session: {session_id}")

    print("\n2. Simulate a conversation...")
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "What's the weather?"},
        {
            "role": "assistant",
            "content": "I don't have access to real-time weather data.",
        },
    ]
    save_session(session_id=session_id, messages=messages)
    print(f"   Saved {len(messages)} messages")

    print("\n3. Load the session...")
    loaded = load_session(session_id=session_id)
    print(f"   Loaded session: {loaded['name']}")
    print(f"   Messages: {len(loaded['messages'])}")

    print("\n4. List all sessions...")
    result = list_sessions()
    print(f"   Total sessions: {len(result['sessions'])}")

    print("\n5. Delete the session...")
    delete_session(session_id=session_id)
    print("   Deleted")

    result = list_sessions()
    print(f"   Remaining sessions: {len(result['sessions'])}")


async def demo_custom_backend():
    """Demonstrate using a custom memory backend."""
    print("\n" + "=" * 60)
    print("Custom Memory Backend Demo")
    print("=" * 60)

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))
        set_memory_backend(storage)

        print("\n1. Using custom backend (temp directory)...")

        agent = Agent(
            name="custom-agent",
            instructions="You are a helpful assistant.",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[remember, recall, list_memory],
        )

        print("   Prompt: 'Remember my secret is 12345'")
        response = await agent.run("Remember my secret is 12345")
        print(f"   Response: {response[:100]}...")

        print("\n2. Verify in custom backend...")
        result = list_memory.invoke()
        print(f"   Keys: {result['keys']}")

        result = recall.invoke(key="secret")
        print(f"   Secret: {result}")

    print("\n3. Reset to default backend...")
    reset_memory_backend()
    print("   Reset complete")


async def main():
    print("=" * 60)
    print("TINYCUA SDK - Memory & Session Demo")
    print("=" * 60)

    print("\nPrerequisites:")
    print("- LM Studio running at http://localhost:1234")
    print("- qwen/qwen3.5-9b model loaded")
    print("\nPress Ctrl+C to skip any demo")

    try:
        await demo_llm_with_memory()
    except Exception as e:
        print(f"\n   Skipped: {e}")

    try:
        await demo_session_persistence()
    except Exception as e:
        print(f"\n   Skipped: {e}")

    try:
        await demo_stream_with_memory()
    except Exception as e:
        print(f"\n   Skipped: {e}")

    try:
        await demo_cancel_execution()
    except Exception as e:
        print(f"\n   Skipped: {e}")

    try:
        await demo_custom_backend()
    except Exception as e:
        print(f"\n   Skipped: {e}")

    print("\n" + "=" * 60)
    print("All demos completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
