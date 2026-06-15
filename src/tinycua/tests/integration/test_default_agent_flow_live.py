"""Live default create_tinycua_agent().run() contract tests.

These tests are opt-in because they require a local OpenAI-compatible server.
"""

from __future__ import annotations

import os
from pathlib import Path

import dotenv
import pytest
from tinycua_sdk.agent.llm_model import LanguageModel

from tinycua.config.session_config import InteractionPolicy, SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.models.digested_information import DigestedInformation


pytestmark = pytest.mark.live_llm

_WORKER_PROMPT = (
    "This request must use worker mode. If a route tool is available, call "
    "select_query_route with route=worker. Create a concise three-step task "
    "plan for migrating a project to a new Python package manager."
)


def _require_live_llm() -> None:
    dotenv.load_dotenv(
        Path(__file__).resolve().parent.parent.parent / ".env.test",
        override=False,
    )
    if os.environ.get("TINYCUA_LIVE_LLM") != "1":
        pytest.skip("Set TINYCUA_LIVE_LLM=1 to run live LLM contract tests")

    required = {
        "OPENAI_CHAT_COMPLETIONS_BASE_URL": "http://localhost:1234/v1",
        "OPENAI_CHAT_COMPLETIONS_MODEL": "qwen/qwen3.5-4b",
        "OPENAI_CHAT_COMPLETIONS_API_KEY": "tinycua-local-test",
        "TINYCUA_BASE_URL": "http://localhost:1234/v1",
        "TINYCUA_MODEL": "qwen/qwen3.5-4b",
        "TINYCUA_API_KEY": "tinycua-local-test",
    }
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        pytest.fail(f"Missing live LLM environment variables: {', '.join(missing)}")
    mismatched = {
        name: os.environ.get(name)
        for name, expected in required.items()
        if os.environ.get(name) != expected
    }
    if mismatched:
        pytest.fail(f"Live LLM environment variables must match local contract: {mismatched}")


def _live_llm_model() -> LanguageModel:
    """Return the explicit local OpenAI Chat Completions model config."""
    return LanguageModel(
        provider="openai-chat-completions",
        model_name=os.environ["OPENAI_CHAT_COMPLETIONS_MODEL"],
        base_url=os.environ["OPENAI_CHAT_COMPLETIONS_BASE_URL"],
        api_key=os.environ["OPENAI_CHAT_COMPLETIONS_API_KEY"],
    )


@pytest.mark.asyncio
async def test_default_agent_live_passthrough_flow() -> None:
    """Public factory starts with QueryAnalyst and exposes route tools live."""
    _require_live_llm()

    agent = create_tinycua_agent(
        session_config=SessionConfig(
            interaction_policy=InteractionPolicy(uncertain_strategy="route_worker")
        ),
        llm_model=_live_llm_model(),
    )
    result = await agent.run("Say hello in one short sentence.")

    trace = agent.loop.get_execution_trace()
    assert isinstance(result, str)
    assert result.strip()
    assert trace[0]["node_id"] == "query_analyst"
    assert trace[0].get("route_label") in {"passthrough", "worker"}
    assert trace[0].get("route_source") in {"tool_call", "content_or_fallback"}
    assert "select_query_route" in trace[0].get("resolved_tool_names", [])
    if trace[0].get("route_label") == "passthrough":
        assert "worker" not in [entry["node_id"] for entry in trace]
        assert "digester" not in [entry["node_id"] for entry in trace]
    assert trace[-1]["node_id"] == "response"


@pytest.mark.asyncio
async def test_default_agent_live_uncertain_non_hitl_completes() -> None:
    """HITL-disabled uncertain handling completes without blocking."""
    _require_live_llm()

    session_config = SessionConfig(
        interaction_policy=InteractionPolicy(
            hitl_enabled=False,
            uncertain_strategy="fallback_response",
        )
    )
    agent = create_tinycua_agent(
        session_config=session_config,
        llm_model=_live_llm_model(),
    )
    result = await agent.run("Maybe do the thing we discussed earlier.")

    assert isinstance(result, str)
    trace = agent.loop.get_execution_trace()
    assert trace[0]["node_id"] == "query_analyst"
    assert "select_query_route" in trace[0].get("resolved_tool_names", [])
    assert trace[-1]["node_id"] == "response"


@pytest.mark.asyncio
async def test_default_agent_live_worker_flow_runs_digester_before_worker() -> None:
    """Live worker-mode path spawns Digester before Worker and terminates."""
    _require_live_llm()

    agent = create_tinycua_agent(
        session_config=SessionConfig(
            interaction_policy=InteractionPolicy(uncertain_strategy="route_worker")
        ),
        llm_model=_live_llm_model(),
    )
    result = await agent.run(_WORKER_PROMPT)

    trace = agent.loop.get_execution_trace()
    node_ids = [entry["node_id"] for entry in trace]
    assert isinstance(result, str)
    assert result.strip()
    assert trace[0]["node_id"] == "query_analyst"
    assert trace[0].get("route_label") == "worker"
    assert trace[0].get("route_source") in {"tool_call", "content_or_fallback"}
    assert "select_query_route" in trace[0].get("resolved_tool_names", [])
    assert "digester" in node_ids
    assert "worker" in node_ids
    assert node_ids.index("digester") < node_ids.index("worker")
    worker_trace = trace[node_ids.index("worker")]
    assert "select_worker_route" in worker_trace.get("resolved_tool_names", [])
    assert worker_trace.get("route_source") in {"tool_call", "content_or_fallback"}
    assert trace[-1]["node_id"] == "response"
    assert any(
        isinstance(entry.content, DigestedInformation)
        for entry in agent.loop.root_session.session_context
    )


@pytest.mark.asyncio
async def test_default_agent_live_streaming_passthrough_trace_order() -> None:
    """Streaming passthrough path emits events and preserves trace ordering."""
    _require_live_llm()

    agent = create_tinycua_agent(llm_model=_live_llm_model())
    stream = await agent.run("Say hello in one short sentence.", stream=True)
    events = [event async for event in stream]

    trace = agent.loop.get_execution_trace()
    assert events
    assert any(event.get("type") == "response.output_text.delta" for event in events)
    assert trace[0]["node_id"] == "query_analyst"
    assert trace[0].get("route_label") in {"worker", "passthrough", "uncertain"}
    assert "select_query_route" in trace[0].get("resolved_tool_names", [])
    assert trace[-1]["node_id"] == "response"


@pytest.mark.asyncio
async def test_default_agent_live_streaming_worker_trace_order() -> None:
    """Streaming worker path emits events and records Digester before Worker."""
    _require_live_llm()

    agent = create_tinycua_agent(
        session_config=SessionConfig(
            interaction_policy=InteractionPolicy(uncertain_strategy="route_worker")
        ),
        llm_model=_live_llm_model(),
    )
    stream = await agent.run(_WORKER_PROMPT, stream=True)
    events = [event async for event in stream]

    trace = agent.loop.get_execution_trace()
    node_ids = [entry["node_id"] for entry in trace]
    assert events
    assert any(event.get("type") == "response.output_text.delta" for event in events)
    assert trace[0]["node_id"] == "query_analyst"
    assert trace[0].get("route_label") == "worker"
    assert "select_query_route" in trace[0].get("resolved_tool_names", [])
    assert "digester" in node_ids
    assert "worker" in node_ids
    assert node_ids.index("digester") < node_ids.index("worker")
    worker_trace = trace[node_ids.index("worker")]
    assert "select_worker_route" in worker_trace.get("resolved_tool_names", [])
    assert trace[-1]["node_id"] == "response"
