"""TinyCUA LLM runtime configuration contracts."""

from __future__ import annotations

from tinycua_sdk.agent.llm_model import LanguageModel

from tinycua.factory import create_tinycua_agent


def test_factory_defaults_local_runtime_temperature_to_balanced_value() -> None:
    """TinyCUA applies its orchestration sampling default when unset."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
    )

    agent = create_tinycua_agent(llm_model=model)

    assert agent.llm_model.temperature == 0.6


def test_factory_preserves_explicit_temperature() -> None:
    """An explicit user temperature remains respected."""
    model = LanguageModel(
        provider="openai-chat-completions",
        model_name="local-model",
        base_url="http://localhost:1234/v1",
        api_key="test",
        temperature=0.0,
    )

    agent = create_tinycua_agent(llm_model=model)

    assert agent.llm_model.temperature == 0.0
