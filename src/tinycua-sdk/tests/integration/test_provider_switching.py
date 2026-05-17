"""Integration tests for provider registry switching via LanguageModel.provider."""

from collections.abc import AsyncIterator

import pytest

from tinycua_sdk.agent.events import LLMEvent, LLMResponse
from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.exceptions import ProviderNotSupportedError
from tinycua_sdk.core.providers import ProviderInfo, ProviderRegistry, get_provider_registry


# ── Fake clients for contract-level testing (no provider SDK) ──────────────


class _FakeAlphaClient(LLMClient):
    """Fake LLMClient that returns 'alpha response'."""

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
            content="alpha response",
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            model="alpha-model",
        )

    async def close(self) -> None:
        pass


class _FakeBetaClient(LLMClient):
    """Fake LLMClient that returns 'beta response'."""

    async def _chat_impl(
        self,
        messages: list,
        tools=None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMEvent]:
        return LLMResponse(
            content="beta response",
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            model="beta-model",
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
        "alpha",
        lambda cfg: _FakeAlphaClient(),
        ProviderInfo(id="alpha", factory=lambda c: _FakeAlphaClient(), description="Alpha"),
    )
    registry.register(
        "beta",
        lambda cfg: _FakeBetaClient(),
        ProviderInfo(id="beta", factory=lambda c: _FakeBetaClient(), description="Beta"),
    )

    model_a = LanguageModel(provider="alpha", model_name="alpha-model")
    model_b = LanguageModel(provider="beta", model_name="beta-model")

    client_a = registry.create_client(model_a)
    client_b = registry.create_client(model_b)

    resp_a = await client_a.chat([{"role": "user", "content": "hello"}])  # type: ignore[arg-type]
    resp_b = await client_b.chat([{"role": "user", "content": "hello"}])  # type: ignore[arg-type]

    assert resp_a["content"] == "alpha response"  # type: ignore[index]
    assert resp_b["content"] == "beta response"  # type: ignore[index]


# ── Test 2: Unsupported provider raises clear error ────────────────────────


def test_unsupported_provider_raises_error(registry: ProviderRegistry) -> None:
    """Given no providers registered for a string, when create_client is
    called, ProviderNotSupportedError is raised with supported list."""
    registry.register(
        "supported-one",
        lambda c: _FakeAlphaClient(),
        ProviderInfo(id="supported-one", factory=lambda c: _FakeAlphaClient(), description="S1"),
    )

    model = LanguageModel(provider="does-not-exist", model_name="test")
    with pytest.raises(ProviderNotSupportedError) as excinfo:
        registry.create_client(model)
    assert "does-not-exist" in str(excinfo.value)
    assert "supported-one" in str(excinfo.value)


# ── Test 3: list_providers returns registered providers ────────────────────


def test_list_providers_returns_registered(registry: ProviderRegistry) -> None:
    """Given providers registered, list_providers includes all of them."""
    registry.register(
        "p1",
        lambda c: _FakeAlphaClient(),
        ProviderInfo(id="p1", factory=lambda c: _FakeAlphaClient(), description="Provider 1"),
    )
    registry.register(
        "p2",
        lambda c: _FakeBetaClient(),
        ProviderInfo(id="p2", factory=lambda c: _FakeBetaClient(), description="Provider 2"),
    )

    providers = registry.list_providers()
    ids = [p.id for p in providers]
    assert "p1" in ids
    assert "p2" in ids


# ── Test 4: raw_events=True with stream=False raises ValueError ────────────


@pytest.mark.asyncio
async def test_raw_events_requires_stream(registry: ProviderRegistry) -> None:
    """Given raw_events=True and stream=False, chat() raises ValueError."""
    registry.register(
        "test",
        lambda c: _FakeAlphaClient(),
        ProviderInfo(id="test", factory=lambda c: _FakeAlphaClient(), description="Test"),
    )
    client = registry.create_client(LanguageModel(provider="test", model_name="test"))

    with pytest.raises(ValueError, match="raw_events=True requires stream=True"):
        await client.chat([{"role": "user", "content": "hi"}], raw_events=True)  # type: ignore[arg-type]


# ── Test 5: openai-responses resolves through registry (default registration) ─


@pytest.mark.asyncio
async def test_openai_responses_default_registration(default_registry: ProviderRegistry) -> None:
    """Given openai-responses is auto-registered in the default singleton,
    when create_client is called with provider="openai-responses", the
    returned client is correctly configured from the LanguageModel config.

    This test does NOT call register() — it relies on the default
    registration that happens at import time. This proves the auto-registration
    path works, unlike a test that manually re-registers the provider.
    """
    # Verify the provider is already registered (default registration)
    assert default_registry.is_supported("openai-responses")

    # Construct a LanguageModel with an explicit model_name and base_url
    model = LanguageModel(
        provider="openai-responses",
        model_name="gpt-4o",
        base_url="https://api.openai.com/v1",
    )
    client = default_registry.create_client(model)

    # Verify the default registration produced a configured client
    from tinycua_sdk.agent.llm_client import OpenAICompatibleClient

    assert isinstance(client, OpenAICompatibleClient), (
        f"Expected OpenAICompatibleClient, got {type(client).__name__}"
    )

    # The client should be properly initialized from the model config.
    # Verify by checking it can resolve the httpx client key without error.
    key = client._client_key()
    assert key[0] == model.base_url, f"Expected base_url {model.base_url}, got {key[0]}"


# ── Test 6: Unrecognized provider strings raise ProviderNotSupportedError ─────


def test_unrecognized_provider_strings_rejected(default_registry: ProviderRegistry) -> None:
    """Given only openai-responses is registered (via default registration),
    any unrecognized provider strings (e.g. "openai", "openai-compatible",
    "unknown-provider") raise ProviderNotSupportedError with migration
    guidance listing registered providers. Rejection is registry-driven —
    no hard-coded provider list in LanguageModel."""
    for unrecognized in ("openai", "openai-compatible", "unknown-provider"):
        model = LanguageModel(provider=unrecognized, model_name="test")
        with pytest.raises(ProviderNotSupportedError) as excinfo:
            default_registry.create_client(model)
        assert unrecognized in str(excinfo.value)
        assert "openai-responses" in str(excinfo.value)
