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


pytestmark = pytest.mark.live_llm


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
    """Public factory starts with QueryAnalyst and reaches ResponseNode live."""
    _require_live_llm()

    agent = create_tinycua_agent(llm_model=_live_llm_model())
    result = await agent.run("Say hello in one short sentence.")

    trace = agent.loop.get_execution_trace()
    assert isinstance(result, str)
    assert result.strip()
    assert trace[0]["node_id"] == "query_analyst"
    assert trace[0].get("route_label") in {"passthrough", "uncertain"}
    assert all(entry["node_id"] != "worker" for entry in trace)
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
    assert trace[-1]["node_id"] == "response"
