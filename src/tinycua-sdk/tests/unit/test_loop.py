"""Tests for BaseLoop execution."""

import asyncio
import pytest
from unittest.mock import AsyncMock

from tinycua_sdk import Agent, AgentPolicy, BaseLoop, LanguageModel, Skill, tool


class TestBaseLoopBuildSystemMessage:
    """Test _build_system_message method."""

    def test_build_system_message_with_instructions(self):
        agent = Agent(
            instructions="You are helpful.",
            llm_model=LanguageModel(),
        )
        loop = BaseLoop()
        msg = loop._build_system_message(agent)
        assert msg["role"] == "system"
        assert "You are helpful." in msg["content"]

    def test_build_system_message_with_override(self):
        agent = Agent(
            instructions="Original.",
            llm_model=LanguageModel(),
        )
        loop = BaseLoop()
        msg = loop._build_system_message(agent, "Override.")
        assert "Override." in msg["content"]
        assert "Original." not in msg["content"]

    def test_build_system_message_with_skills(self):
        skill = Skill(
            name="coder",
            description="Write code",
            instructions="Write clean code.",
        )
        agent = Agent(
            instructions="Be helpful.",
            llm_model=LanguageModel(),
            skills=[skill],
        )
        loop = BaseLoop()
        msg = loop._build_system_message(agent)
        assert "[coder]" in msg["content"]
        assert "Write clean code." in msg["content"]

    def test_build_system_message_no_instructions_no_skills(self):
        agent = Agent(llm_model=LanguageModel())
        loop = BaseLoop()
        msg = loop._build_system_message(agent)
        assert msg["content"] == ""


class TestBaseLoopRun:
    """Test BaseLoop.run() execution flow."""

    @pytest.mark.asyncio
    async def test_run_returns_content(self):
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        agent._call_llm = AsyncMock(
            return_value={
                "content": "Hello, world!",
                "tool_calls": None,
                "usage": None,
            }
        )

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "Say hi"}],
            tools=[],
        )
        assert result == "Hello, world!"
        agent._call_llm.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_with_tool_calls(self):
        @tool
        def get_time() -> str:
            return "12:00"

        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        call_count = 0

        async def mock_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_time",
                                "arguments": "{}",
                            },
                        }
                    ],
                    "usage": None,
                }
            return {
                "content": "The time is 12:00.",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "What time?"}],
            tools=[get_time],
        )
        assert result == "The time is 12:00."
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_run_unknown_tool(self):
        loop = BaseLoop(max_iterations=5)
        agent = Agent(llm_model=LanguageModel())

        call_count = 0

        async def mock_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "nonexistent_tool",
                                "arguments": "{}",
                            },
                        }
                    ],
                    "usage": None,
                }
            return {
                "content": "Tool not found.",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "Do something"}],
            tools=[],
        )
        assert result == "Tool not found."
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_run_max_iterations(self):
        loop = BaseLoop(max_iterations=2)

        agent = Agent(
            llm_model=LanguageModel(),
            policy=AgentPolicy(max_tool_calls=100),
        )

        call_count = 0

        async def tool_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{call_count}",
                        "type": "function",
                        "function": {
                            "name": "dummy_tool",
                            "arguments": "{}",
                        },
                    }
                ],
                "usage": None,
            }

        @tool
        def dummy_tool() -> str:
            return "result"

        agent._call_llm = tool_call_llm
        agent.add_tools(dummy_tool)

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "Keep going"}],
            tools=[dummy_tool],
        )
        assert call_count == 2
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_cancellation(self):
        loop = BaseLoop(max_iterations=10)
        agent = Agent(llm_model=LanguageModel())

        agent._cancelled = True

        with pytest.raises(asyncio.CancelledError):
            await loop.run(
                agent,
                messages=[{"role": "user", "content": "Cancel me"}],
                tools=[],
            )

    @pytest.mark.asyncio
    async def test_run_max_tool_calls_break(self):
        loop = BaseLoop(max_iterations=10)

        agent = Agent(
            llm_model=LanguageModel(),
            policy=AgentPolicy(max_tool_calls=1),
        )

        call_count = 0

        async def mock_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            return {
                "content": "still going",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        result = await loop.run(
            agent,
            messages=[{"role": "user", "content": "Go"}],
            tools=[],
        )
        assert result == "still going"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_run_with_override_instructions(self):
        loop = BaseLoop(max_iterations=5)
        agent = Agent(
            instructions="Original instructions.",
            llm_model=LanguageModel(),
        )

        captured_messages = []

        async def mock_call_llm(messages, tools):
            captured_messages.extend(messages)
            return {
                "content": "Done.",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        await loop.run(
            agent,
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
            override_instructions="Override instructions.",
        )

        assert any("Override instructions." in m["content"] for m in captured_messages if m["role"] == "system")
        assert not any("Original instructions." in m["content"] for m in captured_messages if m["role"] == "system")
