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
from tinycua_sdk.core.providers import ProviderRegistry, ProviderInfo
from tinycua_sdk.core.exceptions import ProviderNotSupportedError


# ── Fake clients for contract-level testing (no provider SDK) ──────────────

class _FakeAlphaClient(LLMClient):
    async def chat(self, messages, tools=None, stream=False, raw_events=False):
        from collections.abc import AsyncIterator
        from tinycua_sdk.agent.events import CanonicalResponse
        if stream:
            async def _gen():
                yield {"type": "response.completed", "finish_reason": "stop"}
            return _gen()
        return CanonicalResponse(
            content="alpha response",
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            model="alpha-model",
        )

    async def close(self):
        pass


class _FakeBetaClient(LLMClient):
    async def chat(self, messages, tools=None, stream=False, raw_events=False):
        from tinycua_sdk.agent.events import CanonicalResponse
        return CanonicalResponse(
            content="beta response",
            tool_calls=None,
            usage=None,
            finish_reason="stop",
            model="beta-model",
        )

    async def close(self):
        pass


@pytest.fixture(autouse=True)
def _fresh_registry():
    """Reset registry before each test to avoid test pollution."""
    ProviderRegistry.reset()
    yield
    ProviderRegistry.reset()


# ── Test 1: Registry resolves correct provider ─────────────────────────────

async def test_registry_returns_correct_client_per_provider():
    """Given registered providers, when create_client is called, the
    returned client's chat() response reflects the correct provider."""

    ProviderRegistry.register(
        "alpha",
        lambda cfg: _FakeAlphaClient(),
        ProviderInfo(id="alpha", factory=lambda c: _FakeAlphaClient(), description="Alpha"),
    )
    ProviderRegistry.register(
        "beta",
        lambda cfg: _FakeBetaClient(),
        ProviderInfo(id="beta", factory=lambda c: _FakeBetaClient(), description="Beta"),
    )

    model_a = LanguageModel(provider="alpha", model_name="alpha-model")
    model_b = LanguageModel(provider="beta", model_name="beta-model")

    client_a = ProviderRegistry.create_client(model_a)
    client_b = ProviderRegistry.create_client(model_b)

    resp_a = await client_a.chat([{"role": "user", "content": "hello"}])
    resp_b = await client_b.chat([{"role": "user", "content": "hello"}])

    assert resp_a["content"] == "alpha response"
    assert resp_b["content"] == "beta response"


# ── Test 2: Unsupported provider raises clear error ────────────────────────

def test_unsupported_provider_raises_error():
    """Given no providers registered for a string, when create_client is
    called, ProviderNotSupportedError is raised with supported list."""

    ProviderRegistry.register(
        "supported-one",
        lambda c: _FakeAlphaClient(),
        ProviderInfo(id="supported-one", factory=lambda c: _FakeAlphaClient(), description="S1"),
    )

    model = LanguageModel(provider="does-not-exist", model_name="test")
    with pytest.raises(ProviderNotSupportedError) as excinfo:
        ProviderRegistry.create_client(model)
    assert "does-not-exist" in str(excinfo.value)
    assert "supported-one" in str(excinfo.value)


# ── Test 3: list_providers returns registered providers ────────────────────

def test_list_providers_returns_registered():
    """Given providers registered, list_providers includes all of them."""

    ProviderRegistry.register(
        "p1",
        lambda c: _FakeAlphaClient(),
        ProviderInfo(id="p1", factory=lambda c: _FakeAlphaClient(), description="Provider 1"),
    )
    ProviderRegistry.register(
        "p2",
        lambda c: _FakeBetaClient(),
        ProviderInfo(id="p2", factory=lambda c: _FakeBetaClient(), description="Provider 2"),
    )

    providers = ProviderRegistry.list_providers()
    ids = [p.id for p in providers]
    assert "p1" in ids
    assert "p2" in ids


# ── Test 4: raw_events=True with stream=False raises ValueError ────────────

async def test_raw_events_requires_stream():
    """Given raw_events=True and stream=False, chat() raises ValueError."""

    ProviderRegistry.register(
        "test",
        lambda c: _FakeAlphaClient(),
        ProviderInfo(id="test", factory=lambda c: _FakeAlphaClient(), description="Test"),
    )
    client = ProviderRegistry.create_client(LanguageModel(provider="test", model_name="test"))

    with pytest.raises(ValueError, match="raw_events=True requires stream=True"):
        await client.chat([{"role": "user", "content": "hi"}], raw_events=True)
```

### Key Test Scenarios

- [ ] **Scenario 1**: Registry resolves different provider clients from `LanguageModel.provider` and each returns the expected canonical response shape — this is the primary success criterion proving the switching mechanism works.
- [ ] **Scenario 2**: Unsupported provider strings raise `ProviderNotSupportedError` with a clear message listing supported providers — verifies user-facing error quality.
- [ ] **Edge case**: `raw_events=True` with `stream=False` raises `ValueError` — validates the cross-parameter validation contract.

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for canonical schema TypedDicts — verify type shapes, imports, and discriminated union narrowing
- [ ] Unit tests for `ProviderRegistry` — register, reset, create_client, list_providers, is_supported edge cases
- [ ] Unit tests for error classes — `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` can be imported, raised, and carry expected attributes
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua-sdk && uv run pytest`

### Manual Verification

- [ ] Run type checker on the new TypedDicts: `cd src/tinycua-sdk && uv run mypy tinycua_sdk/agent/events.py`
- [ ] Verify all old event exports in `agent/__init__.py` that are removed are marked with migration guidance

### Performance Considerations

- [ ] None — Phase 1 is purely structural (types, ABC, registry). No hot-path changes.

## Proposed Changes

### Canonical SSE Event Schema

#### [MODIFY] `tinycua_sdk/agent/events.py`

- **[Description of change]**: Replace existing event TypedDicts with the new canonical schema. Add `ContentDeltaEvent`, `ContentDoneEvent`, `ToolCallStartedEvent` (refined), `ToolCallArgumentsDeltaEvent` (refined), `ToolCallArgumentsDoneEvent` (refined), `ToolCallReadyEvent`, `CanonicalUsage`, `ResponseUsageEvent` (refined), `ResponseCompletedEvent` (refined), `ResponseFailedEvent` (refined). Remove old TypedDicts (`ResponseCreatedEvent`, `ResponseCancelledEvent`, `ResponseOutputTextDeltaEvent`, `ResponseToolCallDeltaEvent`, `ErrorEvent`, `ResponseInProgressEvent`, raw provider events). Add `CanonicalEvent` union type alias, `CanonicalResponse`, `RawSseEvent` TypedDicts. Add canonical input types (`SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolResultMessage`, `CanonicalMessage` union, `CanonicalToolSpec`).
- **[Rationale]**: The spec requires a formalized provider-agnostic canonical schema. Existing TypedDicts are a mix of normalized and raw provider events with overlapping semantics.

#### [MODIFY] `tinycua_sdk/agent/__init__.py`

- **[Description of change]**: Update exports to include new canonical event types and remove removed old TypedDict exports. Add canonical input type exports.
- **[Rationale]**: Public API must reflect the new schema. Consumers importing from `agent.__init__` should get the new types.

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **[Description of change]**: Refactor `LLMClient` ABC — update `chat()` parameter types to `list[CanonicalMessage]` and `list[CanonicalToolSpec] | None`, add `raw_events` parameter, update return type to `CanonicalResponse | AsyncIterator[CanonicalEvent] | AsyncIterator[tuple[CanonicalEvent | None, RawSseEvent | None]]`. Add `raw_events=True` + `stream=False` → `ValueError` validation. Document canonical event contract and tool-call state machine rules in docstring. Deprecate `OpenAICompatibleClient` (mark as deprecated, keep functional in Phase 1).
- **[Rationale]**: FR-001, FR-005, FR-006, FR-007, FR-013. The ABC must define the contract that all provider clients implement.

### Provider Registry

#### [MODIFY] `tinycua_sdk/core/providers.py`

- **[Description of change]**: Add `ProviderFactory` type alias, `ProviderInfo` dataclass, `ProviderRegistry` class with `register()`, `create_client()`, `list_providers()`, `is_supported()`, `reset()` methods. Add singleton instance `_provider_registry`. Keep existing `resolve_provider()` and `normalize_base_url()` functions — they remain usable during Phase 1 migration.
- **[Rationale]**: FR-003, FR-004, FR-009. The registry maps provider strings to client factories and provides runtime validation.

### Error Classes

#### [NEW] `tinycua_sdk/core/exceptions.py`

- **[Description of change]**: Create `ProviderNotSupportedError(provider_id, supported_list)`, `ProviderAuthError(message)`, `ProviderApiError(status_code, message)` exception classes.
- **[Dependencies]**: Imported by `providers.py` and provider client implementations.
- **[Rationale]**: FR-009. Clear, actionable error types for provider-related failures.

### Agent Public API

#### [NEW] update exports in `tinycua_sdk/agent/__init__.py`

- **[Description of change]**: Add `CanonicalEvent`, `ContentDeltaEvent`, `ContentDoneEvent`, `ToolCallReadyEvent`, `CanonicalResponse`, `CanonicalMessage`, `CanonicalToolSpec`, `CanonicalUsage`, `RawSseEvent` to `__all__`. Remove old event types that are no longer part of the canonical schema.
- **[Rationale]**: Public API alignment with new canonical schema.

### Tests

#### [NEW] `tests/unit/test_canonical_schema.py`

- **[Description of change]**: Unit tests validating canonical schema TypedDicts type-check and have correct shapes. Tests for `CanonicalEvent` discriminated union narrowing by `type` field.
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

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua_sdk/agent/events.py` | Modify | Canonical SSE schema replaces old TypedDicts; canonical input types added |
| `tinycua_sdk/agent/llm_client.py` | Modify | Refactored ABC with canonical types; `OpenAICompatibleClient` deprecated |
| `tinycua_sdk/core/providers.py` | Modify | `ProviderRegistry` added alongside existing provider functions |
| `tinycua_sdk/core/exceptions.py` | New | Provider-specific exception classes |
| `tinycua_sdk/agent/__init__.py` | Modify | Updated exports for new canonical types |
| `tests/unit/test_canonical_schema.py` | New | Schema type validation tests |
| `tests/unit/test_provider_registry.py` | New | Registry behavior unit tests |
| `tests/unit/test_error_classes.py` | New | Error class unit tests |
| `tests/integration/test_provider_switching.py` | New | Contract-level integration tests |

## Data Model Changes

```python
# Canonical SSE Event Schema (events.py)
ContentDeltaEvent      — type: "content.delta", delta: str, index: int
ContentDoneEvent       — type: "content.done", index: int
ToolCallStartedEvent   — type: "tool_call.started", id, call_id, name
ToolCallArgumentsDeltaEvent — type: "tool_call.arguments.delta", id, arguments: str
ToolCallArgumentsDoneEvent  — type: "tool_call.arguments.done", id, call_id, name, arguments
ToolCallReadyEvent     — type: "tool_call.ready", id, call_id, name, arguments
CanonicalUsage         — input_tokens: int|None, output_tokens: int|None, total_tokens: int|None
ResponseUsageEvent     — type: "response.usage", usage: CanonicalUsage
ResponseCompletedEvent — type: "response.completed", finish_reason: str
ResponseFailedEvent    — type: "response.failed", error: dict
CanonicalResponse      — content, tool_calls, usage, finish_reason, model
RawSseEvent            — provider: str, raw_event: Any

# Canonical Input Types (events.py)
SystemMessage          — role: "system", content: str
UserMessage            — role: "user", content: str
AssistantMessage       — role: "assistant", content: str|None
ToolResultMessage      — role: "tool_result", call_id: str, content: str
CanonicalMessage       — union of SystemMessage | UserMessage | AssistantMessage | ToolResultMessage
CanonicalToolSpec      — name: str, description: str, parameters: dict

# Provider Registry (providers.py)
ProviderFactory        — Callable[[LanguageModel], LLMClient]
ProviderInfo           — id: str, factory, description: str, supported_models: list[str]|None

# Error Classes (exceptions.py)
ProviderNotSupportedError(provider_id, supported_list)
ProviderAuthError(message)
ProviderApiError(status_code, message)
```

## API Changes

### Modified Interfaces

| Interface | Change |
|-----------|--------|
| `LLMClient.chat()` | Parameters: `messages: list[CanonicalMessage]`, `tools: list[CanonicalToolSpec] | None`, added `raw_events: bool = False`. Removed `model_config: LanguageModel` (configuration now bound at construction). Return type now union of `CanonicalResponse` / `AsyncIterator[CanonicalEvent]` / `AsyncIterator[tuple[CanonicalEvent|None, RawSseEvent|None]]`. |
| `LLMClient.close()` | Made abstract (was optional). |

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
| Breaking change to `LLMClient` ABC signature breaks existing subclasses | High | Add new ABC alongside deprecated one (Phase 1 is additive). `OpenAICompatibleClient` remains unchanged so existing consumers are not broken. New consumers adopt the new contract. |
| Old event TypedDict removal breaks existing consumers | High | Update all internal references (loop, agent) to use new canonical types. Export removal is documented in the breaking change migration guide. |
| ProviderRegistry singleton causes test pollution | Medium | Provide `reset()` method; use `autouse` fixture in tests to reset between runs. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-17*
