"""Integration tests for Stage 8 custom agent loops.

This file contains:
1. Contract tests that DON'T require an LLM server (always run):
   - Custom loop override of Agent.run()
   - Cooperative cancellation via agent.is_cancelled
   - max_iterations inheritance

2. Real integration tests marked with @pytest.mark.integration (skipped
   when no LLM server is available):
   - Custom loop calling agent._call_llm() against the configured endpoint
   - ReAct-style loop with real LLM transport
   - Streaming lifecycle events through the real transport
   - PlanThenExecute two-phase loop with model override

The deterministic fake-LLM contract tests for _call_llm() access, ReAct
tool execution, PlanThenExecute, and streaming have been moved to
tests/unit/test_loop_custom.py for fast control-flow coverage (see ISSUE-001).
"""

from __future__ import annotations

import asyncio
import json
import os
import pytest

from tinycua_sdk import Agent, BaseLoop, LanguageModel, tool
from tinycua_sdk.agent.executor import ToolExecutor


# =============================================================================
# Contract Tests (always run, no LLM server required)
# =============================================================================


@pytest.mark.asyncio
async def test_custom_loop_overrides_default_execution():
    """Passing a BaseLoop subclass to Agent uses that loop for run().

    Note: This is an intentional Stage 8 acceptance smoke test at the
    integration-goals layer. The same basic custom-loop behavior is also
    covered at the unit level in tests/unit/test_loop.py::test_custom_loop.
    The overlap is deliberate: this test validates the user-facing contract
    (Agent accepts a loop= argument), while the unit test validates the
    internal dispatch.
    """
    class MyLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            return "custom result"

    agent = Agent(llm_model=LanguageModel(), loop=MyLoop())

    assert await agent.run("Hello") == "custom result"


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


# =============================================================================
# Real Integration Tests (require live LLM server, marked @pytest.mark.integration)
# =============================================================================


def _build_language_model() -> LanguageModel:
    """Build a LanguageModel from environment variables.

    Uses TINYCUA_* or LLM_* env vars, falling back to localhost defaults.
    """
    return LanguageModel(
        provider=os.environ.get("TINYCUA_PROVIDER", "openai-compatible"),
        base_url=os.environ.get(
            "TINYCUA_BASE_URL",
            os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1"),
        ),
        model_name=os.environ.get(
            "TINYCUA_MODEL",
            os.environ.get("LLM_MODEL", "qwen/qwen3.5-9b"),
        ),
        api_key=os.environ.get("TINYCUA_API_KEY", os.environ.get("LLM_API_KEY", "dummy")),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_custom_loop_calls_real_llm():
    """A custom loop can call agent._call_llm() against the configured endpoint.

    This test verifies real LLM transport through the SDK: a custom loop
    that calls agent._call_llm() receives a properly-formatted response
    from the live endpoint, without any monkeypatching.
    """
    class LLMLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            response = await agent._call_llm(messages, tools)
            content = response.get("content", "")
            return content if content else "[no content]"

    llm_model = _build_language_model()
    agent = Agent(llm_model=llm_model, loop=LLMLoop())

    result = await agent.run("Say hello in one word.", stream=False)
    assert isinstance(result, str)
    assert len(result) > 0
    # Verify we got a real response (not an empty or error string)
    assert result != "[no content]", "LLM returned no content"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_react_loop_real_llm():
    """A ReAct-style loop calls agent._call_llm() through the real transport.

    This test verifies the ReAct loop pattern works against the configured
    LLM endpoint. It creates a tool and a ReAct loop, then runs a query.
    The test does NOT force tool calls — it verifies the loop executes
    without error and returns a string response from the real model.
    """
    @tool
    def search(query: str) -> str:
        """Search for information. Returns simulated results."""
        return f"Simulated result for: {query}"

    class ReActLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            response = await agent._call_llm(messages, tools)
            content = response.get("content", "")
            if content:
                return content

            # Handle tool calls if the model makes them
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
                return final.get("content", "[no final answer]")

            return "[no response]"

    llm_model = _build_language_model()
    agent = Agent(llm_model=llm_model, tools=[search], loop=ReActLoop())

    result = await agent.run("Say hello in one word.", stream=False)
    assert isinstance(result, str)
    assert len(result) > 0
    assert result not in ("[no response]", "[no final answer]"), f"Unexpected result: {result}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_streaming_lifecycle_real_llm():
    """Streaming run verifies provider/SDK lifecycle events through real transport.

    This test creates an agent with the real LanguageModel and runs a
    streaming query. It verifies that the standard lifecycle events
    (response.created, response.in_progress, response.output_text.delta,
    response.usage, response.completed) are all present in the stream,
    delivered through the actual SDK transport without monkeypatching.
    """
    llm_model = _build_language_model()
    agent = Agent(llm_model=llm_model)

    stream = await agent.run("Say hello in one word.", stream=True)
    events = [event async for event in stream]
    event_types = [e["type"] for e in events]

    assert "response.created" in event_types, f"Missing response.created in {event_types}"
    assert "response.in_progress" in event_types, f"Missing response.in_progress in {event_types}"
    assert "response.output_text.delta" in event_types, f"Missing content delta in {event_types}"
    assert "response.usage" in event_types, f"Missing response.usage in {event_types}"
    assert "response.completed" in event_types, f"Missing response.completed in {event_types}"

    # Verify order: created -> in_progress -> deltas -> completed
    created_idx = event_types.index("response.created")
    in_progress_idx = event_types.index("response.in_progress")
    completed_idx = event_types.index("response.completed")

    assert created_idx < in_progress_idx, \
        f"response.created ({created_idx}) should come before response.in_progress ({in_progress_idx})"
    assert in_progress_idx < completed_idx, \
        f"response.in_progress ({in_progress_idx}) should come before response.completed ({completed_idx})"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_model_override_real_llm():
    """Custom loop can pass a copied LanguageModel through _call_llm(llm_model=...).

    This test verifies the model override path against the real endpoint:
    a custom loop copies the agent's LanguageModel with a modified temperature
    and passes it through _call_llm(llm_model=...). The test verifies the
    override reaches the real client by checking the response is valid.

    The full PlanThenExecute two-phase contract (plan + execute) is covered
    deterministically in tests/unit/test_loop_custom.py (test_plan_then_execute_loop_works).
    """
    class ModelOverrideLoop(BaseLoop):
        async def run(self, agent, messages, tools, override_instructions=None, stream=False):
            # Verify model override works: copy with different temperature
            override_model = agent.llm_model.model_copy(update={"temperature": 0.3})
            response = await agent._call_llm(messages, llm_model=override_model)
            return response.get("content") or ""

    llm_model = _build_language_model()
    agent = Agent(llm_model=llm_model, loop=ModelOverrideLoop())

    result = await agent.run("Say hello in one word.", stream=False)
    assert isinstance(result, str)
    assert len(result) > 0, f"Model returned empty content: {result!r}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_custom_loop_uses_public_helpers():
    """Custom loop using public helpers produces correct tool-calling result.

    Tests the new ``build_system_message()``, ``process_tool_calls()``, and
    ``last_assistant_content()`` public helpers against a real LLM endpoint.
    The tool_choice on the LanguageModel forces the LLM to call the tool.
    """
    @tool
    def get_weather(city: str) -> str:
        """Get weather for a city."""
        return f"Weather in {city}: sunny"

    class CustomToolLoop(BaseLoop):
        def __init__(self, **kwargs):
            self.initial_llm_model = kwargs.pop("initial_llm_model", None)
            super().__init__(**kwargs)
            self.called_build_system_message = False
            self.called_process_tool_calls = False
            self.called_last_assistant_content = False
            self.last_working_messages: list[dict] = []

        async def run(self, agent, messages, tools,
                      override_instructions=None, stream=False):
            system_msg = self.build_system_message(agent, override_instructions)
            self.called_build_system_message = True
            working = [system_msg] + list(messages)
            tool_call_count = 0
            llm_calls = 0

            for _ in range(self.max_iterations):
                if agent.is_cancelled:
                    raise asyncio.CancelledError()

                if llm_calls == 0 and self.initial_llm_model is not None:
                    response = await agent._call_llm(working, tools, llm_model=self.initial_llm_model)
                else:
                    response = await agent._call_llm(working, tools)
                llm_calls += 1
                content = response.get("content")
                tool_calls = response.get("tool_calls")

                if tool_calls:
                    tool_call_count, max_reached = await self.process_tool_calls(
                        agent, tools, tool_calls, working, tool_call_count,
                        assistant_content=content or "",
                    )
                    self.called_process_tool_calls = True
                    if max_reached:
                        self.last_working_messages = list(working)
                        self.called_last_assistant_content = True
                        return self.last_assistant_content(working) or "[max tool calls]"
                else:
                    if content:
                        working.append({"role": "assistant", "content": content})
                    self.last_working_messages = list(working)
                    self.called_last_assistant_content = True
                    return self.last_assistant_content(working) or ""

            self.last_working_messages = list(working)
            self.called_last_assistant_content = True
            return self.last_assistant_content(working) or "[max iterations]"

    llm_model = _build_language_model()
    llm_model_with_tc = llm_model.model_copy(
        update={"tool_choice": {"type": "function", "name": "get_weather"}},
    )
    loop = CustomToolLoop(initial_llm_model=llm_model_with_tc)
    agent = Agent(
        llm_model=llm_model,
        tools=[get_weather],
        loop=loop,
    )

    result = await agent.run("What is the weather in Tokyo?")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "[max tool calls]" not in result
    assert "[max iterations]" not in result

    assert loop.called_build_system_message, "build_system_message was not called"
    assert loop.called_process_tool_calls, "process_tool_calls was not called"
    assert loop.called_last_assistant_content, "last_assistant_content was not called"

    helper_call_msgs = [
        m for m in loop.last_working_messages
        if isinstance(m, dict) and m.get("type") == "function_call_output"
    ]
    assert len(helper_call_msgs) > 0, (
        "No function_call_output messages found — helpers did not execute tool calls"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_custom_streaming_loop_uses_public_helpers():  # noqa: C901
    """Custom streaming loop using public helpers works end-to-end.

    Tests the new ``process_stream_iteration()`` and
    ``process_stream_tool_calls()`` public helpers against a real LLM.
    """
    @tool
    def get_weather(city: str) -> str:
        """Get weather for a city."""
        return f"Weather in {city}: sunny"

    class CustomStreamingLoop(BaseLoop):
        def __init__(self, **kwargs):
            self.initial_llm_model = kwargs.pop("initial_llm_model", None)
            super().__init__(**kwargs)
            self.called_build_system_message = False
            self.called_process_stream_iteration = False
            self.called_process_stream_tool_calls = False
            self.last_working_messages: list[dict] = []

        async def run(self, agent, messages, tools,
                      override_instructions=None, stream=False):
            async def _stream():
                system_msg = self.build_system_message(agent, override_instructions)
                self.called_build_system_message = True
                working = [system_msg] + list(messages)
                tool_call_count = 0
                cumulative_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                usage_settled_ids = set()
                finish_reason = "completed"
                cancelled = False
                provider_failed = False
                completed_by_provider = False
                llm_calls = 0

                try:
                    for _ in range(self.max_iterations):
                        if agent.is_cancelled:
                            yield {"type": "response.cancelled"}
                            cancelled = True
                            break

                        content_parts = []
                        tool_calls_buffer = {}
                        usage_settled_ids.clear()

                        if llm_calls == 0 and self.initial_llm_model is not None:
                            llm_stream = await agent._call_llm(working, tools, stream=True, llm_model=self.initial_llm_model)
                        else:
                            llm_stream = await agent._call_llm(working, tools, stream=True)
                        llm_calls += 1

                        iteration_completed = False
                        async for event in self.process_stream_iteration(
                            llm_stream, agent, content_parts, tool_calls_buffer,
                            cumulative_usage, usage_settled_ids,
                        ):
                            self.called_process_stream_iteration = True
                            if event["type"] == "response.completed":
                                iteration_completed = True
                            if event["type"] == "response.cancelled":
                                cancelled = True
                            elif event["type"] in ("response.failed", "error"):
                                provider_failed = True
                            yield event
                        completed_by_provider = iteration_completed

                        if cancelled or provider_failed:
                            break

                        combined = "".join(content_parts)
                        tool_calls_list = list(tool_calls_buffer.values())

                        if tool_calls_list:
                            tool_call_count, max_reached = await self.process_stream_tool_calls(
                                agent, tools, tool_calls_list, working, tool_call_count,
                                combined_content=combined,
                            )
                            self.called_process_stream_tool_calls = True
                            if max_reached:
                                finish_reason = "max_tool_calls"
                                break
                        else:
                            working.append({"role": "assistant", "content": combined})
                            break
                    else:
                        finish_reason = "max_iterations"
                except Exception as e:
                    self.last_working_messages = list(working)
                    yield {"type": "response.failed", "error": {"message": str(e)}}
                    return

                self.last_working_messages = list(working)
                yield {"type": "response.usage", "usage": dict(cumulative_usage)}
                if not completed_by_provider and not provider_failed and not cancelled:
                    yield {"type": "response.completed", "finish_reason": finish_reason}

            return _stream()

    llm_model = _build_language_model()
    llm_model_with_tc = llm_model.model_copy(
        update={"tool_choice": {"type": "function", "name": "get_weather"}},
    )
    loop = CustomStreamingLoop(initial_llm_model=llm_model_with_tc)
    agent = Agent(llm_model=llm_model, tools=[get_weather], loop=loop)

    stream = await agent.run("What is the weather in Tokyo?", stream=True)
    events = [e async for e in stream]
    event_types = [e["type"] for e in events]

    assert "response.created" in event_types
    assert "response.completed" in event_types
    assert "response.failed" not in event_types, "Stream ended with failure"

    completed_events = [e for e in events if e["type"] == "response.completed"]
    if completed_events:
        assert completed_events[-1].get("finish_reason") not in ("max_tool_calls", "max_iterations"), (
            "Stream exited via max limit fallback instead of completing naturally"
        )

    assert loop.called_build_system_message, "build_system_message was not called"
    assert loop.called_process_stream_iteration, "process_stream_iteration was not called"
    assert loop.called_process_stream_tool_calls, "process_stream_tool_calls was not called"

    helper_call_msgs = [
        m for m in loop.last_working_messages
        if isinstance(m, dict) and m.get("type") == "function_call_output"
    ]
    assert len(helper_call_msgs) > 0, (
        "No function_call_output messages found — streaming helpers did not execute tool calls"
    )
