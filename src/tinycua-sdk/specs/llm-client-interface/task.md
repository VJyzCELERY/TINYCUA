# Tasks: Unified LLM Client Interface — Phase 1 (Foundation)

Implementation tasks for Phase 1 of the Unified LLM Client Interface. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests (`tests/integration/test_provider_switching.py`): registry switching, unsupported providers, raw_events validation <!-- id: 1 -->
  - [x] Test: `openai-responses` default registration resolves correctly via registry <!-- id: 1a -->
  - [x] Test: deprecated `"openai-compatible"` and unknown provider strings raise `ProviderNotSupportedError`; `"openai"` resolves as a deprecated alias for `"openai-responses"` <!-- id: 1b -->
- [x] Write unit tests (`tests/unit/test_canonical_schema.py`): canonical event TypedDict shapes and type narrowing <!-- id: 2 -->
- [x] Write unit tests (`tests/unit/test_provider_registry.py`): register, reset, create_client, list, is_supported, error cases <!-- id: 3 -->
- [x] Write unit tests (`tests/unit/test_error_classes.py`): `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` attributes and representation <!-- id: 4 -->
- [x] Write unit/contract tests (`tests/unit/test_openai_compatible_client.py`): `OpenAICompatibleClient` under refactored `LLMClient` ABC <!-- id: 4a -->
  - [x] Test: instantiates from `LanguageModel` and implements `_chat_impl()` <!-- id: 4a1 -->
  - [x] Test: resolves through `ProviderRegistry.create_client()` <!-- id: 4a2 -->
  - [x] Test: non-streaming `chat()` returns correct `LLMResponse` shape <!-- id: 4a3 -->
  - [x] Test: streaming `chat()` yields canonical `LLMEvent` items <!-- id: 4a4 -->
  - [x] Test: `raw_events=True` with `stream=False` raises `ValueError` via base class <!-- id: 4a5 -->
- [x] Run all new tests — expect RED (failures) since no implementation yet <!-- id: 5 -->

## Implementation Phase

### Task A: Core Exception Classes

- [x] Create `tinycua_sdk/core/exceptions.py` with `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` <!-- id: 6 -->
- [x] Wire into `core/__init__.py` exports <!-- id: 7 -->

### Task B: Canonical SSE Event Schema + Input Types

- [x] Add new canonical TypedDicts to `tinycua_sdk/agent/events.py` replacing existing ones <!-- id: 8 -->
  - [x] Add `ContentDeltaEvent` (type: `"response.output_text.delta"`), `ContentDoneEvent` (type: `"response.output_text.done"`) TypedDicts — Responses-shaped canonical event names
  - [x] Add `ToolCallStartedEvent` (type: `"response.output_item.added"`), `ToolCallArgumentsDeltaEvent` (type: `"response.function_call_arguments.delta"`), `ToolCallArgumentsDoneEvent` (type: `"response.function_call_arguments.done"`), `ToolCallReadyEvent` (type: `"tool_call.ready"`, synthetic) TypedDicts — Responses-shaped canonical event names
  - [x] Add `TokenUsage`, `ResponseUsageEvent`, `ResponseCompletedEvent`, `ResponseFailedEvent` TypedDicts (refined)
  - [x] Add `LLMEvent` union type alias
  - [x] Add `LLMResponse` TypedDict
  - [x] Add `RawSseEvent` TypedDict
  - [x] Add canonical input types: `SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolResultMessage`, `LLMMessage` union, `LLMToolSpec`
  - [x] Remove old content/tool event TypedDicts (`ResponseOutputTextDeltaEvent`, `ResponseToolCallDeltaEvent`) — consumers must migrate to new canonical types
  - [x] Lifecycle/error TypedDicts (`ResponseCreatedEvent`, `ResponseCancelledEvent`, `ErrorEvent`, `ResponseInProgressEvent`) are canonical and remain in the ``LLMEvent`` union
  - [x] Update `__all__` in `events.py` with new types only
- [x] Update `tinycua_sdk/agent/__init__.py` exports: replace existing types with new canonical types <!-- id: 9 -->

### Task C: Refactor `LLMClient` ABC

- [x] Refactor existing `LLMClient` ABC in `tinycua_sdk/agent/llm_client.py` with canonical event contract <!-- id: 10 -->
  - [x] Refactor existing `LLMClient` ABC in-place — remove old method signatures, add canonical types
  - [x] Define concrete `chat()` with canonical types: `messages: list[LLMMessage]`, `tools: list[LLMToolSpec] | None`, `raw_events: bool = False`
  - [x] Add return type union: `LLMResponse | AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]`
  - [x] Concrete `chat()` performs shared validation: `raw_events=True` + `stream=False` → `ValueError`, then delegates to abstract `_chat_impl()`
  - [x] Define abstract `_chat_impl(messages, tools, stream, raw_events)` — `raw_events` is passed through so providers can yield paired `(canonical, raw)` tuples when requested
  - [x] Add abstract `close()` method
  - [x] Update docstring with canonical event contract and tool-call state machine rules
- [x] Update `OpenAICompatibleClient` to implement new `LLMClient` contract (requires `_chat_impl()`) <!-- id: 11 -->
  - Note: This is a breaking change; backward compatibility is not maintained

### Task C.5: Default Provider & Base URL Migration

- [x] Update `LanguageModel.provider` default from `"openai-compatible"` to `"openai-responses"` in `tinycua_sdk/agent/llm_model.py` <!-- id: 12a -->
- [x] Update `resolve_provider()` / `VALID_PROVIDERS` in `tinycua_sdk/core/providers.py` to accept `"openai-responses"` as a valid provider identifier. Provider rejection is registry-driven — `LanguageModel` normalizes without hard-coding the recognized set, and `ProviderRegistry.create_client()` rejects any unrecognized provider via `ProviderNotSupportedError` <!-- id: 12b -->
- [x] Update `normalize_base_url(None, "openai-responses")` to return `"https://api.openai.com/v1"` instead of the fallthrough localhost default <!-- id: 12c -->
- [x] Add tests:
  - [x] `LanguageModel()` default provider resolves to `"openai-responses"` <!-- id: 12d -->
  - [x] `normalize_base_url(None, "openai-responses")` returns OpenAI API URL <!-- id: 12e -->
  - [x] Unrecognized provider strings (e.g. `LanguageModel(provider="openai-compatible")` or `"unknown-provider"`) raise `ProviderNotSupportedError` at `ProviderRegistry.create_client()` time — rejection is registry-driven, not hard-coded in `LanguageModel`. Note: `"openai"` is a deprecated compatibility alias that resolves to `"openai-responses"` in Phase 1. <!-- id: 12f -->

### Task D: ProviderRegistry Implementation

- [x] Add imports for `LanguageModel`, `LLMClient`, error classes in `tinycua_sdk/core/providers.py` — use `TYPE_CHECKING` + `from __future__ import annotations` to avoid circular imports with `agent.llm_client` <!-- id: 13 -->
- [x] Add `ProviderFactory = Callable[[LanguageModel], LLMClient]` type alias under `TYPE_CHECKING` guard <!-- id: 14 -->
- [x] Add `ProviderInfo` dataclass with `id`, `factory`, `description`, `supported_models` <!-- id: 15 -->
- [x] Implement `ProviderRegistry` class <!-- id: 16 -->
  - [x] `register(provider_id, factory, metadata)`
  - [x] `create_client(model_config) → LLMClient` — raises `ProviderNotSupportedError` for unknown providers
  - [x] `list_providers() → list[ProviderInfo]`
  - [x] `is_supported(provider_id) → bool`
  - [x] `reset()` — clear all registered providers
- [x] Add singleton instance `_provider_registry` and convenience function `get_provider_registry()` <!-- id: 17 -->
- [x] Preserve `resolve_provider()` and `VALID_PROVIDERS` as migration-compatibility helpers — existing code can still reference them during the Phase 1 transition — but explicitly update them to accept `"openai-responses"` and remove any hard-coded validation of the registered-provider set from `LanguageModel`. Final support/rejection of provider strings is now owned by `ProviderRegistry.create_client()` via `ProviderNotSupportedError`. The helpers are preserved as concepts (provider normalization, default URL mapping) but their validation role is superseded by the registry. <!-- id: 18 -->
- [x] Update `normalize_base_url()` to add `"openai-responses"` → OpenAI API base URL mapping (was falling through to localhost default) <!-- id: 18b -->
- [x] Add default registration: auto-register `"openai-responses"` → `OpenAIResponsesClient` factory in the singleton `_provider_registry` using a deferred local import (`from tinycua_sdk.agent.llm_client import OpenAIResponsesClient` inside the factory body) <!-- id: 18a -->
  - [x] `openai-responses` is the only pre-registered provider in Phase 1 — old strings (`"openai"`, `"openai-compatible"`) are NOT registered
  - [x] `ProviderRegistry.create_client()` raises `ProviderNotSupportedError` for old strings, listing `openai-responses` as the supported migration target
- [x] Update `core/__init__.py` exports for new types <!-- id: 19 -->

### Task E: AgentExecutor Integration with ProviderRegistry

- [x] Update `_get_llm_client()` in `tinycua_sdk/agent/executor.py` to use `get_provider_registry().create_client(self.config.llm_model)` instead of hardcoded `OpenAICompatibleClient()` — ensures the executor respects `LanguageModel.provider` switching through the registry <!-- id: 20a -->
- [x] Ensure `AgentExecutor.__init__()` or `self.config.llm_model` always provides a `LanguageModel` so the registry can resolve the provider correctly; add type annotations if needed <!-- id: 20b -->
- [x] Update `_call_llm()` signature: remove `model` positional parameter (configuration is bound at client construction); update call to `client.chat(messages, tool_schemas, stream=stream)` using new canonical types (no per-call `model` or `model_config` parameter) <!-- id: 20c -->
- [x] Write tests proving `AgentExecutor` uses the registry and respects `LanguageModel.provider` switching — include tests for `_get_llm_client()` resolving different providers and `_call_llm()` using the new `LLMClient.chat()` signature <!-- id: 20d -->

## Testing Phase

- [x] Run integration tests (`tests/integration/test_provider_switching.py`) — expect GREEN (all pass) <!-- id: 20 -->
- [x] Run unit tests (`tests/unit/test_canonical_schema.py`) — expect GREEN <!-- id: 21 -->
- [x] Run unit tests (`tests/unit/test_provider_registry.py`) — expect GREEN <!-- id: 22 -->
- [x] Run unit tests (`tests/unit/test_error_classes.py`) — expect GREEN <!-- id: 23 -->
- [x] Run unit/contract tests (`tests/unit/test_openai_compatible_client.py`) — expect GREEN <!-- id: 23a -->
- [x] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 24 -->
- [x] Run type checker: `cd src/tinycua-sdk && uv run mypy tinycua_sdk/agent/events.py tinycua_sdk/agent/llm_client.py tinycua_sdk/core/` <!-- id: 25 -->

<!-- Documentation and PR tasks deferred to separate documentation PR -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-17*
