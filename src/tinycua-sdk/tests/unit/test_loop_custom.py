"""Contract tests for BaseLoop subclassing — fast, deterministic, no LLM server.

These tests verify the BaseLoop extension point contract using deterministic
fake LLM responses. They are unit/contract tests, not integration tests —
they validate control flow against stubs, not against a live LLM endpoint.

Moved from tests/integration/goals/test_adv_01_custom_agent_loop.py as part
of the Stage 8 cleanup (ISSUE-001): fake-LLM scenarios belong in unit tests
for fast control-flow coverage; real transport coverage is in
tests/integration/goals/test_adv_01_custom_agent_loop.py with the
@pytest.mark.integration marker.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest

from tinycua_sdk import Agent, BaseLoop, LanguageModel, tool
from tinycua_sdk.agent.executor import ToolExecutor


class TestCustomLoopContract:
    """Contract tests for the BaseLoop subclassing contract.

    These tests use fake _call_llm() implementations to verify that
    custom loops can:
    - Call agent._call_llm() directly
    - Execute ReAct-style tool loops
    - Implement PlanThenExecute two-phase loops with model override
    - Handle streaming lifecycle events
    """

    @pytest.mark.asyncio
    async def test_custom_loop_can_call_agent_call_llm(self):
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
    async def test_react_style_custom_loop_can_execute_tool_and_continue(self):
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
                    call_id = tc.get("call_id", tc["id"])
                    messages.append({
                        "type": "function_call",
                        "call_id": call_id,
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    })
                    messages.append({
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": str(result),
                    })
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
        second_messages = calls[1][0]
        assert any(
            msg.get("type") == "function_call_output" and msg.get("call_id") == "call_1"
            for msg in second_messages
        ), "Expected function_call_output with call_id='call_1' in the follow-up call"

    @pytest.mark.asyncio
    async def test_plan_then_execute_loop_works(self):
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
                                call_id = tc.get("call_id", tc["id"])
                                exec_messages.append({
                                    "type": "function_call",
                                    "call_id": call_id,
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                })
                                exec_messages.append({
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": str(result),
                                })
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
            assert any(
                msg.get("type") == "function_call_output" and msg.get("call_id") == "call_1"
                for msg in messages
            ), "Expected function_call_output with call_id='call_1' in PlanThenExecute follow-up"
            return {"content": "Tokyo has sunny weather.", "tool_calls": None}

        agent._call_llm = fake_call_llm

        result = await agent.run("What is the weather in Tokyo?")
        assert result == "Tokyo has sunny weather."

    @pytest.mark.asyncio
    async def test_default_streaming_loop_emits_in_progress_event(self):
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
