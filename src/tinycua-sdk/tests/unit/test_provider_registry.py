"""Unit tests for ProviderRegistry.

Tests register, reset, create_client, list_providers, is_supported,
re-registration behavior, and error cases for unsupported providers.
"""

import pytest

from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderNotSupportedError
from tinycua_sdk.providers.registry import ProviderRegistry
from tinycua_sdk.providers.utility import ProviderInfo


class _MinimalClient(LLMClient):
    """Minimal LLMClient for testing."""

    async def _chat_impl(self, messages, tools=None, stream=False, raw_events=False):
        from tinycua_sdk.agent.events import LLMResponse
        return LLMResponse(
            content="test", tool_calls=None, usage=None, finish_reason="stop", model="test",
        )

    async def close(self) -> None:
        pass


@pytest.fixture
def registry() -> ProviderRegistry:
    """Return a fresh ProviderRegistry for each test."""
    return ProviderRegistry()


class TestProviderRegistry:
    """ProviderRegistry core functionality."""

    def test_register_and_create_client(self, registry: ProviderRegistry) -> None:
        def factory(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        info = ProviderInfo(id="openai-compatible", factory=factory, description="Test")
        registry.register("openai-compatible", factory, info)

        model = LanguageModel.model_construct(provider="openai-compatible", model_name="test")
        client = registry.create_client(model)
        assert isinstance(client, LLMClient)
        assert isinstance(client, _MinimalClient)

    def test_create_client_unsupported_provider(self, registry: ProviderRegistry) -> None:
        model = LanguageModel.model_construct(provider="openai", model_name="test")
        with pytest.raises(ProviderNotSupportedError) as excinfo:
            registry.create_client(model)
        assert "openai" in str(excinfo.value)

    def test_create_client_error_lists_supported(self, registry: ProviderRegistry) -> None:
        def factory(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        info = ProviderInfo(id="existing", factory=factory, description="Existing")
        registry.register("existing", factory, info)

        model = LanguageModel.model_construct(provider="openai", model_name="test")
        with pytest.raises(ProviderNotSupportedError) as excinfo:
            registry.create_client(model)
        assert "openai" in str(excinfo.value)
        assert "existing" in str(excinfo.value)

    def test_is_supported_returns_true(self, registry: ProviderRegistry) -> None:
        def factory(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        info = ProviderInfo(id="my-provider", factory=factory, description="")
        registry.register("my-provider", factory, info)

        assert registry.is_supported("my-provider") is True

    def test_is_supported_returns_false(self, registry: ProviderRegistry) -> None:
        assert registry.is_supported("not-registered") is False

    def test_list_providers_empty(self, registry: ProviderRegistry) -> None:
        assert registry.list_providers() == []

    def test_list_providers_after_registration(self, registry: ProviderRegistry) -> None:
        def factory(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        info = ProviderInfo(id="openai-compatible", factory=factory, description="OpenAI Compatible")
        registry.register("openai-compatible", factory, info)

        providers = registry.list_providers()
        assert len(providers) == 1
        assert providers[0].id == "openai-compatible"

    def test_reset_clears_all_providers(self, registry: ProviderRegistry) -> None:
        def factory(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        registry.register("openai-compatible", factory, ProviderInfo(id="openai-compatible", factory=factory, description=""))

        registry.reset()
        assert registry.list_providers() == []
        assert registry.is_supported("openai-compatible") is False

    def test_re_register_overwrites(self, registry: ProviderRegistry) -> None:
        def factory_a(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        def factory_b(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        registry.register("openai-compatible", factory_a, ProviderInfo(id="openai-compatible", factory=factory_a, description="A"))
        registry.register("openai-compatible", factory_b, ProviderInfo(id="openai-compatible", factory=factory_b, description="B"))

        providers = registry.list_providers()
        assert len(providers) == 1
        assert providers[0].description == "B"

    def test_create_client_with_config(self, registry: ProviderRegistry) -> None:
        """Client receives the LanguageModel config at construction."""
        captured_configs: list[LanguageModel] = []

        def capturing_factory(cfg: LanguageModel) -> LLMClient:
            captured_configs.append(cfg)
            return _MinimalClient()

        info = ProviderInfo(id="openai-compatible", factory=capturing_factory, description="Capture")
        registry.register("openai-compatible", capturing_factory, info)

        model = LanguageModel.model_construct(provider="openai-compatible", model_name="gpt-4o", temperature=0.5)
        registry.create_client(model)

        assert len(captured_configs) == 1
        assert captured_configs[0].model_name == "gpt-4o"
        assert captured_configs[0].temperature == 0.5

    def test_list_providers_includes_all(self, registry: ProviderRegistry) -> None:
        """list_providers includes openai-chat-completions when registered."""
        def factory(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        registry.register("openai-chat-completions", factory, ProviderInfo(id="openai-chat-completions", factory=factory, description="Chat"))
        registry.register("openai-responses", factory, ProviderInfo(id="openai-responses", factory=factory, description="Responses"))

        providers = registry.list_providers()
        ids = [p.id for p in providers]
        assert "openai-chat-completions" in ids
        assert "openai-responses" in ids

    def test_openai_chat_completions_resolves(self, registry: ProviderRegistry) -> None:
        """provider='openai-chat-completions' creates the right client."""
        from tinycua_sdk.providers.open_ai_chat_completions import OpenAIChatCompletionsClient

        def factory(cfg: LanguageModel) -> LLMClient:
            return OpenAIChatCompletionsClient(cfg)

        registry.register("openai-chat-completions", factory, ProviderInfo(id="openai-chat-completions", factory=factory, description="Chat"))

        model = LanguageModel.model_construct(provider="openai-chat-completions", model_name="gpt-4o")
        client = registry.create_client(model)
        assert isinstance(client, OpenAIChatCompletionsClient)


class TestProviderInfo:
    """ProviderInfo dataclass behavior."""

    def test_provider_info_defaults(self) -> None:
        def factory(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        info = ProviderInfo(id="test", factory=factory)
        assert info.id == "test"
        assert info.description == ""
        assert info.supported_models is None

    def test_provider_info_full(self) -> None:
        def factory(cfg: LanguageModel) -> _MinimalClient:
            return _MinimalClient()
        info = ProviderInfo(
            id="full",
            factory=factory,
            description="Full provider",
            supported_models=["gpt-4o", "gpt-4o-mini"],
        )
        assert info.description == "Full provider"
        assert info.supported_models == ["gpt-4o", "gpt-4o-mini"]


class TestRegistryFactoryPrecedence:
    """Explicit factory argument takes precedence over metadata.factory (ISSUE-005)."""

    def test_explicit_factory_overrides_metadata_factory(self) -> None:
        """register() uses the explicit factory arg, not metadata.factory."""

        class A(LLMClient):
            async def _chat_impl(self, messages, tools=None, stream=False, raw_events=False):
                from tinycua_sdk.agent.events import LLMResponse
                return LLMResponse(content='A', tool_calls=None, usage=None, finish_reason='stop', model='a')
            async def close(self): pass

        class B(LLMClient):
            async def _chat_impl(self, messages, tools=None, stream=False, raw_events=False):
                from tinycua_sdk.agent.events import LLMResponse
                return LLMResponse(content='B', tool_calls=None, usage=None, finish_reason='stop', model='b')
            async def close(self): pass

        def factory_a(cfg): return A()
        def factory_b(cfg): return B()

        r = ProviderRegistry()
        r.register('openai-compatible', factory_a, ProviderInfo(id='openai-compatible', factory=factory_b, description='metadata'))
        assert isinstance(r.create_client(LanguageModel.model_construct(provider='openai-compatible')), A)
