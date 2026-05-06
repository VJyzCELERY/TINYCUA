"""Tests for Agent.run() method."""

import asyncio
import pytest
from unittest.mock import AsyncMock

from tinycua_sdk import Agent, BaseLoop, LanguageModel, tool


class TestAgentRun:
    """Test Agent.run() method."""

    @pytest.mark.asyncio
    async def test_run_returns_string(self):
        agent = Agent(llm_model=LanguageModel())

        mock_loop = AsyncMock(spec=BaseLoop)
        mock_loop.run = AsyncMock(return_value="Hello, world!")
        agent.config.loop = mock_loop

        result = await agent.run("Say hello")
        assert isinstance(result, str)
        assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_run_passes_query_as_user_message(self):
        agent = Agent(llm_model=LanguageModel())

        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None):
                captured["messages"] = messages
                captured["tools"] = tools
                captured["override"] = override_instructions
                return "ok"

        agent.config.loop = CapturingLoop()

        result = await agent.run("What is 2+2?")
        assert result == "ok"
        assert captured["messages"][-1] == {
            "role": "user",
            "content": "What is 2+2?",
        }

    @pytest.mark.asyncio
    async def test_run_with_message_history(self):
        agent = Agent(llm_model=LanguageModel())

        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()

        history = [
            {"role": "user", "content": "Previous message."},
            {"role": "assistant", "content": "Previous response."},
        ]

        await agent.run(
            "New query",
            messages=history,
        )
        assert captured["messages"][0] == history[0]
        assert captured["messages"][1] == history[1]
        assert captured["messages"][2] == {
            "role": "user",
            "content": "New query",
        }

    @pytest.mark.asyncio
    async def test_run_with_instruction_override(self):
        agent = Agent(
            instructions="Default instructions.",
            llm_model=LanguageModel(),
        )

        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None):
                captured["override"] = override_instructions
                return "ok"

        agent.config.loop = CapturingLoop()

        await agent.run(
            "Query",
            instructions="Override instructions.",
        )
        assert captured["override"] == "Override instructions."

    @pytest.mark.asyncio
    async def test_run_uses_default_loop_when_none_set(self):
        agent = Agent(llm_model=LanguageModel())
        assert agent.loop is None

        agent._call_llm = AsyncMock(
            return_value={
                "content": "Default loop works.",
                "tool_calls": None,
                "usage": None,
            }
        )

        result = await agent.run("Test default loop")
        assert result == "Default loop works."

    @pytest.mark.asyncio
    async def test_run_rejects_streaming(self):
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(NotImplementedError, match="Streaming"):
            await agent.run("Query", stream="event")

    @pytest.mark.asyncio
    async def test_cancellation_before_run(self):
        agent = Agent(llm_model=LanguageModel())

        agent.cancel()
        assert agent.is_cancelled is True

        with pytest.raises(asyncio.CancelledError):
            await agent.run("Cancelled query")

    @pytest.mark.asyncio
    async def test_cancellation_during_multi_step_run(self):
        agent = Agent(llm_model=LanguageModel())

        call_count = 0
        step_1_started = asyncio.Event()

        async def multi_step_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                step_1_started.set()
                await asyncio.sleep(10)
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "dummy_tool",
                                "arguments": "{}",
                            },
                        }
                    ],
                    "usage": None,
                }
            return {"content": "done", "tool_calls": None, "usage": None}

        @tool
        def dummy_tool() -> str:
            return "result"

        agent._call_llm = multi_step_call_llm
        agent.add_tools(dummy_tool)

        task = asyncio.create_task(agent.run("Multi-step query"))
        await step_1_started.wait()
        agent.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_multiple_runs_are_independent(self):
        agent = Agent(llm_model=LanguageModel())

        call_count = 0

        async def mock_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            return {
                "content": f"Response {call_count}",
                "tool_calls": None,
                "usage": None,
            }

        agent._call_llm = mock_call_llm

        r1 = await agent.run("Query 1")
        r2 = await agent.run("Query 2")
        assert r1 == "Response 1"
        assert r2 == "Response 2"
