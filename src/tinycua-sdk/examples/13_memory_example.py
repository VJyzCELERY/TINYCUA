"""Memory Example - Demonstrates the Memory system in TINYCUA SDK.

This example shows how to:
1. Use memory tools (remember, recall, forget, list_memory)
2. Use different memory backends
3. Use memory with an Agent

Prerequisites:
- OpenAI-compatible server running at http://localhost:1234/v1
- Model: qwen/qwen3.5-9b loaded
"""

import asyncio
import tempfile
import os

from tinycua_sdk import Agent
from tinycua_sdk.tools import (
    remember,
    recall,
    forget,
    list_memory,
    clear_memory,
    set_memory_backend,
    LocalMemoryBackend,
)


# =============================================================================
# Example 1: Basic Memory Operations
# =============================================================================

async def example_basic_memory():
    """Basic memory CRUD operations."""
    print("=" * 60)
    print("Example 1: Basic Memory Operations")
    print("=" * 60)
    
    # Set up a temporary memory backend
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_path = os.path.join(tmpdir, "memory.json")
        backend = LocalMemoryBackend(storage_path=memory_path)
        set_memory_backend(backend)
        
        # Remember a value
        print("\nRemembering: user_name = Alice")
        result = remember.invoke(key="user_name", value="Alice")
        print(f"  Result: {result}")
        
        # Remember another value
        print("\nRemembering: favorite_color = blue")
        result = remember.invoke(key="favorite_color", value="blue")
        print(f"  Result: {result}")
        
        # Recall a value
        print("\nRecalling: user_name")
        result = recall.invoke(key="user_name")
        print(f"  Result: {result}")
        
        # List all keys
        print("\nListing all keys:")
        result = list_memory.invoke()
        print(f"  Result: {result}")
        
        # Forget a value
        print("\nForgetting: favorite_color")
        result = forget.invoke(key="favorite_color")
        print(f"  Result: {result}")
        
        # List again
        print("\nAfter forgetting:")
        result = list_memory.invoke()
        print(f"  Result: {result}")
        
        # Clear all
        print("\nClearing all memory:")
        result = clear_memory.invoke()
        print(f"  Result: {result}")


# =============================================================================
# Example 2: Custom Memory Backend
# =============================================================================

async def example_custom_backend():
    """Use a custom memory backend."""
    print("\n" + "=" * 60)
    print("Example 2: Custom Memory Backend")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use a specific path
        memory_path = os.path.join(tmpdir, "my_memory.json")
        backend = LocalMemoryBackend(storage_path=memory_path)
        set_memory_backend(backend)
        
        print(f"\nUsing custom path: {memory_path}")
        
        # Store some data
        remember.invoke(key="secret", value="my-secret-value")
        
        # Recall it
        result = recall.invoke(key="secret")
        print(f"Recalled: {result}")
        
        # Check the file exists
        import os
        print(f"File exists: {os.path.exists(memory_path)}")
        
        # Read the file content
        with open(memory_path, 'r') as f:
            content = f.read()
            print(f"File content: {content[:100]}...")


# =============================================================================
# Example 3: Memory with Agent
# =============================================================================

async def example_memory_with_agent():
    """Use memory tools with an Agent."""
    print("\n" + "=" * 60)
    print("Example 3: Memory with Agent")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up temporary memory
        memory_path = os.path.join(tmpdir, "memory.json")
        backend = LocalMemoryBackend(storage_path=memory_path)
        set_memory_backend(backend)
        
        # Create an agent with memory tools
        agent = Agent(
            name="memory-agent",
            instructions="You have memory tools to remember and recall information.",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
            tools=[remember, recall, list_memory],  # Add memory tools
        )

        print(f"\nCreated agent: {agent.name}")
        print(f"Tools: {[t.name for t in agent.tools]}")

        # Test agent run
        print("\nTesting agent run:")
        try:
            response = await agent.run("Say hello in 3 words.")
            print(f"Response: {response}")
        except Exception as e:
            print(f"Error (expected if local OpenAI-compatible server not running): {e}")


# =============================================================================
# Example 4: Remembering User Preferences
# =============================================================================

async def example_user_preferences():
    """Remember and recall user preferences across conversations."""
    print("\n" + "=" * 60)
    print("Example 4: User Preferences")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_path = os.path.join(tmpdir, "memory.json")
        backend = LocalMemoryBackend(storage_path=memory_path)
        set_memory_backend(backend)
        
        # First conversation - learn user preferences
        print("\nConversation 1: Learning preferences")
        remember.invoke(key="user_name", value="Bob")
        remember.invoke(key="user_language", value="English")
        
        result = recall.invoke(key="user_name")
        print(f"Remembered name: {result}")
        
        # Second conversation - recall preferences
        print("\nConversation 2: Using preferences")
        result = recall.invoke(key="user_language")
        print(f"Recalled language: {result}")


# =============================================================================
# Example 5: Memory in Multi-Turn Conversation
# =============================================================================

async def example_memory_in_conversation():
    """Use memory in a multi-turn conversation."""
    print("\n" + "=" * 60)
    print("Example 5: Memory in Conversation")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_path = os.path.join(tmpdir, "memory.json")
        backend = LocalMemoryBackend(storage_path=memory_path)
        set_memory_backend(backend)
        
        # Create agent with memory tools
        agent = Agent(
            name="convo-agent",
            instructions="You can use memory to remember things between messages.",
            provider="openai-compatible",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
            tools=[remember, recall, list_memory],
        )
        
        # Note: In real usage, the LLM would call these tools automatically
        # when it needs to remember or recall information.
        
        # Manually store context for demonstration
        remember.invoke(key="context", value="User is asking about Python")
        remember.invoke(key="last_topic", value="Python programming")
        
        print("\nStored context in memory:")
        result = list_memory.invoke()
        print(f"  Keys: {result['keys']}")
        
        # Recall context
        print("\nRecalling context:")
        result = recall.invoke(key="context")
        print(f"  Result: {result}")


# =============================================================================
# Main
# =============================================================================

async def main():
    """Run all examples."""
    print("TINYCUA SDK - Memory Examples")
    print("=" * 60)
    
    await example_basic_memory()
    await example_custom_backend()
    await example_memory_with_agent()
    await example_user_preferences()
    await example_memory_in_conversation()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())