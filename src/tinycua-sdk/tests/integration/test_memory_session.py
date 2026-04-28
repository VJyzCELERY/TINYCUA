"""End-to-end integration tests for memory, session, and cancel features.

These tests require:
- LM Studio running with qwen/qwen3.5-9b model loaded
- LM Studio API accessible at http://localhost:1234/v1

Run with: pytest tests/integration/ -v -m integration
"""

import pytest
import tempfile
from pathlib import Path


class TestMemoryToolsWithLLM:
    """Test memory tools with actual LLM."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_llm_uses_remember_tool(self):
        """Test that LLM calls remember tool when prompted."""
        from tinycua_sdk.models import Agent
        from tinycua.agent.tools.memory_tools import remember, recall, list_memory
        from tinycua.agent.tools.memory_tools import reset_memory_backend

        reset_memory_backend()

        agent = Agent(
            name="test-memory",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[remember, recall, list_memory],
        )

        await agent.run("My favorite color is purple")

        result = list_memory.invoke()
        assert "favorite_color" in result["keys"] or "color" in result["keys"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_llm_uses_recall_tool(self):
        """Test that LLM calls recall tool when prompted."""
        from tinycua_sdk.models import Agent
        from tinycua.agent.tools.memory_tools import remember, recall
        from tinycua.agent.tools.memory_tools import reset_memory_backend

        reset_memory_backend()

        remember.invoke(key="name", value="Alice")

        agent = Agent(
            name="test-recall",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[remember, recall],
        )

        await agent.run("What is my name?")


class TestMemoryStreaming:
    """Test streaming with memory tools."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_stream_with_memory_tool(self):
        """Test streaming response with memory tool call."""
        from tinycua_sdk.models import Agent, StreamEventType
        from tinycua.agent.tools.memory_tools import remember
        from tinycua.agent.tools.memory_tools import reset_memory_backend

        reset_memory_backend()

        agent = Agent(
            name="test-stream-memory",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
            tools=[remember],
        )

        tool_call_events = []

        async for event in agent.stream("Remember my pet is cat"):
            if event.type == StreamEventType.TOOL_CALL_START:
                tool_call_events.append(event)

        assert len(tool_call_events) > 0


class TestSessionUtilities:
    """Test session utilities."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_and_load_session(self):
        """Test creating and loading a session."""
        from tinycua_sdk.utils import (
            create_session,
            save_session,
            load_session,
            delete_session,
        )

        result = create_session(name="Test Session")
        session_id = result["session_id"]

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        save_result = save_session(session_id=session_id, messages=messages)
        assert save_result["success"] is True

        loaded = load_session(session_id=session_id)
        assert loaded["success"] is True
        assert len(loaded["messages"]) == 2

        delete_result = delete_session(session_id=session_id)
        assert delete_result["success"] is True

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_sessions(self):
        """Test listing sessions."""
        from tinycua_sdk.utils import create_session, list_sessions, delete_session

        result = create_session(name="List Test Session")
        session_id = result["session_id"]

        result = list_sessions()
        assert "sessions" in result
        assert len(result["sessions"]) >= 1

        delete_session(session_id=session_id)


class TestCancelMechanism:
    """Test cancel mechanism."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cancel_state(self):
        """Test cancel state changes."""
        from tinycua_sdk.models import Agent

        agent = Agent(
            name="test-cancel",
            provider="lmstudio",
            model="qwen/qwen3.5-9b",
            base_url="http://localhost:1234",
            api_key="dummy",
        )

        assert agent.is_cancelled is False

        agent.cancel()
        assert agent.is_cancelled is True

        agent.reset_cancel()
        assert agent.is_cancelled is False


class TestCustomMemoryBackend:
    """Test custom memory backend."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_custom_backend_with_llm(self):
        """Test using custom memory backend with LLM."""
        from tinycua_sdk.models import Agent
        from tinycua.agent.tools.memory_tools import remember, recall, list_memory
        from tinycua_sdk.tools.memory import LocalMemoryBackend
        from tinycua.agent.tools.memory_tools import (
            set_memory_backend,
            reset_memory_backend,
        )

        reset_memory_backend()

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalMemoryBackend(storage_path=str(Path(tmpdir) / "memory.json"))
            set_memory_backend(storage)

            agent = Agent(
                name="test-custom",
                provider="lmstudio",
                model="qwen/qwen3.5-9b",
                base_url="http://localhost:1234",
                api_key="dummy",
                tools=[remember, recall, list_memory],
            )

            await agent.run("Remember my number is 42")

            result = list_memory.invoke()
            assert "number" in result["keys"] or len(result["keys"]) > 0

        reset_memory_backend()


class TestMemoryPersistence:
    """Test that memory persists across agent runs."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_memory_persists_between_runs(self):
        """Test memory is accessible in subsequent runs."""
        from tinycua.agent.tools.memory_tools import remember, recall
        from tinycua.agent.tools.memory_tools import reset_memory_backend

        reset_memory_backend()

        remember.invoke(key="test_key", value="test_value")

        result = recall.invoke(key="test_key")
        assert result["found"] is True
        assert result["value"] == "test_value"
