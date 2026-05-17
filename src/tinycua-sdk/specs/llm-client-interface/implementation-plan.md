# Implementation: Unified LLM Client Interface — Phase 1 (Foundation)

Define the canonical SSE event schema, canonical input types, refactored `LLMClient` ABC, `ProviderRegistry`, and error classes for the TINYCUA SDK. This phase is provider-agnostic — no provider SDK integrations are included.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P0
- **Estimated Effort**: M

## Environment Pre-requisites

> **N/A** — Phase 1 is provider-agnostic and requires no external services, API keys, or running infrastructure. All tests run purely against the type system and in-memory registry.

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/integration/test_provider_switching.py
"""Integration tests for provider registry switching via LanguageModel.provider."""

import pytest
from tinycua_sdk.agent.llm_client import LLMClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.providers import ProviderRegistry, ProviderInfo, get_provider_registry
from tinycua_sdk.core.exceptions import ProviderNotSupportedError


# ── Fake clients for contract-level testing (no provider SDK) ──────────────
# NOTE: Cross-parameter validation (e.g., raw_events=True requires stream=True)
# lives in the LLMClient ABC base class via a concrete template-method
# pattern: chat() is concrete, performs shared validation, then delegates to
# abstract _chat_impl(). These fakes include the check inline so the planned
# tests can validate the contract.

class _FakeAlphaClient(LLMClient):
    async def _chat_impl(self, messages, tools=None, stream=False, raw_events=False):
        from collections.abc import AsyncIterator
        from tinycua_sdk.agent.events import LLMResponse
        if stream:
            async def _gen():
                yield {"type": "response.completed", "finish_reason": "stop"}
            return _gen()
        return LLMResponse(
            content="alpha response",
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            model="alpha-model",
        )

    async def close(self):
        pass


class _FakeBetaClient(LLMClient):
    async def _chat_impl(self, messages, tools=None, stream=False, raw_events=False):
        from tinycua_sdk.agent.events import LLMResponse
        return LLMResponse(
            content="beta response",
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            model="beta-model",
        )

    async def close(self):
        pass


@pytest.fixture
def registry():
    """Return a *fresh* ProviderRegistry instance for isolated provider tests.

    This fixture does NOT use the singleton registry, so default registrations
    (e.g. ``openai-responses`` registered at import time) are never affected.
    Use this fixture for tests that register custom fake providers — each test
    gets a clean instance with zero pre-registered providers.
    """
    reg = ProviderRegistry()
    yield reg


@pytest.fixture
def default_registry():
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

async def test_registry_returns_correct_client_per_provider(registry):
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

    resp_a = await client_a.chat([{"role": "user", "content": "hello"}])
    resp_b = await client_b.chat([{"role": "user", "content": "hello"}])

    assert resp_a["content"] == "alpha response"
    assert resp_b["content"] == "beta response"


# ── Test 2: Unsupported provider raises clear error ────────────────────────

def test_unsupported_provider_raises_error(registry):
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

def test_list_providers_returns_registered(registry):
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

async def test_raw_events_requires_stream(registry):
    """Given raw_events=True and stream=False, chat() raises ValueError."""

    registry.register(
        "test",
        lambda c: _FakeAlphaClient(),
        ProviderInfo(id="test", factory=lambda c: _FakeAlphaClient(), description="Test"),
    )
    client = registry.create_client(LanguageModel(provider="test", model_name="test"))

    with pytest.raises(ValueError, match="raw_events=True requires stream=True"):
        await client.chat([{"role": "user", "content": "hi"}], raw_events=True)


# ── Test 5: openai-responses resolves through registry (default registration) ─

async def test_openai_responses_default_registration(default_registry):
    """Given openai-responses is auto-registered in the default singleton,
    when create_client is called with provider="openai-responses", the
    returned client is correctly configured from the LanguageModel config.

    This test does NOT call register() — it relies on the default
    registration that happens at import time. This proves the auto-registration
    path works, unlike a test that manually re-registers the provider.

    Unlike Test 6/7 which verify deterministic fake responses, this test
    validates that the default registration preserves the configured model
    and base URL path — the intended Phase 1 migration path."""
    import os

    # Verify the provider is already registered (default registration)
    assert default_registry.is_supported("openai-responses")

    # Construct a LanguageModel with an explicit model_name and base_url
    # that mirrors the configured path a real consumer would use.
    model = LanguageModel(
        provider="openai-responses",
        model_name="gpt-4o",
        base_url=os.environ.get("TEST_OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    client = default_registry.create_client(model)

    # Verify the default registration produced a configured client without
    # manual registration. Do NOT make a live provider call — that is tested
    # separately (see Test 6/7 for fake-provider switching tests).
    from tinycua_sdk.agent.llm_client import OpenAICompatibleClient
    assert isinstance(client, OpenAICompatibleClient), (
        f"Expected OpenAICompatibleClient, got {type(client).__name__}"
    )

    # The client should be properly initialized from the model config.
    # Verify by checking it can resolve the httpx client key without error.
    key = client._client_key(model)
    assert key[0] == model.base_url, f"Expected base_url {model.base_url}, got {key[0]}"


# ── Test 6: Unrecognized provider strings raise ProviderNotSupportedError ─────

def test_unrecognized_provider_strings_rejected(default_registry):
    """Given only openai-responses is registered (via default registration),
    any unrecognized provider strings (e.g. "openai", "openai-compatible",
    "unknown-provider") raise ProviderNotSupportedError with migration
    guidance listing registered providers. Rejection is registry-driven —
    no hard-coded provider list in LanguageModel."""

    # openai-responses is auto-registered — no need to manually register
    for unrecognized in ("openai", "openai-compatible", "unknown-provider"):
        model = LanguageModel(provider=unrecognized, model_name="test")
        with pytest.raises(ProviderNotSupportedError) as excinfo:
            default_registry.create_client(model)
        assert unrecognized in str(excinfo.value)
        assert "openai-responses" in str(excinfo.value)
```

### Key Test Scenarios

- [ ] **Scenario 1**: Registry resolves different provider clients from `LanguageModel.provider` and each returns the expected canonical response shape — this is the primary success criterion proving the switching mechanism works.
- [ ] **Scenario 2**: Unsupported provider strings raise `ProviderNotSupportedError` with a clear message listing supported providers — verifies user-facing error quality.
- [ ] **Scenario 3**: `provider="openai-responses"` is accepted through the registry and resolves a usable client without manual registration — proves the Phase 1 default registration path works.
- [ ] **Scenario 4**: Unrecognized provider strings (including old strings like `"openai"`, `"openai-compatible"`) raise `ProviderNotSupportedError` with migration guidance via registry-driven rejection — no hard-coded provider list in `LanguageModel`.
- [ ] **Scenario 5**: `LanguageModel()` with no explicit provider defaults to `"openai-responses"` and resolves successfully through the registry — proves the default provider change.
- [ ] **Edge case**: `raw_events=True` with `stream=False` raises `ValueError` — validates the cross-parameter validation contract.

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for canonical schema TypedDicts — verify type shapes, imports, and discriminated union narrowing
- [ ] Unit tests for `ProviderRegistry` — register, reset, create_client, list_providers, is_supported edge cases
- [ ] Unit tests for error classes — `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` can be imported, raised, and carry expected attributes
- [ ] `OpenAICompatibleClient` contract tests — verify the refactored client:
  - [ ] Instantiates correctly from `LanguageModel` configuration with the new `LLMClient` ABC contract
  - [ ] Implements `_chat_impl()` and can be resolved via `ProviderRegistry.create_client()`
  - [ ] Non-streaming `chat()` returns correct `LLMResponse` shape
  - [ ] Streaming `chat()` yields canonical `LLMEvent` items
  - [ ] `raw_events=True` with `stream=False` raises `ValueError` via base class validation
- [ ] Unit tests for default provider behavior:
  - [ ] `LanguageModel().provider` returns `"openai-responses"` (changed from `"openai-compatible"`)
  - [ ] `normalize_base_url(None, "openai-responses")` returns `"https://api.openai.com/v1"` (correct default for OpenAI Responses API)
  - [ ] `normalize_base_url("http://localhost:1234/v1", "openai-responses")` preserves explicit override
  - [ ] Unrecognized provider strings (e.g. `"openai"`, `"openai-compatible"`) still instantiate `LanguageModel` — the model normalizes without hard-coding the recognized set — but `ProviderRegistry.create_client()` raises `ProviderNotSupportedError` because the provider is not registered
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua-sdk && uv run pytest`

### Manual Verification

- [ ] Run type checker on the new TypedDicts: `cd src/tinycua-sdk && uv run mypy tinycua_sdk/agent/events.py`
- [ ] Verify old event exports are removed from `agent/__init__.py` (consumers must migrate to new canonical types)

### Performance Considerations

- [ ] None — Phase 1 is purely structural (types, ABC, registry). No hot-path changes.

## Proposed Changes

### Canonical SSE Event Schema

#### [MODIFY] `tinycua_sdk/agent/events.py`

- **[Description of change]**: Add new canonical event TypedDicts replacing existing ones. Add `ContentDeltaEvent`, `ContentDoneEvent`, `ToolCallStartedEvent` (refined), `ToolCallArgumentsDeltaEvent` (refined), `ToolCallArgumentsDoneEvent` (refined), `ToolCallReadyEvent`, `TokenUsage`, `ResponseUsageEvent` (refined), `ResponseCompletedEvent` (refined), `ResponseFailedEvent` (refined). Remove old TypedDicts (`ResponseCreatedEvent`, `ResponseCancelledEvent`, `ResponseOutputTextDeltaEvent`, `ResponseToolCallDeltaEvent`, `ErrorEvent`, `ResponseInProgressEvent`) — consumers must migrate to the new canonical types. Add `LLMEvent` union type alias, `LLMResponse`, `RawSseEvent` TypedDicts. Add canonical input types (`SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolResultMessage`, `LLMMessage` union, `LLMToolSpec`).
- **[Rationale]**: The spec requires a formalized provider-agnostic canonical schema. Existing TypedDicts are a mix of normalized and raw provider events with overlapping semantics.

#### [MODIFY] `tinycua_sdk/agent/__init__.py`

- **[Description of change]**: Add new canonical event types and canonical input type exports to `__all__`. Replace existing TypedDict exports with the new canonical types.
- **[Rationale]**: Public API must expose the new schema. This is a breaking change — consumers must update imports to use the new canonical types.

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **[Description of change]**: Refactor existing `LLMClient` ABC with canonical event contract. Define `chat()` with canonical parameter types (`list[LLMMessage]`, `list[LLMToolSpec] | None`, `raw_events: bool = False`) and return type (`LLMResponse | AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]`). Make `chat()` concrete with shared `raw_events=True` + `stream=False` → `ValueError` validation, then delegate to abstract `_chat_impl()`. Document canonical event contract and tool-call state machine rules in docstring. Existing subclasses must be updated — this is a breaking change.
- **[Rationale]**: FR-001, FR-005, FR-006, FR-007, FR-013. The ABC must define the contract that all provider clients implement.

### Provider Registry

#### [MODIFY] `tinycua_sdk/core/providers.py`

- **[Description of change]**: Add `ProviderFactory` type alias, `ProviderInfo` dataclass, `ProviderRegistry` class with `register()`, `create_client()`, `list_providers()`, `is_supported()`, `reset()` methods. Add singleton instance `_provider_registry`. Keep existing `resolve_provider()` function — it remains usable during Phase 1 migration. **Phase 1 default registration**: Auto-register `"openai-responses"` → `OpenAICompatibleClient` factory in the singleton registry so that `LanguageModel(provider="openai-responses", ...)` resolves correctly via `ProviderRegistry.create_client()`. Old provider strings (`"openai"`, `"openai-compatible"`) are NOT registered — they raise `ProviderNotSupportedError` via `create_client()`.
- **Default provider change**: `LanguageModel.provider` default changes from `"openai-compatible"` to `"openai-responses"` so that `LanguageModel()` with no explicit provider resolves through the registry. Provider recognition and rejection are owned by `ProviderRegistry` — `LanguageModel` normalizes provider strings without hard-coding the recognized set. Unrecognized providers are rejected at `create_client()` time via `ProviderNotSupportedError`.
- **Default base URL for `openai-responses`**: `normalize_base_url(None, "openai-responses")` returns `"https://api.openai.com/v1"` instead of the generic default (`http://localhost:1234/v1`). Add `"openai-responses"` → OpenAI default URL mapping in `normalize_base_url()`.
- **⚠ Import cycle mitigation**: `core/providers.py` already exports `normalize_base_url` which is imported by `llm_client.py`. To prevent circular imports (`core.providers` → `agent.llm_client` → `core.providers`):
  - Add `from __future__ import annotations` to `core/providers.py` (deferred evaluation).
  - Import `LanguageModel` and `LLMClient` under `TYPE_CHECKING` guards (type-only references, never evaluated at runtime).
  - Use a local deferred import inside the default-registration callable: `from tinycua_sdk.agent.llm_client import OpenAICompatibleClient` is placed inside the factory function body, not at module top level. This ensures `core.providers` can be fully imported without triggering the `agent.llm_client` import chain until the factory is actually invoked.
- **[Rationale]**: FR-003, FR-004, FR-009. The registry maps provider strings to client factories and provides runtime validation.

### Agent Executor Integration

#### [MODIFY] `tinycua_sdk/agent/executor.py`

- **[Description of change]**: Update `AgentExecutor._get_llm_client()` to use `ProviderRegistry` instead of hardcoded `OpenAICompatibleClient()`. Replace direct instantiation with `get_provider_registry().create_client(self.config.llm_model)` so the executor respects `LanguageModel.provider` switching. Update `_call_llm()` to the new `LLMClient.chat()` signature — configuration is bound at construction so `model` is no longer passed as a per-call parameter; callers create a new client via the registry for different configurations. Add `LanguageModel` support in `AgentExecutor.__init__()` or ensure `self.config.llm_model` is always set for registry resolution.
- **[Rationale]**: REVIEW ISSUE-001 — The registry-first entrypoint is documented in the design but the implementation plan omitted the concrete component (`AgentExecutor`) that currently hardcodes `OpenAICompatibleClient()`. Without this migration, registry unit tests can pass while real agent execution flows continue bypassing the registry, making provider switching through `LanguageModel.provider` ineffective.

### Error Classes

#### [NEW] `tinycua_sdk/core/exceptions.py`

- **[Description of change]**: Create `ProviderNotSupportedError(provider_id, supported_list)`, `ProviderAuthError(message)`, `ProviderApiError(status_code, message)` exception classes.
- **[Dependencies]**: Imported by `providers.py` and provider client implementations.
- **[Rationale]**: FR-009. Clear, actionable error types for provider-related failures.

### Agent Public API

#### [NEW] update exports in `tinycua_sdk/agent/__init__.py`

- **[Description of change]**: Add `LLMEvent`, `ContentDeltaEvent`, `ContentDoneEvent`, `ToolCallReadyEvent`, `LLMResponse`, `LLMMessage`, `LLMToolSpec`, `TokenUsage`, `RawSseEvent` to `__all__`. Replace existing event type exports with the new canonical types.
- **[Rationale]**: Public API must expose the new canonical types. This is a breaking change — consumers must update imports.

### Tests

#### [NEW] `tests/unit/test_canonical_schema.py`

- **[Description of change]**: Unit tests validating canonical schema TypedDicts type-check and have correct shapes. Tests for `LLMEvent` discriminated union narrowing by `type` field.
- **[Dependencies]**: `events.py` canonical types.

#### [NEW] `tests/unit/test_provider_registry.py`

- **[Description of change]**: Unit tests for `ProviderRegistry` — `register()`, `reset()`, `create_client()`, `list_providers()`, `is_supported()`, error cases for unsupported providers, and re-registration behavior.
- **[Dependencies]**: `providers.py`, `exceptions.py`.

#### [NEW] `tests/unit/test_error_classes.py`

- **[Description of change]**: Unit tests for `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` — import, instantiation, attribute access, string representation.
- **[Dependencies]**: `exceptions.py`.

#### [NEW] `tests/integration/test_provider_switching.py`

- **[Description of change]**: Integration tests (defined in Success Criteria above) testing compile-time/contract-level provider switching via `LanguageModel.provider` with fake client implementations.
- **[Dependencies]**: `llm_client.py`, `providers.py`, `exceptions.py`, `events.py`.

#### [NEW] `tests/unit/test_openai_compatible_client.py`

- **[Description of change]**: Unit and contract tests for the refactored `OpenAICompatibleClient`. Verifies it implements `_chat_impl()`, instantiates from `LanguageModel`, resolves through `ProviderRegistry`, produces correct `LLMResponse` (non-streaming) and `LLMEvent` (streaming) outputs, and passes base class `raw_events=True` with `stream=False` validation.
- **[Dependencies]**: `llm_client.py`, `providers.py`, `events.py`.

#### [MODIFY] `tests/unit/test_executor_integration.py`

- **[Description of change]**: New tests proving `AgentExecutor`/`Agent` uses `ProviderRegistry` and respects `LanguageModel.provider` switching. Tests verify `_get_llm_client()` returns correct client per provider, and `_call_llm()` uses the new `LLMClient.chat()` signature without passing `model` as a per-call parameter. These tests use the `registry` fixture (fresh instance) so default registrations are not affected.
- **[Dependencies]**: `executor.py`, `providers.py`, `llm_client.py`.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua_sdk/agent/events.py` | Modify | Canonical SSE schema added; old TypedDicts removed (breaking); canonical input types added |
| `tinycua_sdk/agent/llm_client.py` | Modify | Existing `LLMClient` ABC refactored with canonical event contract; concrete `chat()` with validation delegates to abstract `_chat_impl()` |
| `tinycua_sdk/core/providers.py` | Modify | `ProviderRegistry` added alongside existing provider functions; `from __future__ import annotations` + `TYPE_CHECKING` guards to prevent circular imports with `agent.llm_client`; default `openai-responses` registration via deferred local import; `normalize_base_url()` updated for `"openai-responses"` default URL |
| `tinycua_sdk/core/exceptions.py` | New | Provider-specific exception classes |
| `tinycua_sdk/agent/__init__.py` | Modify | Updated exports for new canonical types |
| `tinycua_sdk/agent/executor.py` | Modify | `_get_llm_client()` updated to use `get_provider_registry().create_client(self.config.llm_model)` instead of hardcoded `OpenAICompatibleClient()`; `_call_llm()` updated to new `LLMClient.chat()` signature without per-call `model` parameter |
| `tests/unit/test_canonical_schema.py` | New | Schema type validation tests |
| `tests/unit/test_provider_registry.py` | New | Registry behavior unit tests |
| `tests/unit/test_error_classes.py` | New | Error class unit tests |
| `tests/integration/test_provider_switching.py` | New | Contract-level integration tests |
| `tests/unit/test_openai_compatible_client.py` | New | `OpenAICompatibleClient` contract and behavior tests |
| `tests/unit/test_executor_integration.py` | New | Tests proving `AgentExecutor` uses registry and respects `LanguageModel.provider` switching |

## Data Model Changes

```python
# Canonical SSE Event Schema (events.py)
ContentDeltaEvent      — type: "content.delta", delta: str, index: int
ContentDoneEvent       — type: "content.done", index: int
ToolCallStartedEvent   — type: "tool_call.started", id, call_id, name
ToolCallArgumentsDeltaEvent — type: "tool_call.arguments.delta", id, arguments: str
ToolCallArgumentsDoneEvent  — type: "tool_call.arguments.done", id, call_id, name, arguments
ToolCallReadyEvent     — type: "tool_call.ready", id, call_id, name, arguments
TokenUsage         — input_tokens: int|None, output_tokens: int|None, total_tokens: int|None
ResponseUsageEvent     — type: "response.usage", usage: TokenUsage
ResponseCompletedEvent — type: "response.completed", finish_reason: str
ResponseFailedEvent    — type: "response.failed", error: dict
LLMResponse      — content, tool_calls, usage, finish_reason, model
RawSseEvent            — provider: str, raw_event: Any

# Canonical Input Types (events.py)
SystemMessage          — role: "system", content: str
UserMessage            — role: "user", content: str
AssistantMessage       — role: "assistant", content: str|None
ToolResultMessage      — role: "tool_result", call_id: str, content: str
LLMMessage       — union of SystemMessage | UserMessage | AssistantMessage | ToolResultMessage
LLMToolSpec      — name: str, description: str, parameters: dict

# Provider Registry (providers.py)
ProviderFactory        — Callable[[LanguageModel], LLMClient]
ProviderInfo           — id: str, factory, description: str, supported_models: list[str]|None

# Error Classes (exceptions.py)
ProviderNotSupportedError(provider_id, supported_list)
ProviderAuthError(message)
ProviderApiError(status_code, message)
```

## API Changes

### Refactored `LLMClient` ABC

| Interface | Change |
|-----------|--------|
| **`LLMClient.chat()`** (refactored → concrete) | Parameters: `messages: list[LLMMessage]`, `tools: list[LLMToolSpec] | None`, `raw_events: bool = False`. No `model_config` (configuration bound at construction). Return type union of `LLMResponse` / `AsyncIterator[LLMEvent]` / `AsyncIterator[tuple[LLMEvent|None, RawSseEvent|None]]`. Concrete method performs shared validation (`raw_events=True` requires `stream=True`) then delegates to abstract `_chat_impl()`. |
| **`LLMClient._chat_impl()`** (new, abstract) | Parameters: `messages: list[LLMMessage]`, `tools: list[LLMToolSpec] | None`, `stream: bool = False`, `raw_events: bool = False`. Subclasses implement provider-specific logic here. The `raw_events` flag is passed through so providers can yield paired `(canonical, raw)` tuples when requested. |
| **`LLMClient.close()`** | Abstract method (unchanged). |

> **Note**: This is a **breaking change**. The existing `LLMClient` ABC is refactored in-place — subclasses must add `_chat_impl()` implementation. `OpenAICompatibleClient` must be updated to match the new contract in Phase 1. Backward compatibility is not maintained.

### New Interfaces

| Interface | Description |
|-----------|-------------|
| `ProviderRegistry.register()` | Register a provider factory + metadata |
| `ProviderRegistry.create_client(model_config)` | Resolve a configured client from `LanguageModel` |
| `ProviderRegistry.list_providers()` | List registered providers |
| `ProviderRegistry.is_supported(provider_id)` | Check if provider is registered |
| `ProviderRegistry.reset()` | Clear all registered providers (testing) |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| None | — | Phase 1 is provider-agnostic and requires no new external dependencies |

### Internal Dependencies

- [ ] Depends on existing `LanguageModel` model (`tinycua_sdk/agent/llm_model.py`)
- [ ] Depends on existing `core/providers.py` infrastructure (coexists alongside new registry)
- [ ] Blocks Phase 2 (OpenAI Responses API provider implementation)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking change to `LLMClient` ABC signature breaks existing subclasses | High | This is an intentional breaking change — `LLMClient` ABC is refactored in-place. Existing subclasses must be updated to implement `_chat_impl(messages, tools, stream, raw_events)`. No backward-compatibility shim is provided. |
| Old event TypedDict removal breaks existing consumers | High | This is an intentional breaking change — old TypedDicts are removed in Phase 1. Consumers must migrate to new canonical types. |
| ProviderRegistry singleton causes test pollution | Medium | Custom-provider tests use fresh ``ProviderRegistry()`` instances (not the singleton). Default-registration tests use the singleton but never call ``reset()``, so built-in defaults persist. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-17*
