"""Tests proving AgentExecutor/Agent uses ProviderRegistry
and respects LanguageModel.provider switching."""

import pytest

from tinycua_sdk.agent.config import AgentConfig
from tinycua_sdk.agent.executor import AgentExecutor
from tinycua_sdk.agent.events import UserMessage
from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.providers import ProviderInfo, ProviderRegistry


class _FakeExecutorClient(LLMClient):
    """Minimal client for executor tests."""

    def __init__(self, tag: str = "default") -> None:
        self.tag = tag

    async def _chat_impl(self, messages, tools=None, stream=False, raw_events=False):
        from tinycua_sdk.agent.events import LLMResponse
        return LLMResponse(
            content=f"response from {self.tag}",
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            model="test",
        )

    async def close(self) -> None:
        pass


class TestAgentExecutorRegistryIntegration:
    """Test _get_llm_client uses ProviderRegistry."""

    def test_get_llm_client_uses_registry(self) -> None:
        """_get_llm_client returns a client from the registry."""
        registry = ProviderRegistry()

        def factory(cfg: LanguageModel) -> _FakeExecutorClient:
            return _FakeExecutorClient(tag="executor-test")

        registry.register(
            "test-provider",
            factory,
            ProviderInfo(id="test-provider", factory=factory, description="Test"),
        )

        model = LanguageModel(provider="test-provider", model_name="test")
        config = AgentConfig(name="executor-test", llm_model=model)
        executor = AgentExecutor(config=config, registry=registry)

        client = executor._get_llm_client()

        assert isinstance(client, _FakeExecutorClient)
        assert client.tag == "executor-test"

    def test_get_llm_client_caching(self) -> None:
        """_get_llm_client caches the client instance."""
        registry = ProviderRegistry()

        call_count = 0

        def factory(cfg: LanguageModel) -> _FakeExecutorClient:
            nonlocal call_count
            call_count += 1
            return _FakeExecutorClient(tag=f"call-{call_count}")

        registry.register(
            "test",
            factory,
            ProviderInfo(id="test", factory=factory, description=""),
        )

        model = LanguageModel(provider="test", model_name="test")
        config = AgentConfig(name="caching-test", llm_model=model)
        executor = AgentExecutor(config=config, registry=registry)

        client1 = executor._get_llm_client()
        client2 = executor._get_llm_client()

        assert client1 is client2
        assert call_count == 1


class TestAgentExecutorCallLlm:
    """Test _call_llm uses new LLMClient.chat() signature."""

    @pytest.mark.asyncio
    async def test_call_llm_returns_response(self) -> None:
        """_call_llm returns LLMResponse via registry-resolved client."""
        registry = ProviderRegistry()

        def factory(cfg: LanguageModel) -> _FakeExecutorClient:
            return _FakeExecutorClient(tag="llm-call-test")

        registry.register(
            "test-provider",
            factory,
            ProviderInfo(id="test-provider", factory=factory, description=""),
        )

        model = LanguageModel(provider="test-provider", model_name="test")
        config = AgentConfig(name="call-llm-test", llm_model=model)
        executor = AgentExecutor(config=config, registry=registry)

        result = await executor._call_llm(
            messages=[UserMessage(role="user", content="hello")],
        )

        assert isinstance(result, dict)
        assert result["content"] == "response from llm-call-test"
