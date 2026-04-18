"""Integration Tests: Memory and Session Tools

Tests based on example: 03_memory_and_session.py
Tests:
1. Memory tools with LLM
2. Memory streaming
3. Cancel execution
4. Session persistence
5. Custom memory backend
"""

import pytest
import asyncio
import logging
from tinycua_sdk.agent import Agent
from tinycua_sdk.tools import remember, recall, forget, list_memory
from tinycua_sdk.tools.memory import LocalMemoryBackend
from tinycua_sdk.tools.memory_tools import set_memory_backend, reset_memory_backend
from tinycua_sdk.utils import create_session, save_session, load_session, list_sessions, delete_session

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def memory_agent():
    """Create an agent with memory tools."""
    reset_memory_backend()  # Ensure clean state
    return Agent(
        name="memory-agent",
        instructions="You are a helpful assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=[remember, recall, forget, list_memory],
    )


@pytest.fixture
def temp_memory_backend():
    """Create a temporary memory backend."""
    import tempfile
    from pathlib import Path

    tmpdir = tempfile.mkdtemp()
    storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))
    set_memory_backend(storage)
    yield storage
    import shutil
    shutil.rmtree(tmpdir)


# =============================================================================
# Test Cases
# =============================================================================

class TestMemoryTools:
    """Test memory tool functionality."""

    @pytest.mark.asyncio
    async def test_remember_tool(self, memory_agent):
        """Test remembering information."""
        logger.info("Testing remember tool")
        # Remember something
        await memory_agent.run("Remember my name is Bob")

        # Verify it was stored
        result = list_memory.invoke()
        logger.info(f"Memory keys after remember: {result['keys']}")
        assert "name" in result["keys"] or "my name" in result["keys"]

    @pytest.mark.asyncio
    async def test_recall_tool(self, memory_agent):
        """Test recalling information."""
        logger.info("Testing recall tool")
        # Store information
        await memory_agent.run("Remember my favorite color is blue")

        # Recall it
        result = await memory_agent.run("What is my favorite color?")
        logger.info(f"Recalled: {result[:100]}...")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_list_memory_tool(self, memory_agent):
        """Test listing memory keys."""
        logger.info("Testing list_memory tool")
        # Remember something
        await memory_agent.run("Remember this is a test")

        # List memory
        result = list_memory.invoke()
        logger.info(f"Memory keys: {result['keys']}")
        assert isinstance(result, dict)
        assert "keys" in result


class TestMemoryStreaming:
    """Test memory tool streaming."""

    @pytest.mark.asyncio
    async def test_stream_with_memory_tool(self, memory_agent):
        """Test streaming with memory tool call."""
        from tinycua_sdk.models import StreamEventType

        logger.info("Testing streaming with memory tool")
        tool_calls_detected = False

        async for event in memory_agent.stream("Remember my favorite color is blue"):
            if event.type == StreamEventType.TOOL_CALL_START:
                tool_calls_detected = True
                logger.info(f"Tool call detected: {event.data.get('tool_name')}")
                break

        assert tool_calls_detected is True


class TestCancelExecution:
    """Test cancel execution functionality."""

    def test_cancel_agent(self, memory_agent):
        """Test canceling agent execution."""
        # Initial state
        assert memory_agent.is_cancelled is False

        # Cancel
        memory_agent.cancel()
        assert memory_agent.is_cancelled is True

        # Reset
        memory_agent.reset_cancel()
        assert memory_agent.is_cancelled is False


class TestSessionPersistence:
    """Test session persistence functionality."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """Test creating a session."""
        logger.info("Testing create_session")
        result = create_session(name="Test Session")
        logger.info(f"Created session: {result['session_id']}")
        assert "session_id" in result
        assert result["name"] == "Test Session"

    @pytest.mark.asyncio
    async def test_save_and_load_session(self):
        """Test saving and loading a session."""
        logger.info("Testing save and load session")
        result = create_session(name="Test Session")
        session_id = result["session_id"]

        # Save messages
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        save_session(session_id=session_id, messages=messages)
        logger.info(f"Saved {len(messages)} messages")

        # Load session
        loaded = load_session(session_id=session_id)
        logger.info(f"Loaded session: {loaded['name']} with {len(loaded['messages'])} messages")
        assert loaded["name"] == "Test Session"
        assert len(loaded["messages"]) == len(messages)

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        """Test listing sessions."""
        logger.info("Testing list_sessions")
        result = list_sessions()
        logger.info(f"Found {len(result['sessions'])} sessions")
        assert "sessions" in result
        assert isinstance(result["sessions"], list)

    @pytest.mark.asyncio
    async def test_delete_session(self):
        """Test deleting a session."""
        logger.info("Testing delete_session")
        result = create_session(name="Session to Delete")
        session_id = result["session_id"]
        logger.info(f"Created session: {session_id}")

        # Delete it
        delete_session(session_id=session_id)
        logger.info(f"Deleted session: {session_id}")


class TestCustomMemoryBackend:
    """Test custom memory backend functionality."""

    @pytest.mark.asyncio
    async def test_custom_backend(self, temp_memory_backend):
        """Test using a custom memory backend."""
        logger.info("Testing custom memory backend")
        agent = Agent(
            name="custom-agent",
            instructions="You are a helpful assistant.",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[remember, recall, list_memory],
        )

        # Remember something
        await agent.run("Remember my secret is 12345")

        # Verify it was stored
        result = list_memory.invoke()
        logger.info(f"Keys in custom backend: {result['keys']}")
        assert len(result["keys"]) > 0


# =============================================================================
# Test Runner
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
