"""Integration tests for agent calling (GS-03).

Converts targets: 01_run_returns_string, 02_run_with_history,
03_instruction_override, 04_cancellation
"""

import asyncio
import pytest

from tinycua_sdk import Agent, LanguageModel, tool


class TestGS03AgentCalling:
    """Test suite for Agent.run() calling patterns."""

    @pytest.mark.asyncio
    async def test_gs_01_run_returns_string(self, mock_llm_client):
        """Target 3.1: Agent.run returns a string with stream='off'."""
        agent = Agent(llm_model=LanguageModel())
        response = await agent.run("What is the capital of France?", stream="off")
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_gs_02_run_with_message_history(self, mock_llm_client):
        """Target 3.2: Agent.run respects prior message history."""
        agent = Agent(llm_model=LanguageModel())
        history = [
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Nice to meet you!"},
        ]
        response = await agent.run("What is my name?", messages=history, stream="off")
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_gs_03_run_with_instruction_override(self, mock_llm_client):
        """Target 3.3: Runtime instruction override works."""
        agent = Agent(
            llm_model=LanguageModel(),
            instructions="You are a helpful assistant.",
        )
        response = await agent.run(
            "Tell me a joke.",
            instructions="You are a pirate. Be funny and concise.",
            stream="off",
        )
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_gs_04_cancellation(self):
        """Target 3.4: Agent.cancel() stops an in-flight run."""
        agent = Agent(llm_model=LanguageModel())

        call_count = 0
        step_1_started = asyncio.Event()

        async def multi_step_call_llm(messages, tools):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                step_1_started.set()
                await asyncio.sleep(0.1)
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

        task = asyncio.create_task(
            agent.run("Write a long essay about cheese.")
        )
        await step_1_started.wait()
        agent.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
