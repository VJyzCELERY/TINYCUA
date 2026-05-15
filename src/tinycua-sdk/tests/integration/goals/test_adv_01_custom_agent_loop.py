"""Integration tests for Stage 8 custom agent loops.

Tests the BaseLoop extension point for SDK consumers:
- Custom loop override of Agent.run()
- Protected _call_llm() access from custom loops
- Cooperative cancellation via agent.is_cancelled
- max_iterations inheritance
- ReAct-style loop with tool execution
- PlanThenExecute two-phase loop with model override
- Streaming lifecycle event completeness (response.in_progress)
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest

from tinycua_sdk import Agent, BaseLoop, LanguageModel, tool
from tinycua_sdk.agent.executor import ToolExecutor


@pytest.mark.asyncio
async def test_custom_loop_overrides_default_execution():
    """Passing a BaseLoop subclass to Agent uses that loop for run()."""

    class MyLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            return "custom result"

    agent = Agent(llm_model=LanguageModel(), loop=MyLoop())

    assert await agent.run("Hello") == "custom result"


@pytest.mark.asyncio
async def test_custom_loop_can_call_agent_call_llm():
    """Custom loops can reuse the agent LLM transport helper."""

    class LLMLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            response = await agent._call_llm(messages, tools)
            return response.get("content", "")

    agent = Agent(llm_model=LanguageModel(), loop=LLMLoop())

    async def fake_call_llm(messages, tools=None, stream=False, llm_model=None):
        assert messages[-1] == {"role": "user", "content": "Say hi."}
        assert tools == []
        return {"content": "hi", "tool_calls": None, "usage": None}

    agent._call_llm = fake_call_llm

    assert await agent.run("Say hi.") == "hi"


@pytest.mark.asyncio
async def test_custom_loop_can_respect_agent_cancellation():
    """A custom loop can observe agent.is_cancelled and exit cooperatively."""

    class SlowLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            for _ in range(100):
                if agent.is_cancelled:
                    return "[cancelled]"
                await asyncio.sleep(0.001)
            return "done"

    agent = Agent(llm_model=LanguageModel(), loop=SlowLoop())
    task = asyncio.create_task(agent.run("Wait"))

    await asyncio.sleep(0.01)
    agent.cancel()

    assert await task == "[cancelled]"


@pytest.mark.asyncio
async def test_custom_loop_can_use_max_iterations():
    """Custom loops inherit and can rely on self.max_iterations."""

    class CountingLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            count = 0
            for _ in range(self.max_iterations):
                count += 1
            return f"ran {count} times"

    agent = Agent(llm_model=LanguageModel(), loop=CountingLoop(max_iterations=3))

    assert await agent.run("Hello") == "ran 3 times"


@pytest.mark.asyncio
async def test_react_style_custom_loop_can_execute_tool_and_continue():
    """A ReAct-style loop can call the LLM, execute a tool, and continue."""

    @tool
    def weather(city: str) -> str:
        """Get weather for a city."""
        return f"Sunny in {city}."

    class ReActLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            response = await agent._call_llm(messages, tools)
            if response.get("tool_calls"):
                tc = response["tool_calls"][0]
                tool_obj = next(t for t in tools if t.name == tc["name"])
                arguments = json.loads(tc["arguments"])
                result = await ToolExecutor.execute(tool_obj, arguments, agent)
                messages.append({"role": "tool", "content": str(result), "name": tc["name"]})
                final = await agent._call_llm(messages)
                return final.get("content", "")
            return response.get("content", "")

    agent = Agent(llm_model=LanguageModel(), tools=[weather], loop=ReActLoop())
    calls = []

    async def fake_call_llm(messages, tools=None, stream=False, llm_model=None):
        calls.append((messages, tools))
        if len(calls) == 1:
            return {
                "content": "Act: weather",
                "tool_calls": [{"id": "call_1", "name": "weather", "arguments": '{"city": "Tokyo"}'}],
            }
        return {"content": "It is sunny in Tokyo.", "tool_calls": None}

    agent._call_llm = fake_call_llm

    assert await agent.run("What is the weather in Tokyo?") == "It is sunny in Tokyo."


@pytest.mark.asyncio
async def test_plan_then_execute_loop_works():
    """A PlanThenExecuteLoop can produce a plan and execute steps."""

    @tool
    def search(query: str) -> str:
        """Search for information."""
        return f"Results for {query}."

    class PlanThenExecuteLoop(BaseLoop):
        def __init__(self, max_iterations=5, plan_temperature=0.3):
            super().__init__(max_iterations=max_iterations)
            self.plan_temperature = plan_temperature

        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            # Phase 1: Planning
            plan_messages = messages + [{
                "role": "system",
                "content": "First, outline a step-by-step plan. Do not execute yet.",
            }]
            plan_model = agent.llm_model.model_copy(update={"temperature": self.plan_temperature})
            plan_response = await agent._call_llm(plan_messages, llm_model=plan_model)
            plan = plan_response.get("content", "")

            # Phase 2: Execution
            exec_messages = messages + [
                {"role": "assistant", "content": plan},
                {"role": "system", "content": "Now execute the plan above step by step."},
            ]

            for _ in range(self.max_iterations):
                if agent.is_cancelled:
                    return "[cancelled]"

                response = await agent._call_llm(exec_messages, tools)
                content = response.get("content", "")
                exec_messages.append({"role": "assistant", "content": content})

                if not response.get("tool_calls"):
                    return content

                for tc in response["tool_calls"]:
                    tool_name = tc["name"]
                    arguments = json.loads(tc["arguments"])
                    for t in tools:
                        if t.name == tool_name:
                            result = await ToolExecutor.execute(t, arguments, agent)
                            exec_messages.append({"role": "tool", "content": str(result), "name": tool_name})
                            break

            return "[max iterations reached]"

    agent = Agent(llm_model=LanguageModel(), tools=[search], loop=PlanThenExecuteLoop(max_iterations=3))
    calls = []

    async def fake_call_llm(messages, tools=None, stream=False, llm_model=None):
        calls.append((messages, tools))
        if len(calls) == 1:
            # Phase 1: return a plan with model override assertion
            assert llm_model is not None
            assert llm_model.temperature == 0.3
            return {"content": "Plan: 1. Search for Tokyo weather.", "tool_calls": None}
        if len(calls) == 2:
            # Phase 2: execute tool
            return {
                "content": "",
                "tool_calls": [{"id": "call_1", "name": "search", "arguments": '{"query": "Tokyo weather"}'}],
            }
        # Phase 2 follow-up: final answer
        return {"content": "Tokyo has sunny weather.", "tool_calls": None}

    agent._call_llm = fake_call_llm

    result = await agent.run("What is the weather in Tokyo?")
    assert result == "Tokyo has sunny weather."


@pytest.mark.asyncio
async def test_default_streaming_loop_emits_in_progress_event():
    """BaseLoop stream output includes the deferred response.in_progress event."""

    async def fake_call_llm(messages, tools=None, stream=False, llm_model=None):
        assert stream is True

        async def chunks() -> AsyncIterator[dict]:
            yield {"type": "response.output_text.delta", "delta": "Hello", "item_id": "msg_1"}

        return chunks()

    agent = Agent(llm_model=LanguageModel())
    agent._call_llm = fake_call_llm

    stream = await agent.run("Hello", stream=True)
    events = [event async for event in stream]
    event_types = [event["type"] for event in events]

    assert event_types.index("response.created") < event_types.index("response.in_progress")
    assert event_types.index("response.in_progress") < event_types.index("response.output_text.delta")
    assert "response.usage" in event_types
    assert "response.completed" in event_types
