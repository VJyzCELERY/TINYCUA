"""Integration tests for provider registry switching via LanguageModel.provider."""

from collections.abc import AsyncIterator

import pytest

from tinycua_sdk.agent.events import LLMEvent, LLMResponse, UserMessage
from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderNotSupportedError
from tinycua_sdk.core.providers import ProviderInfo, ProviderRegistry, get_provider_registry


# ── Fake clients for contract-level testing (no provider SDK) ──────────────


class _FakeOpenaiCompatibleClient(LLMClient):
    """Fake LLMClient that returns 'alpha-style response'."""

    async def _chat_impl(
        self,
        messages: list,
        tools=None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMEvent]:
        if stream:
            async def _gen() -> AsyncIterator[LLMEvent]:
                yield {"type": "response.completed", "finish_reason": "stop"}  # type: ignore[typeddict-item]
            return _gen()
        return LLMResponse(
            content="openai-compatible response",
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            model="compatible-model",
        )

    async def close(self) -> None:
        pass


class _FakeOpenaiClient(LLMClient):
    """Fake LLMClient that returns 'beta-style response'."""

    async def _chat_impl(
        self,
        messages: list,
        tools=None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMEvent]:
        return LLMResponse(
            content="openai response",
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            model="openai-model",
        )

    async def close(self) -> None:
        pass


@pytest.fixture
def registry() -> ProviderRegistry:
    """Return a *fresh* ProviderRegistry instance for isolated provider tests.

    This fixture does NOT use the singleton registry, so default registrations
    (e.g. ``openai-responses`` registered at import time) are never affected.
    Use this fixture for tests that register custom fake providers — each test
    gets a clean instance with zero pre-registered providers.
    """
    reg = ProviderRegistry()
    yield reg


@pytest.fixture
def default_registry() -> ProviderRegistry:
    """Return the singleton provider registry with defaults preserved.

    Default providers (e.g. ``openai-responses`` registered at import time)
    remain available because this fixture never calls ``reset()``. Use this
    fixture to test default-registration behavior.

    .. caution::
       Tests using this fixture share the singleton. They MUST NOT register
       custom providers — use the ``registry`` fixture (fresh instance) for
       custom-provider tests instead. If a test *must* temporarily register
       a provider, it is responsible for cleaning up after itself.
    """
    reg = get_provider_registry()
    yield reg


# ── Test 1: Registry resolves correct provider ─────────────────────────────


@pytest.mark.asyncio
async def test_registry_returns_correct_client_per_provider(registry: ProviderRegistry) -> None:
    """Given registered providers, when create_client is called, the
    returned client's chat() response reflects the correct provider."""
    registry.register(
        "openai-responses",
        lambda cfg: _FakeOpenaiCompatibleClient(),
        ProviderInfo(id="openai-responses", factory=lambda c: _FakeOpenaiCompatibleClient(), description="OpenAI Responses"),
    )
    registry.register(
        "openai-compatible",
        lambda cfg: _FakeOpenaiClient(),
        ProviderInfo(id="openai-compatible", factory=lambda c: _FakeOpenaiClient(), description="Compatible"),
    )

    model_a = LanguageModel(provider="openai-responses", model_name="alpha-model")
    model_b = LanguageModel.model_construct(provider="openai-compatible", model_name="beta-model")

    client_a = registry.create_client(model_a)
    client_b = registry.create_client(model_b)

    resp_a = await client_a.chat([UserMessage(role="user", content="hello")])
    resp_b = await client_b.chat([UserMessage(role="user", content="hello")])

    assert resp_a["content"] == "openai-compatible response"  # type: ignore[index]
    assert resp_b["content"] == "openai response"  # type: ignore[index]
    # (intentionally swapped names — model_a uses _FakeOpenaiCompatibleClient, model_b uses _FakeOpenaiClient)


# ── Test 2: Unsupported provider raises clear error ────────────────────────


def test_unsupported_provider_raises_error(registry: ProviderRegistry) -> None:
    """Given known provider not registered in the target registry, when
    create_client is called, ProviderNotSupportedError is raised with
    supported list."""
    registry.register(
        "supported-one",
        lambda c: _FakeOpenaiCompatibleClient(),
        ProviderInfo(id="supported-one", factory=lambda c: _FakeOpenaiCompatibleClient(), description="S1"),
    )

    model = LanguageModel.model_construct(provider="openai", model_name="test")
    with pytest.raises(ProviderNotSupportedError) as excinfo:
        registry.create_client(model)
    assert "openai" in str(excinfo.value)
    assert "supported-one" in str(excinfo.value)


# ── Test 3: list_providers returns registered providers ────────────────────


def test_list_providers_returns_registered(registry: ProviderRegistry) -> None:
    """Given providers registered, list_providers includes all of them."""
    registry.register(
        "provider-alpha",
        lambda c: _FakeOpenaiCompatibleClient(),
        ProviderInfo(id="provider-alpha", factory=lambda c: _FakeOpenaiCompatibleClient(), description="Provider 1"),
    )
    registry.register(
        "provider-beta",
        lambda c: _FakeOpenaiClient(),
        ProviderInfo(id="provider-beta", factory=lambda c: _FakeOpenaiClient(), description="Provider 2"),
    )

    providers = registry.list_providers()
    ids = [p.id for p in providers]
    assert "provider-alpha" in ids
    assert "provider-beta" in ids


# ── Test 4: raw_events=True with stream=False raises ValueError ────────────


@pytest.mark.asyncio
async def test_raw_events_requires_stream(registry: ProviderRegistry) -> None:
    """Given raw_events=True and stream=False, chat() raises ValueError."""
    registry.register(
        "openai-compatible",
        lambda c: _FakeOpenaiCompatibleClient(),
        ProviderInfo(id="openai-compatible", factory=lambda c: _FakeOpenaiCompatibleClient(), description="OpenAI Compatible"),
    )
    client = registry.create_client(LanguageModel.model_construct(provider="openai-compatible", model_name="test"))

    with pytest.raises(ValueError, match="raw_events=True requires stream=True"):
        await client.chat([UserMessage(role="user", content="hi")], raw_events=True)


# ── Test 5: openai-responses and openai-chat-completions resolve through registry ──


@pytest.mark.asyncio
async def test_default_registrations(default_registry: ProviderRegistry) -> None:
    """Given providers are auto-registered in the default singleton,
    create_client returns the correct client type for each."""
    from tinycua_sdk.agent.llm_client import OpenAIChatCompletionsClient, OpenAIResponsesClient

    assert default_registry.is_supported("openai-responses")
    assert default_registry.is_supported("openai-chat-completions")

    model_resp = LanguageModel(provider="openai-responses", model_name="gpt-4o")
    client_resp = default_registry.create_client(model_resp)
    assert isinstance(client_resp, OpenAIResponsesClient)

    model_chat = LanguageModel(provider="openai-chat-completions", model_name="gpt-4o")
    client_chat = default_registry.create_client(model_chat)
    assert isinstance(client_chat, OpenAIChatCompletionsClient)


# ── Test 6: Known but unregistered providers raise ProviderNotSupportedError ──


def test_deprecated_providers_rejected_by_registry(
    default_registry: ProviderRegistry, caplog: pytest.LogCaptureFixture,
) -> None:
    """Given deprecated provider strings ("openai", "openai-compatible"),
    LanguageModel accepts them, but ProviderRegistry.create_client() raises
    ProviderNotSupportedError — rejection is registry-driven.

    .. note::
       ``"openai"`` now resolves to ``"openai-responses"`` via the alias
       map with a deprecation warning, so it DOES work. Only truly
       unsupported strings like ``"openai-compatible"`` are rejected.
    """
    import logging

    caplog.set_level(logging.WARNING)

    # "openai" is now aliased to "openai-responses" → succeeds with warning
    model = LanguageModel(provider="openai", model_name="test")
    client = default_registry.create_client(model)
    assert any("deprecated" in rec.message.lower() for rec in caplog.records), (
        f"Expected deprecation warning for 'openai', got: {[rec.message for rec in caplog.records]}"
    )
    from tinycua_sdk.agent.llm_client import OpenAIResponsesClient
    assert isinstance(client, OpenAIResponsesClient)

    caplog.clear()

    # "openai-compatible" is NOT registered → raises ProviderNotSupportedError
    model2 = LanguageModel(provider="openai-compatible", model_name="test")
    with pytest.raises(ProviderNotSupportedError) as excinfo:
        default_registry.create_client(model2)
    assert "openai-compatible" in str(excinfo.value)
    assert "openai-responses" in str(excinfo.value)


# ── Test 7: Unknown provider string rejected at registry time ──


def test_unknown_provider_rejected_by_registry(default_registry: ProviderRegistry) -> None:
    """Given a completely unknown provider string, LanguageModel accepts it,
    but ProviderRegistry.create_client() raises ProviderNotSupportedError —
    rejection is registry-driven."""
    model = LanguageModel(provider="completely-unknown-provider", model_name="test")
    with pytest.raises(ProviderNotSupportedError) as excinfo:
        default_registry.create_client(model)
    assert "completely-unknown-provider" in str(excinfo.value)
    assert "openai-responses" in str(excinfo.value)
