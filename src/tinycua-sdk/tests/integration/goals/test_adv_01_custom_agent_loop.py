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
