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

from tinycua_sdk import Agent, BaseLoop, LanguageModel, Skill, tool
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
                    call_id = tc.get("call_id") or tc.get("id")
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
                                call_id = tc.get("call_id") or tc.get("id")
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
        """BaseLoop stream output includes the deferred response.in_progress event.

        Note: This test intentionally overlaps with
        tests/unit/test_loop.py::test_in_progress_emitted_before_delta and
        tests/unit/test_agent_streaming.py. The overlap is deliberate:
        this test validates the in-progress ordering contract for the custom
        BaseLoop subclassing path specifically, while the other tests cover
        the default loop path and agent-level streaming.
        """
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


class TestCustomPublicHelpers:
    """Tests for new public helper methods on BaseLoop.

    These tests verify that custom loop subclasses can call the new public
    helper methods directly in their own run() override. They are the
    always-run RED gate — they must pass without an LLM server.
    """

    @pytest.mark.asyncio
    async def test_custom_loop_calls_build_system_message(self):
        """Custom loop subclass can call build_system_message() directly."""
        class HelperLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                system_msg = self.build_system_message(agent, override_instructions)
                return system_msg["content"]

        agent = Agent(
            instructions="You are helpful.",
            llm_model=LanguageModel(),
        )
        loop = HelperLoop()
        result = await loop.run(
            agent, [{"role": "user", "content": "hi"}], [],
        )
        assert "You are helpful." in result

    @pytest.mark.asyncio
    async def test_custom_loop_calls_build_system_message_with_skills(self):
        """build_system_message includes skill instructions."""
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

        class HelperLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                system_msg = self.build_system_message(agent, override_instructions)
                return system_msg["content"]

        loop = HelperLoop()
        result = await loop.run(
            agent, [{"role": "user", "content": "hi"}], [],
        )
        assert "[coder]" in result
        assert "Write clean code." in result

    @pytest.mark.asyncio
    async def test_custom_loop_calls_process_tool_calls(self):
        """Custom loop can call process_tool_calls() with fake tool calls."""
        @tool
        def get_time() -> str:
            return "12:00"

        class ToolCallLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                system_msg = self.build_system_message(agent, override_instructions)
                working = [system_msg] + list(messages)

                tool_calls = [
                    {"id": "call_1", "name": "get_time", "arguments": "{}"},
                ]
                count, max_reached = await self.process_tool_calls(
                    agent, tools, tool_calls, working, 0,
                )
                assert count == 1, f"Expected count=1, got {count}"
                assert max_reached is False
                assert len(working) >= 3
                # Verify function_call_output was added
                has_output = any(
                    m.get("type") == "function_call_output"
                    for m in working
                )
                assert has_output, "No function_call_output found in working messages"
                return "ok"

        agent = Agent(llm_model=LanguageModel(), tools=[get_time])
        loop = ToolCallLoop()
        result = await loop.run(
            agent, [{"role": "user", "content": "time?"}], [get_time],
        )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_custom_loop_calls_process_tool_calls_with_assistant_content(self):
        """process_tool_calls prepends assistant content before function_call."""
        @tool
        def get_time() -> str:
            return "12:00"

        class ToolCallLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                system_msg = self.build_system_message(agent, override_instructions)
                working = [system_msg] + list(messages)

                tool_calls = [
                    {"id": "call_1", "name": "get_time", "arguments": "{}"},
                ]
                count, max_reached = await self.process_tool_calls(
                    agent, tools, tool_calls, working, 0,
                    assistant_content="Let me check the time.",
                )
                assert count == 1
                assert max_reached is False
                # Verify assistant message was prepended before function_call
                assistant_idx = next(
                    i for i, m in enumerate(working)
                    if m.get("role") == "assistant"
                )
                func_call_idx = next(
                    i for i, m in enumerate(working)
                    if m.get("type") == "function_call"
                )
                assert assistant_idx < func_call_idx, (
                    "Assistant message should come before function_call"
                )
                return "ok"

        agent = Agent(llm_model=LanguageModel(), tools=[get_time])
        loop = ToolCallLoop()
        result = await loop.run(
            agent, [{"role": "user", "content": "time?"}], [get_time],
        )
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_custom_loop_calls_process_tool_calls_max_reached(self):
        """process_tool_calls respects max_tool_calls guard."""
        @tool
        def dummy() -> str:
            return "ok"

        from tinycua_sdk import AgentPolicy
        policy = AgentPolicy(max_tool_calls=1)

        class ToolCallLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                system_msg = self.build_system_message(agent, override_instructions)
                working = [system_msg] + list(messages)

                tool_calls = [
                    {"id": "call_1", "name": "dummy", "arguments": "{}"},
                    {"id": "call_2", "name": "dummy", "arguments": "{}"},
                ]
                count, max_reached = await self.process_tool_calls(
                    agent, tools, tool_calls, working, 0,
                )
                assert count == 1, f"Expected count=1 (only 1 executed), got {count}"
                assert max_reached is True
                return "maxed"

        agent = Agent(llm_model=LanguageModel(), tools=[dummy], policy=policy)
        loop = ToolCallLoop()
        result = await loop.run(
            agent, [{"role": "user", "content": "go"}], [dummy],
        )
        assert result == "maxed"

    @pytest.mark.asyncio
    async def test_custom_loop_calls_process_stream_iteration(self):
        """Custom loop can call process_stream_iteration() with a fake stream.

        Covers lifecycle event ordering, content accumulation, tool-call
        buffering, and usage settlement.
        """
        class StreamLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                async def fake_llm_stream():
                    yield {"type": "response.created", "response": {"id": "r_1"}}
                    yield {"type": "response.in_progress"}
                    yield {"type": "response.output_text.delta", "delta": "Hello", "item_id": "1"}
                    yield {"type": "response.usage", "usage": {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}}

                content_parts: list[str] = []
                tool_calls_buffer: dict = {}
                cumulative_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                usage_settled_ids: set[str] = set()

                events: list[dict] = []
                async for event in self.process_stream_iteration(
                    fake_llm_stream(), agent, content_parts, tool_calls_buffer,
                    cumulative_usage, usage_settled_ids,
                ):
                    events.append(event)

                # Verify lifecycle events
                event_types = [e["type"] for e in events]
                assert "response.created" in event_types
                assert "response.in_progress" in event_types
                assert "response.output_text.delta" in event_types

                # Content accumulated
                assert "".join(content_parts) == "Hello"

                # Usage accumulated
                assert cumulative_usage["total_tokens"] == 8

                return "streamed"

        agent = Agent(llm_model=LanguageModel())
        loop = StreamLoop()
        result = await loop.run(agent, [{"role": "user", "content": "hi"}], [])
        assert result == "streamed"

    @pytest.mark.asyncio
    async def test_custom_loop_calls_process_stream_iteration_tool_calls(self):
        """process_stream_iteration buffers tool calls from stream."""
        class StreamToolLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                async def fake_llm_stream():
                    yield {
                        "type": "tool_call.started",
                        "id": "call_1",
                        "call_id": "call_1",
                        "name": "get_time",
                    }
                    yield {
                        "type": "tool_call.arguments.done",
                        "id": "call_1",
                        "arguments": "{}",
                    }

                content_parts: list[str] = []
                tool_calls_buffer: dict = {}
                cumulative_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                usage_settled_ids: set[str] = set()

                events: list[dict] = []
                async for event in self.process_stream_iteration(
                    fake_llm_stream(), agent, content_parts, tool_calls_buffer,
                    cumulative_usage, usage_settled_ids,
                ):
                    events.append(event)

                # Tool calls should be buffered
                assert len(tool_calls_buffer) == 1
                assert tool_calls_buffer["call_1"]["name"] == "get_time"
                return "tool buffered"

        agent = Agent(llm_model=LanguageModel())
        loop = StreamToolLoop()
        result = await loop.run(agent, [{"role": "user", "content": "time?"}], [])
        assert result == "tool buffered"

    @pytest.mark.asyncio
    async def test_custom_loop_calls_process_stream_iteration_cancellation(self):
        """process_stream_iteration handles cancellation via agent."""
        class CancelStreamLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                async def fake_llm_stream():
                    yield {"type": "response.output_text.delta", "delta": "Hello", "item_id": "1"}

                content_parts: list[str] = []
                tool_calls_buffer: dict = {}
                cumulative_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                usage_settled_ids: set[str] = set()

                agent._cancelled = True
                events: list[dict] = []
                async for event in self.process_stream_iteration(
                    fake_llm_stream(), agent, content_parts, tool_calls_buffer,
                    cumulative_usage, usage_settled_ids,
                ):
                    events.append(event)

                event_types = [e["type"] for e in events]
                assert "response.cancelled" in event_types
                return "cancelled"

        agent = Agent(llm_model=LanguageModel())
        loop = CancelStreamLoop()
        result = await loop.run(agent, [{"role": "user", "content": "hi"}], [])
        assert result == "cancelled"

    @pytest.mark.asyncio
    async def test_custom_loop_calls_process_stream_tool_calls(self):
        """Custom loop can call process_stream_tool_calls() with fake tool calls."""
        @tool
        def get_time() -> str:
            return "12:00"

        class StreamToolExecLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                system_msg = self.build_system_message(agent, override_instructions)
                working = [system_msg] + list(messages)

                tool_calls_list = [
                    {"id": "call_1", "name": "get_time", "arguments": "{}"},
                ]
                count, max_reached = await self.process_stream_tool_calls(
                    agent, tools, tool_calls_list, working, 0,
                )
                assert count == 1
                assert max_reached is False
                assert len(working) >= 3
                has_func_call = any(
                    m.get("type") == "function_call"
                    for m in working
                )
                has_func_output = any(
                    m.get("type") == "function_call_output"
                    for m in working
                )
                assert has_func_call, "No function_call found"
                assert has_func_output, "No function_call_output found"
                return "executed"

        agent = Agent(llm_model=LanguageModel(), tools=[get_time])
        loop = StreamToolExecLoop()
        result = await loop.run(
            agent, [{"role": "user", "content": "time?"}], [get_time],
        )
        assert result == "executed"

    @pytest.mark.asyncio
    async def test_custom_loop_calls_process_stream_tool_calls_with_content(self):
        """process_stream_tool_calls can accept combined_content."""
        @tool
        def get_time() -> str:
            return "12:00"

        class StreamToolContentLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                system_msg = self.build_system_message(agent, override_instructions)
                working = [system_msg] + list(messages)

                tool_calls_list = [
                    {"id": "call_1", "name": "get_time", "arguments": "{}"},
                ]
                count, max_reached = await self.process_stream_tool_calls(
                    agent, tools, tool_calls_list, working, 0,
                    combined_content="The time is ",
                )
                assert count == 1
                assert max_reached is False
                # Assistant message with combined_content should be present
                assistant_msgs = [m for m in working if m.get("role") == "assistant"]
                assert len(assistant_msgs) >= 1
                assert assistant_msgs[0].get("content") == "The time is "
                return "content ok"

        agent = Agent(llm_model=LanguageModel(), tools=[get_time])
        loop = StreamToolContentLoop()
        result = await loop.run(
            agent, [{"role": "user", "content": "time?"}], [get_time],
        )
        assert result == "content ok"

    @pytest.mark.asyncio
    async def test_custom_loop_calls_last_assistant_content(self):
        """Custom loop can call last_assistant_content() directly."""
        class ContentLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                working = list(messages)
                working.append({"role": "assistant", "content": "Final answer."})
                result = self.last_assistant_content(working)
                return result

        agent = Agent(llm_model=LanguageModel())
        loop = ContentLoop()
        result = await loop.run(
            agent, [{"role": "user", "content": "hi"}], [],
        )
        assert result == "Final answer."

    @pytest.mark.asyncio
    async def test_custom_loop_calls_last_assistant_content_empty(self):
        """last_assistant_content returns empty string when no assistant messages."""
        class ContentLoop(BaseLoop):
            async def run(self, agent, messages, tools,
                          override_instructions=None, stream=False):
                # No assistant messages
                return self.last_assistant_content(list(messages))

        agent = Agent(llm_model=LanguageModel())
        loop = ContentLoop()
        result = await loop.run(
            agent, [{"role": "user", "content": "hi"}], [],
        )
        assert result == ""
