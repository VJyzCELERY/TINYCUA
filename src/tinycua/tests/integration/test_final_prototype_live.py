"""Live local LLM acceptance tests for the finalized prototype runtime."""

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
    dotenv.load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env.test", override=False)
    if os.environ.get("TINYCUA_LIVE_LLM") != "1":
        pytest.skip("Set TINYCUA_LIVE_LLM=1 to run live LLM contract tests")
    for name in (
        "OPENAI_CHAT_COMPLETIONS_BASE_URL",
        "OPENAI_CHAT_COMPLETIONS_MODEL",
        "OPENAI_CHAT_COMPLETIONS_API_KEY",
    ):
        if not os.environ.get(name):
            pytest.fail(f"Missing live LLM environment variable: {name}")


def _live_llm_model() -> LanguageModel:
    return LanguageModel(
        provider="openai-chat-completions",
        model_name=os.environ["OPENAI_CHAT_COMPLETIONS_MODEL"],
        base_url=os.environ["OPENAI_CHAT_COMPLETIONS_BASE_URL"],
        api_key=os.environ["OPENAI_CHAT_COMPLETIONS_API_KEY"],
    )


@pytest.mark.asyncio
async def test_final_prototype_live_worker_task_lifecycle_and_streaming() -> None:
    """Live local model exercises worker lifecycle and final stream contracts."""
    _require_live_llm()
    agent = create_tinycua_agent(
        session_config=SessionConfig(
            interaction_policy=InteractionPolicy(uncertain_strategy="route_worker")
        ),
        llm_model=_live_llm_model(),
    )

    result = await agent.run(
        "Use worker mode. If a route tool is available, call select_query_route "
        "with route=worker. Create and execute a concise two-step plan for "
        "writing a short README."
    )
    trace = agent.loop.get_execution_trace()
    node_ids = [entry["node_id"] for entry in trace]

    assert result.strip()
    assert "worker" in node_ids
    assert any(entry.get("task_tree") for entry in trace)
    assert trace[-1]["node_id"] == "response"
