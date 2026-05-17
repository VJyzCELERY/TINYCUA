# Tasks: Unified LLM Client Interface — Phase 1 (Foundation)

Implementation tasks for Phase 1 of the Unified LLM Client Interface. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (`tests/integration/test_provider_switching.py`): registry switching, unsupported providers, raw_events validation <!-- id: 1 -->
- [ ] Write unit tests (`tests/unit/test_canonical_schema.py`): canonical event TypedDict shapes and type narrowing <!-- id: 2 -->
- [ ] Write unit tests (`tests/unit/test_provider_registry.py`): register, reset, create_client, list, is_supported, error cases <!-- id: 3 -->
- [ ] Write unit tests (`tests/unit/test_error_classes.py`): `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` attributes and representation <!-- id: 4 -->
- [ ] Run all new tests — expect RED (failures) since no implementation yet <!-- id: 5 -->

## Implementation Phase

### Task A: Core Exception Classes

- [ ] Create `tinycua_sdk/core/exceptions.py` with `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` <!-- id: 6 -->
- [ ] Wire into `core/__init__.py` exports <!-- id: 7 -->

### Task B: Canonical SSE Event Schema + Input Types

- [ ] Add new canonical TypedDicts to `tinycua_sdk/agent/events.py` alongside existing ones <!-- id: 8 -->
  - [ ] Add `ContentDeltaEvent`, `ContentDoneEvent` TypedDicts
  - [ ] Add `ToolCallStartedEvent`, `ToolCallArgumentsDeltaEvent`, `ToolCallArgumentsDoneEvent`, `ToolCallReadyEvent` TypedDicts (refined from existing)
  - [ ] Add `CanonicalUsage`, `ResponseUsageEvent`, `ResponseCompletedEvent`, `ResponseFailedEvent` TypedDicts (refined)
  - [ ] Add `CanonicalEvent` union type alias
  - [ ] Add `CanonicalResponse` TypedDict
  - [ ] Add `RawSseEvent` TypedDict
  - [ ] Add canonical input types: `SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolResultMessage`, `CanonicalMessage` union, `CanonicalToolSpec`
  - [ ] Keep old event TypedDicts (`ResponseCreatedEvent`, `ResponseCancelledEvent`, `ResponseOutputTextDeltaEvent`, `ResponseToolCallDeltaEvent`, `ErrorEvent`, `ResponseInProgressEvent`) for backward compatibility (removal deferred to Phase 2)
  - [ ] Update `__all__` in `events.py` with new types; keep existing exports
- [ ] Update `tinycua_sdk/agent/__init__.py` exports: add new types alongside existing ones <!-- id: 9 -->

### Task C: Refactor `LLMClient` ABC

- [ ] Refactor existing `LLMClient` ABC in `tinycua_sdk/agent/llm_client.py` with canonical event contract <!-- id: 10 -->
  - [ ] Refactor existing `LLMClient` ABC in-place — remove old method signatures, add canonical types
  - [ ] Define concrete `chat()` with canonical types: `messages: list[CanonicalMessage]`, `tools: list[CanonicalToolSpec] | None`, `raw_events: bool = False`
  - [ ] Add return type union: `CanonicalResponse | AsyncIterator[CanonicalEvent] | AsyncIterator[tuple[CanonicalEvent | None, RawSseEvent | None]]`
  - [ ] Concrete `chat()` performs shared validation: `raw_events=True` + `stream=False` → `ValueError`, then delegates to abstract `_chat_impl()`
  - [ ] Define abstract `_chat_impl()` with same signature minus `raw_events` — subclasses implement provider-specific logic
  - [ ] Add abstract `close()` method
  - [ ] Update docstring with canonical event contract and tool-call state machine rules
- [ ] Update `OpenAICompatibleClient` to implement new `LLMClient` contract (requires `_chat_impl()`) <!-- id: 11 -->
  - Note: This is a breaking change; backward compatibility is not maintained

### Task D: ProviderRegistry Implementation

- [ ] Add imports for `LanguageModel`, `LLMClient`, error classes in `tinycua_sdk/core/providers.py` <!-- id: 13 -->
- [ ] Add `ProviderFactory = Callable[[LanguageModel], LLMClient]` type alias <!-- id: 14 -->
- [ ] Add `ProviderInfo` dataclass with `id`, `factory`, `description`, `supported_models` <!-- id: 15 -->
- [ ] Implement `ProviderRegistry` class <!-- id: 16 -->
  - [ ] `register(provider_id, factory, metadata)`
  - [ ] `create_client(model_config) → LLMClient` — raises `ProviderNotSupportedError` for unknown providers
  - [ ] `list_providers() → list[ProviderInfo]`
  - [ ] `is_supported(provider_id) → bool`
  - [ ] `reset()` — clear all registered providers
- [ ] Add singleton instance `_provider_registry` and convenience function `get_provider_registry()` <!-- id: 17 -->
- [ ] Keep existing `resolve_provider()`, `normalize_base_url()`, `VALID_PROVIDERS`, etc. unchanged <!-- id: 18 -->
- [ ] Update `core/__init__.py` exports for new types <!-- id: 19 -->

## Testing Phase

- [ ] Run integration tests (`tests/integration/test_provider_switching.py`) — expect GREEN (all pass) <!-- id: 20 -->
- [ ] Run unit tests (`tests/unit/test_canonical_schema.py`) — expect GREEN <!-- id: 21 -->
- [ ] Run unit tests (`tests/unit/test_provider_registry.py`) — expect GREEN <!-- id: 22 -->
- [ ] Run unit tests (`tests/unit/test_error_classes.py`) — expect GREEN <!-- id: 23 -->
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
