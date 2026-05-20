# Tasks: Reorganize Client Module — Extract Provider Implementations

Implementation tasks for extracting provider-specific implementations into `tinycua_sdk/providers/`. Check off items as completed.

## TDD Phase (Tests First)

- [x] Create `tests/unit/test_import_sanity.py` — write smoke tests as defined in implementation-plan.md <!-- id: 0 -->
- [x] Run smoke tests — expect RED (failures) since new `providers/` package does not exist yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Create `providers/` Package with Moved Code

- [x] Create `tinycua_sdk/providers/` directory with `__init__.py` <!-- id: 2 -->
  - [x] Add convenience re-exports from all sub-modules for `OpenAIResponsesClient`, `OpenAIChatCompletionsClient`, `resolve_provider`, `normalize_base_url`, `DEFAULT_BASE_URL`, `OPENAI_BASE_URL`, `OPENAI_COMPATIBLE`, `OPENAI_RESPONSES`, `OPENAI_CHAT_COMPLETIONS`, `ProviderRegistry`, `ProviderFactory`, `ProviderInfo`, `get_provider_registry`
- [x] Create `tinycua_sdk/providers/constants.py` — extract constants from `core/providers.py` (`OPENAI_COMPATIBLE`, `OPENAI_RESPONSES`, `OPENAI_CHAT_COMPLETIONS`, `DEFAULT_BASE_URL`, `OPENAI_BASE_URL`, `_PROVIDER_ALIASES`) <!-- id: 3 -->
  - [x] Straight copy — no internal SDK imports (stdlib only)
- [x] Create `tinycua_sdk/providers/registry.py` — extract `ProviderRegistry`, `get_provider_registry` from `core/providers.py` <!-- id: 3b -->
  - [x] Update imports: `from tinycua_sdk.core.providers import OPENAI_COMPATIBLE` → `from tinycua_sdk.providers.constants import OPENAI_COMPATIBLE`; `normalize_base_url` → `from tinycua_sdk.providers.utility import normalize_base_url`
- [x] Create `tinycua_sdk/providers/utility.py` — extract `resolve_provider`, `normalize_base_url`, `ProviderInfo`, `ProviderFactory` from `core/providers.py` <!-- id: 3c -->
  - [x] Update deferred local imports in factory functions: `from tinycua_sdk.agent.llm_client import ...` → `from tinycua_sdk.providers.open_ai import ...`
  - [x] Verify no internal import paths reference the old `core.providers` location
- [x] Create `tinycua_sdk/providers/open_ai.py` — extract `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` from `agent/llm_client.py` <!-- id: 4 -->
  - [x] Move `OpenAIResponsesClient` class + all methods
  - [x] Move `OpenAIChatCompletionsClient` class + all methods
  - [x] Move supporting module-level utilities
  - [x] Move dataclasses
  - [x] Move constants
  - [x] Update import paths
  - [x] Import `_yield_events` from `tinycua_sdk.agent.llm_client`
  - [x] Import `LLMClient` from `tinycua_sdk.agent.llm_client`
  - [x] Set `__all__ = ["OpenAIResponsesClient", "OpenAIChatCompletionsClient"]`
- [x] Verify new files are importable <!-- id: 5 -->

### Phase 2 — Clean up `agent/llm_client.py`

- [x] Remove `OpenAIResponsesClient` class and all its methods <!-- id: 6 -->
- [x] Remove `OpenAIChatCompletionsClient` class and all its methods <!-- id: 7 -->
- [x] Remove supporting module-level utilities that moved to `providers/open_ai.py` <!-- id: 8 -->
- [x] Remove imports that are no longer needed <!-- id: 9 -->
- [x] Update `__all__` — only `["LLMClient"]` remains

### Phase 3 — Delete `core/providers.py`

- [x] Delete `tinycua_sdk/core/providers.py` <!-- id: 10 -->
- [x] Verify `core/__init__.py` does not reference it — remove provider exports <!-- id: 11 -->

### Phase 4 — Update All Internal Imports (Source)

- [x] `agent/__init__.py`: Change imports to `from tinycua_sdk.providers.open_ai import OpenAIResponsesClient, OpenAIChatCompletionsClient` <!-- id: 12 -->
- [x] `agent/executor.py`: Change imports to `from tinycua_sdk.providers.registry import ProviderRegistry, get_provider_registry` <!-- id: 13 -->
- [x] `agent/llm_model.py`: Change import to `from tinycua_sdk.providers.utility import resolve_provider` <!-- id: 14 -->
- [x] `core/__init__.py`: Remove all imports from `core.providers` — keep only `core.exceptions` imports <!-- id: 15 -->

### Phase 5 — Update All Internal Imports (Tests)

- [x] `tests/unit/test_llm_client.py`: Update imports for `OpenAIResponsesClient`, `_normalize_responses_event` from `tinycua_sdk.agent.llm_client` → `tinycua_sdk.providers.open_ai`. `LLMClient` remains from `tinycua_sdk.agent.llm_client`; `_build_payload` from `tinycua_sdk.providers.open_ai`. <!-- id: 16 -->
- [x] `tests/unit/test_providers.py`: Update imports to `tinycua_sdk.providers.utility` / `tinycua_sdk.providers.registry` / `tinycua_sdk.providers.constants` per the actual symbols used <!-- id: 17 -->
- [x] `tests/unit/test_provider_switching.py`: Update imports to `tinycua_sdk.providers.registry` (for `ProviderRegistry`, `get_provider_registry`) and `tinycua_sdk.providers.utility` (for `ProviderInfo`, `ProviderFactory`) <!-- id: 18 -->
- [x] `tests/unit/test_provider_registry.py`: Update imports to `tinycua_sdk.providers.registry` (for `ProviderRegistry`) and `tinycua_sdk.providers.utility` (for `ProviderInfo`) <!-- id: 19 -->
- [x] `tests/unit/test_openai_chat_client.py`: Update import to `tinycua_sdk.providers.open_ai` <!-- id: 20 -->
- [x] `tests/unit/test_executor_integration.py`: Update imports to `tinycua_sdk.providers.registry` (for `ProviderRegistry`) and `tinycua_sdk.providers.utility` (for `ProviderInfo`) <!-- id: 21 -->
- [x] `tests/unit/conftest.py`: Update all `OpenAIResponsesClient` imports to `tinycua_sdk.providers.open_ai` <!-- id: 22 -->
- [x] `tests/integration/test_provider_switching.py`: Update imports to `tinycua_sdk.providers.registry` and `tinycua_sdk.providers.utility` <!-- id: 23 -->
- [x] `tests/integration/test_openai_chat_completions_provider.py`: Update imports to `tinycua_sdk.providers.open_ai` and `tinycua_sdk.providers.registry` <!-- id: 24 -->
- [x] `tests/integration/test_language_model.py`: Update import to `tinycua_sdk.providers.utility` <!-- id: 25 -->

## Testing Phase

- [x] Run smoke tests — expect GREEN (all pass): `cd src/tinycua-sdk && uv run python -c "from tinycua_sdk.providers.open_ai import OpenAIResponsesClient; from tinycua_sdk.providers.utility import resolve_provider; from tinycua_sdk.providers.registry import ProviderRegistry; from tinycua_sdk.providers.constants import DEFAULT_BASE_URL; print('new paths OK')"` <!-- id: 26 -->
- [x] Run unit test suite: `cd src/tinycua-sdk && uv run pytest tests/unit/ -v` <!-- id: 27 -->
- [ ] Run full test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 28 -->

## Verification Phase

- [x] Verify convenience namespace: `uv run python -c "from tinycua_sdk.providers import OpenAIResponsesClient, resolve_provider, ProviderRegistry, DEFAULT_BASE_URL; print('convenience namespace OK')"` <!-- id: 31 -->
- [x] Verify circular import safety: `uv run python -c "import tinycua_sdk; print('no circular import')"` <!-- id: 32 -->

## Documentation Phase

- [x] Update module-level docstrings in `providers/__init__.py`, `providers/constants.py`, `providers/registry.py`, `providers/utility.py`, `providers/open_ai.py` <!-- id: 33 -->
- [x] Update module-level docstring in `agent/llm_client.py` to reflect reduced scope <!-- id: 34 -->

## Review and Merge

- [ ] Create pull request <!-- id: 35 -->
- [ ] Address review feedback <!-- id: 36 -->
- [ ] Merge to main branch <!-- id: 37 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-19*
