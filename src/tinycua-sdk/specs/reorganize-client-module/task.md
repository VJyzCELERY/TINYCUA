# Tasks: Reorganize Client Module — Extract Provider Implementations

Implementation tasks for extracting provider-specific implementations into `tinycua_sdk/providers/`. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Create `tests/unit/test_import_sanity.py` — write smoke tests as defined in implementation-plan.md <!-- id: 0 -->
- [ ] Run smoke tests — expect RED (failures) since new `providers/` package does not exist yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Create `providers/` Package with Moved Code

- [ ] Create `tinycua_sdk/providers/` directory with `__init__.py` <!-- id: 2 -->
  - [ ] Add convenience re-exports for `OpenAIResponsesClient`, `OpenAIChatCompletionsClient`, `resolve_provider`, `normalize_base_url`, `DEFAULT_BASE_URL`, `OPENAI_COMPATIBLE`, `OPENAI_RESPONSES`, `OPENAI_CHAT_COMPLETIONS`, `ProviderRegistry`, `get_provider_registry`
- [ ] Create `tinycua_sdk/providers/providers.py` — verbatim copy of `tinycua_sdk/core/providers.py` <!-- id: 3 -->
  - [ ] Update deferred local imports in `_register_defaults()`: `from tinycua_sdk.agent.llm_client import ...` → `from tinycua_sdk.providers.open_ai import ...`
  - [ ] Verify no internal import paths reference the old `core.providers` location
- [ ] Create `tinycua_sdk/providers/open_ai.py` — extract `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` from `agent/llm_client.py` <!-- id: 4 -->
  - [ ] Move `OpenAIResponsesClient` class + all methods (`_get_client`, `_build_request_kwargs`, `_handle_provider_error`, `_normalize_non_streaming_response`, `_chat_impl`, `_chat_sync`, `_chat_stream`, `close`)
  - [ ] Move `OpenAIChatCompletionsClient` class + all methods (`_get_client`, `_translate_chat_messages`, `_translate_chat_tools`, `_build_chat_payload`, `_normalize_chunk_usage_only`, `_normalize_chunk_content`, `_normalize_chunk_tool_calls`, `_normalize_chunk_finalize`, `_normalize_chat_chunk`, `_normalize_non_streaming_response`, `_handle_provider_error`, `_chat_impl`, `_chat_sync`, `_capture_tool_calls`, `_chat_stream`, `close`)
  - [ ] Move supporting module-level utilities: `_normalize_responses_event`, `_normalize_content_event`, `_normalize_reasoning_event`, `_normalize_tool_event`, `_normalize_lifecycle_event`, `_translate_messages`, `_translate_tools`, `_normalize_chat_chunk` and sub-functions
  - [ ] Move dataclasses: `ToolCallAccumulator`, `_accumulator_to_chat_tool_calls`, `ChoiceAccumulator`
  - [ ] Move constants: `_SUPPORTED_FIELDS`, `_FIELD_MAP`, `_CHAT_SUPPORTED_FIELDS`
  - [ ] Update imports: `from tinycua_sdk.core.providers import normalize_base_url` → `from tinycua_sdk.providers.providers import normalize_base_url`
  - [ ] Import `_yield_events` from `tinycua_sdk.agent.llm_client`
  - [ ] Import `LLMClient` from `tinycua_sdk.agent.llm_client`
  - [ ] Import `LanguageModel` from `tinycua_sdk.agent.llm_model`
  - [ ] Import `ProviderApiError`, `ProviderAuthError` from `tinycua_sdk.core.exceptions`
  - [ ] Set `__all__ = ["OpenAIResponsesClient", "OpenAIChatCompletionsClient"]`
- [ ] Verify new files are importable: `uv run python -c "from tinycua_sdk.providers import OpenAIResponsesClient, resolve_provider; print('OK')"` <!-- id: 5 -->

### Phase 2 — Clean up `agent/llm_client.py`

- [ ] Remove `OpenAIResponsesClient` class and all its methods <!-- id: 6 -->
- [ ] Remove `OpenAIChatCompletionsClient` class and all its methods <!-- id: 7 -->
- [ ] Remove supporting module-level utilities that moved to `providers/open_ai.py`:
  - `_normalize_responses_event`, `_normalize_content_event`, `_normalize_reasoning_event`, `_normalize_tool_event`, `_normalize_lifecycle_event`
  - `_translate_messages`, `_translate_tools`
  - `_normalize_chat_chunk` and sub-functions
  - `ToolCallAccumulator`, `ChoiceAccumulator`, `_accumulator_to_chat_tool_calls`
  - `_SUPPORTED_FIELDS`, `_FIELD_MAP`, `_CHAT_SUPPORTED_FIELDS`
  - `_build_request_kwargs` (Responses), `_build_chat_payload`, `_capture_tool_calls`
  - `_normalize_non_streaming_response` (both variants)
  - `_handle_provider_error` (both variants)
  - `_translate_chat_messages`, `_translate_chat_tools`
- [ ] Remove imports that are no longer needed:
  - `from dataclasses import dataclass, field as dataclass_field`
  - `from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError`
  - `from tinycua_sdk.core.providers import normalize_base_url`
  - `from openai import AsyncOpenAI` (TYPE_CHECKING block)
- [ ] Update `__all__` — only `["LLMClient"]` remains <!-- id: 8 -->
- [ ] Update module docstring to reflect that only `LLMClient` ABC lives here <!-- id: 9 -->
- [ ] Keep `_yield_events` and `_build_payload` (legacy) in the module

### Phase 3 — Delete `core/providers.py`

- [ ] Delete `tinycua_sdk/core/providers.py` <!-- id: 10 -->
- [ ] Verify `core/__init__.py` does not reference it — remove provider exports <!-- id: 11 -->

### Phase 4 — Update All Internal Imports (Source)

- [ ] `agent/__init__.py`: Change imports to `from tinycua_sdk.providers.open_ai import OpenAIResponsesClient, OpenAIChatCompletionsClient` <!-- id: 12 -->
- [ ] `agent/executor.py`: Change imports to `from tinycua_sdk.providers.providers import ProviderRegistry, get_provider_registry` <!-- id: 13 -->
- [ ] `agent/llm_model.py`: Change import to `from tinycua_sdk.providers.providers import resolve_provider` <!-- id: 14 -->
- [ ] `core/__init__.py`: Remove all imports from `core.providers` — keep only `core.exceptions` imports <!-- id: 15 -->

### Phase 5 — Update All Internal Imports (Tests)

- [ ] `tests/unit/test_llm_client.py`: Update imports for `OpenAIResponsesClient`, `_normalize_responses_event` from `tinycua_sdk.agent.llm_client` → `tinycua_sdk.providers.open_ai`. `LLMClient`, `_build_payload` remain from `tinycua_sdk.agent.llm_client`. <!-- id: 16 -->
- [ ] `tests/unit/test_providers.py`: Update imports to `tinycua_sdk.providers.providers` <!-- id: 17 -->
- [ ] `tests/unit/test_provider_switching.py`: Update imports to `tinycua_sdk.providers.providers` <!-- id: 18 -->
- [ ] `tests/unit/test_provider_registry.py`: Update imports to `tinycua_sdk.providers.providers` <!-- id: 19 -->
- [ ] `tests/unit/test_openai_chat_client.py`: Update import to `tinycua_sdk.providers.open_ai` <!-- id: 20 -->
- [ ] `tests/unit/test_executor_integration.py`: Update imports to `tinycua_sdk.providers.providers` <!-- id: 21 -->
- [ ] `tests/unit/conftest.py`: Update all `OpenAIResponsesClient` imports to `tinycua_sdk.providers.open_ai` <!-- id: 22 -->
- [ ] `tests/integration/test_provider_switching.py`: Update imports to `tinycua_sdk.providers.providers` <!-- id: 23 -->
- [ ] `tests/integration/test_openai_chat_completions_provider.py`: Update imports to `tinycua_sdk.providers.open_ai` and `tinycua_sdk.providers.providers` <!-- id: 24 -->
- [ ] `tests/integration/test_language_model.py`: Update import to `tinycua_sdk.providers.providers` <!-- id: 25 -->

## Testing Phase

- [ ] Run smoke tests — expect GREEN (all pass): `cd src/tinycua-sdk && uv run python -c "from tinycua_sdk.providers.open_ai import OpenAIResponsesClient; print('new path OK')"` <!-- id: 26 -->
- [ ] Run unit test suite: `cd src/tinycua-sdk && uv run pytest tests/unit/ -v` <!-- id: 27 -->
- [ ] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 28 -->

## Verification Phase

- [ ] Verify old import path raises `ImportError`: `uv run python -c "from tinycua_sdk.agent.llm_client import OpenAIResponsesClient" 2>&1 | grep -q ImportError && echo 'old path removed'` <!-- id: 29 -->
- [ ] Verify `core.providers` is deleted: `uv run python -c "from tinycua_sdk.core.providers import resolve_provider" 2>&1 | grep -q ImportError && echo 'core.providers deleted'` <!-- id: 30 -->
- [ ] Verify convenience namespace: `uv run python -c "from tinycua_sdk.providers import OpenAIResponsesClient, resolve_provider; print('convenience namespace OK')"` <!-- id: 31 -->
- [ ] Verify circular import safety: `uv run python -c "import tinycua_sdk; print('no circular import')"` <!-- id: 32 -->

## Documentation Phase

- [ ] Update module-level docstrings in `providers/__init__.py`, `providers/providers.py`, `providers/open_ai.py` <!-- id: 33 -->
- [ ] Update module-level docstring in `agent/llm_client.py` to reflect reduced scope <!-- id: 34 -->

## Review and Merge

- [ ] Create pull request <!-- id: 35 -->
- [ ] Address review feedback <!-- id: 36 -->
- [ ] Merge to main branch <!-- id: 37 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-19*
