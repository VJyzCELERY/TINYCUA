# Tasks: Unified LLM Client Interface — Phase 1 (Foundation)

Implementation tasks for Phase 1 of the Unified LLM Client Interface. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (`tests/integration/test_provider_switching.py`): registry switching, unsupported providers, raw_events validation <!-- id: 1 -->
  - [ ] Test: `openai-responses` default registration resolves correctly via registry <!-- id: 1a -->
  - [ ] Test: old provider strings (`"openai"`, `"openai-compatible"`) raise `ProviderNotSupportedError` <!-- id: 1b -->
- [ ] Write unit tests (`tests/unit/test_canonical_schema.py`): canonical event TypedDict shapes and type narrowing <!-- id: 2 -->
- [ ] Write unit tests (`tests/unit/test_provider_registry.py`): register, reset, create_client, list, is_supported, error cases <!-- id: 3 -->
- [ ] Write unit tests (`tests/unit/test_error_classes.py`): `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` attributes and representation <!-- id: 4 -->
- [ ] Write unit/contract tests (`tests/unit/test_openai_compatible_client.py`): `OpenAICompatibleClient` under refactored `LLMClient` ABC <!-- id: 4a -->
  - [ ] Test: instantiates from `LanguageModel` and implements `_chat_impl()` <!-- id: 4a1 -->
  - [ ] Test: resolves through `ProviderRegistry.create_client()` <!-- id: 4a2 -->
  - [ ] Test: non-streaming `chat()` returns correct `LLMResponse` shape <!-- id: 4a3 -->
  - [ ] Test: streaming `chat()` yields canonical `LLMEvent` items <!-- id: 4a4 -->
  - [ ] Test: `raw_events=True` with `stream=False` raises `ValueError` via base class <!-- id: 4a5 -->
- [ ] Run all new tests — expect RED (failures) since no implementation yet <!-- id: 5 -->

## Implementation Phase

### Task A: Core Exception Classes

- [ ] Create `tinycua_sdk/core/exceptions.py` with `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` <!-- id: 6 -->
- [ ] Wire into `core/__init__.py` exports <!-- id: 7 -->

### Task B: Canonical SSE Event Schema + Input Types

- [ ] Add new canonical TypedDicts to `tinycua_sdk/agent/events.py` replacing existing ones <!-- id: 8 -->
  - [ ] Add `ContentDeltaEvent`, `ContentDoneEvent` TypedDicts
  - [ ] Add `ToolCallStartedEvent`, `ToolCallArgumentsDeltaEvent`, `ToolCallArgumentsDoneEvent`, `ToolCallReadyEvent` TypedDicts (refined from existing)
  - [ ] Add `TokenUsage`, `ResponseUsageEvent`, `ResponseCompletedEvent`, `ResponseFailedEvent` TypedDicts (refined)
  - [ ] Add `LLMEvent` union type alias
  - [ ] Add `LLMResponse` TypedDict
  - [ ] Add `RawSseEvent` TypedDict
  - [ ] Add canonical input types: `SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolResultMessage`, `LLMMessage` union, `LLMToolSpec`
  - [ ] Remove old event TypedDicts (`ResponseCreatedEvent`, `ResponseCancelledEvent`, `ResponseOutputTextDeltaEvent`, `ResponseToolCallDeltaEvent`, `ErrorEvent`, `ResponseInProgressEvent`) — consumers must migrate to new canonical types
  - [ ] Update `__all__` in `events.py` with new types only
- [ ] Update `tinycua_sdk/agent/__init__.py` exports: replace existing types with new canonical types <!-- id: 9 -->

### Task C: Refactor `LLMClient` ABC

- [ ] Refactor existing `LLMClient` ABC in `tinycua_sdk/agent/llm_client.py` with canonical event contract <!-- id: 10 -->
  - [ ] Refactor existing `LLMClient` ABC in-place — remove old method signatures, add canonical types
  - [ ] Define concrete `chat()` with canonical types: `messages: list[LLMMessage]`, `tools: list[LLMToolSpec] | None`, `raw_events: bool = False`
  - [ ] Add return type union: `LLMResponse | AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]`
  - [ ] Concrete `chat()` performs shared validation: `raw_events=True` + `stream=False` → `ValueError`, then delegates to abstract `_chat_impl()`
  - [ ] Define abstract `_chat_impl(messages, tools, stream, raw_events)` — `raw_events` is passed through so providers can yield paired `(canonical, raw)` tuples when requested
  - [ ] Add abstract `close()` method
  - [ ] Update docstring with canonical event contract and tool-call state machine rules
- [ ] Update `OpenAICompatibleClient` to implement new `LLMClient` contract (requires `_chat_impl()`) <!-- id: 11 -->
  - Note: This is a breaking change; backward compatibility is not maintained

### Task C.5: Default Provider & Base URL Migration

- [ ] Update `LanguageModel.provider` default from `"openai-compatible"` to `"openai-responses"` in `tinycua_sdk/agent/llm_model.py` <!-- id: 12a -->
- [ ] Update `resolve_provider()` / `VALID_PROVIDERS` in `tinycua_sdk/core/providers.py` to accept `"openai-responses"` as a valid provider identifier. Provider rejection is registry-driven — `LanguageModel` normalizes without hard-coding the recognized set, and `ProviderRegistry.create_client()` rejects any unrecognized provider via `ProviderNotSupportedError` <!-- id: 12b -->
- [ ] Update `normalize_base_url(None, "openai-responses")` to return `"https://api.openai.com/v1"` instead of the fallthrough localhost default <!-- id: 12c -->
- [ ] Add tests:
  - [ ] `LanguageModel()` default provider resolves to `"openai-responses"` <!-- id: 12d -->
  - [ ] `normalize_base_url(None, "openai-responses")` returns OpenAI API URL <!-- id: 12e -->
  - [ ] Unrecognized provider strings (e.g. `LanguageModel(provider="openai")` or `"openai-compatible"`) raise `ProviderNotSupportedError` at `ProviderRegistry.create_client()` time — rejection is registry-driven, not hard-coded in `LanguageModel` <!-- id: 12f -->

### Task D: ProviderRegistry Implementation

- [ ] Add imports for `LanguageModel`, `LLMClient`, error classes in `tinycua_sdk/core/providers.py` — use `TYPE_CHECKING` + `from __future__ import annotations` to avoid circular imports with `agent.llm_client` <!-- id: 13 -->
- [ ] Add `ProviderFactory = Callable[[LanguageModel], LLMClient]` type alias under `TYPE_CHECKING` guard <!-- id: 14 -->
- [ ] Add `ProviderInfo` dataclass with `id`, `factory`, `description`, `supported_models` <!-- id: 15 -->
- [ ] Implement `ProviderRegistry` class <!-- id: 16 -->
  - [ ] `register(provider_id, factory, metadata)`
  - [ ] `create_client(model_config) → LLMClient` — raises `ProviderNotSupportedError` for unknown providers
  - [ ] `list_providers() → list[ProviderInfo]`
  - [ ] `is_supported(provider_id) → bool`
  - [ ] `reset()` — clear all registered providers
- [ ] Add singleton instance `_provider_registry` and convenience function `get_provider_registry()` <!-- id: 17 -->
- [ ] Keep existing `resolve_provider()`, `VALID_PROVIDERS` infrastructure unchanged (they remain usable during Phase 1 migration) <!-- id: 18 -->
- [ ] Update `normalize_base_url()` to add `"openai-responses"` → OpenAI API base URL mapping (was falling through to localhost default) <!-- id: 18b -->
- [ ] Add default registration: auto-register `"openai-responses"` → `OpenAICompatibleClient` factory in the singleton `_provider_registry` using a deferred local import (`from tinycua_sdk.agent.llm_client import OpenAICompatibleClient` inside the factory body) <!-- id: 18a -->
  - [ ] `openai-responses` is the only pre-registered provider in Phase 1 — old strings (`"openai"`, `"openai-compatible"`) are NOT registered
  - [ ] `ProviderRegistry.create_client()` raises `ProviderNotSupportedError` for old strings, listing `openai-responses` as the supported migration target
- [ ] Update `core/__init__.py` exports for new types <!-- id: 19 -->

## Testing Phase

- [ ] Run integration tests (`tests/integration/test_provider_switching.py`) — expect GREEN (all pass) <!-- id: 20 -->
- [ ] Run unit tests (`tests/unit/test_canonical_schema.py`) — expect GREEN <!-- id: 21 -->
- [ ] Run unit tests (`tests/unit/test_provider_registry.py`) — expect GREEN <!-- id: 22 -->
- [ ] Run unit tests (`tests/unit/test_error_classes.py`) — expect GREEN <!-- id: 23 -->
- [ ] Run unit/contract tests (`tests/unit/test_openai_compatible_client.py`) — expect GREEN <!-- id: 23a -->
- [ ] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 24 -->
- [ ] Run type checker: `cd src/tinycua-sdk && uv run mypy tinycua_sdk/agent/events.py tinycua_sdk/agent/llm_client.py tinycua_sdk/core/` <!-- id: 25 -->

## Documentation Phase

- [ ] Update `AGENTS.md` or per-subproject agent notes with migration guidance for new canonical types <!-- id: 26 -->
- [ ] Update changelog entry for Phase 1 breaking changes <!-- id: 27 -->

## Review and Merge

- [ ] Create PR for Phase 1 foundation changes <!-- id: 28 -->
- [ ] Address review feedback <!-- id: 29 -->
- [ ] Merge to main branch <!-- id: 30 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-17*
