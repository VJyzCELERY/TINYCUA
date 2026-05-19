# Implementation: Reorganize Client Module — Extract Provider Implementations

Extract provider-specific LLM client implementations (`OpenAIResponsesClient`, `OpenAIChatCompletionsClient`) and provider resolution utilities (`ProviderRegistry`, `resolve_provider`, `normalize_base_url`) from `agent/llm_client.py` and `core/providers.py` into a dedicated `tinycua_sdk/providers/` package.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1 (structural prerequisite for adding new providers like Anthropic)
- **Estimated Effort**: M

## Environment Pre-requisites

> No special environment setup is needed — this is a pure reorganization with no behavioral changes.

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **None** — no special tooling required

---

## Success Criteria — Import Sanity Tests (TDD First)

Define the import sanity tests (unit-level smoke tests) that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# File: tests/unit/test_import_sanity.py (NEW — smoke tests)
"""Reorganization smoke tests: new import paths resolve, old paths fail."""


def test_new_providers_package_importable():
    """FR-001: The providers package is importable."""
    import tinycua_sdk.providers  # noqa: F401


def test_openai_responses_client_new_path():
    """FR-002/AC-001: OpenAIResponsesClient importable from providers."""
    from tinycua_sdk.providers.open_ai import OpenAIResponsesClient
    assert OpenAIResponsesClient is not None


def test_openai_chat_completions_client_new_path():
    """OpenAIChatCompletionsClient importable from providers."""
    from tinycua_sdk.providers.open_ai import OpenAIChatCompletionsClient
    assert OpenAIChatCompletionsClient is not None


def test_provider_utilities_new_path():
    """FR-004/AC-004: resolve_provider, normalize_base_url from providers.providers."""
    from tinycua_sdk.providers.providers import resolve_provider, normalize_base_url
    assert callable(resolve_provider)
    assert callable(normalize_base_url)


def test_provider_registry_new_path():
    """FR-004: ProviderRegistry importable from providers.providers."""
    from tinycua_sdk.providers.providers import ProviderRegistry
    assert ProviderRegistry is not None


def test_convenience_namespace():
    """AC-004: Convenience re-exports via tinycua_sdk.providers."""
    from tinycua_sdk.providers import (
        DEFAULT_BASE_URL,
        OPENAI_COMPATIBLE,
        OpenAIResponsesClient,
        OpenAIChatCompletionsClient,
        resolve_provider,
        normalize_base_url,
    )
    assert callable(resolve_provider)


def test_llm_client_abc_still_in_agent():
    """AC-003: LLMClient ABC still resolves from agent.llm_client."""
    from tinycua_sdk.agent.llm_client import LLMClient
    assert LLMClient is not None


def test_old_core_providers_path_removed():
    """FR-005: Old core.providers module is deleted."""
    import importlib.util
    spec = importlib.util.find_spec("tinycua_sdk.core.providers")
    assert spec is None, "core.providers module should not exist — it was deleted"


def test_full_test_suite_passes():
    """AC-005: All existing tests pass after reorganization."""
    # Verified by running: uv run pytest tests/unit/
```

### Key Test Scenarios

- [x] **Scenario 1**: New import paths resolve — both `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` importable from `tinycua_sdk.providers.open_ai`
- [x] **Scenario 2**: Provider registry utilities importable from `tinycua_sdk.providers.providers`
- [x] **Scenario 3**: Convenience namespace `tinycua_sdk.providers` re-exports key symbols
- [x] **Scenario 4**: `LLMClient` ABC still resolves from `tinycua_sdk.agent.llm_client`
- [x] **Scenario 5**: Old `core/providers.py` module raises `ImportError` (deleted)
- [x] **Scenario 6**: Full existing test suite passes with only import-path changes

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua-sdk && uv run pytest tests/unit/`
- [ ] Negative import test: `from tinycua_sdk.core.providers import ...` raises `ImportError`

### Manual Verification

- [ ] Run: `uv run python -c "from tinycua_sdk.providers.open_ai import OpenAIResponsesClient; print('new path OK')"`
- [ ] Run: `uv run python -c "from tinycua_sdk.agent.llm_client import OpenAIResponsesClient" 2>&1 | grep -q ImportError && echo 'old path correctly removed'`
- [ ] Run: `uv run python -c "from tinycua_sdk.core.providers import resolve_provider" 2>&1 | grep -q ImportError && echo 'core.providers deleted'`

### Performance Considerations

- [ ] **N/A** — pure file reorganization, no runtime performance impact

## Proposed Changes

### `tinycua_sdk/providers/` Package (NEW)

#### [NEW] `tinycua_sdk/providers/__init__.py`

- **[Description]**: Package init with convenience re-exports of all public symbols from `providers.open_ai` and `providers.providers`
- **[Rationale]**: Provides ergonomic imports like `from tinycua_sdk.providers import OpenAIResponsesClient`
- **[Contents]**: Re-exports `OpenAIResponsesClient`, `OpenAIChatCompletionsClient`, `resolve_provider`, `normalize_base_url`, `DEFAULT_BASE_URL`, `OPENAI_COMPATIBLE`, `OPENAI_RESPONSES`, `OPENAI_CHAT_COMPLETIONS`, `ProviderRegistry`, `get_provider_registry`, `VALID_PROVIDERS`

#### [NEW] `tinycua_sdk/providers/providers.py`

- **[Description]**: Moved verbatim from `tinycua_sdk/core/providers.py` — contains `ProviderRegistry`, `resolve_provider`, `normalize_base_url`, `get_provider_registry`, constants, and `_register_defaults`
- **[Dependencies]**: Inside the new `providers/providers.py`, update deferred local imports inside factory functions (`_register_defaults()`) to import from `tinycua_sdk.providers.open_ai` instead of `tinycua_sdk.agent.llm_client`
- **[Rationale]**: Keeps provider resolution and registry alongside the provider implementations they create

#### [NEW] `tinycua_sdk/providers/open_ai.py`

- **[Description]**: Contains `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` (extracted from `agent/llm_client.py`) along with all supporting module-level utility functions, dataclasses, and constants:
  - `OpenAIResponsesClient` class + all its methods
  - `OpenAIChatCompletionsClient` class + all its methods
  - Utility functions: `_normalize_responses_event`, `_normalize_content_event`, `_normalize_reasoning_event`, `_normalize_tool_event`, `_normalize_lifecycle_event`, `_translate_messages`, `_translate_tools`, `_normalize_chat_chunk`, `_normalize_chunk_content`, `_normalize_chunk_tool_calls`, `_normalize_chunk_finalize`, `_normalize_chunk_usage_only`, `_normalize_non_streaming_response` (Responses and Chat variants), `_handle_provider_error` (both variants), `_translate_chat_messages`, `_translate_chat_tools`
  - Dataclasses: `ToolCallAccumulator`, `ChoiceAccumulator`, `_accumulator_to_chat_tool_calls`
  - Constants: `_SUPPORTED_FIELDS`, `_FIELD_MAP`, `_CHAT_SUPPORTED_FIELDS`
  - Imports updated from `tinycua_sdk.core.providers` → `tinycua_sdk.providers.providers`
  - `_yield_events` is NOT moved — it stays in `llm_client.py` and is imported from there
- **[Rationale]**: All provider-specific code lives in one place; the ABC stays in `agent/` to prevent circular dependencies

### `tinycua_sdk/agent/llm_client.py` (MODIFY)

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **[Description]**: Remove `OpenAIResponsesClient`, `OpenAIChatCompletionsClient` classes and all their supporting code. Keep only `LLMClient` ABC, `_yield_events`, `_build_payload` (legacy), and core utility imports.
- **[Removed classes/methods]**:
  - `OpenAIResponsesClient` class (all methods)
  - `OpenAIChatCompletionsClient` class (all methods)
  - `_normalize_responses_event` and all sub-normalizer functions
  - `_translate_messages`, `_translate_tools`
  - `_normalize_chat_chunk` and sub-functions
  - `_normalize_non_streaming_response` (both variants)
  - `_handle_provider_error` (both variants)
  - `_translate_chat_messages`, `_translate_chat_tools`
  - `_build_chat_payload`, `_capture_tool_calls`
  - `ToolCallAccumulator`, `ChoiceAccumulator`, `_accumulator_to_chat_tool_calls`
  - `_SUPPORTED_FIELDS`, `_FIELD_MAP`, `_CHAT_SUPPORTED_FIELDS`
  - `_build_request_kwargs` (Responses)
- **[Removed imports]**: `httpx`, `from openai import AsyncOpenAI`, `from tinycua_sdk.core.exceptions import ProviderApiError, ProviderAuthError`, `from tinycua_sdk.core.providers import normalize_base_url`, `from dataclasses import dataclass, field`
- **[Kept]**: `LLMClient` ABC, `_yield_events`, `_build_payload` (legacy), `__all__` updated to `["LLMClient"]`
- **[Breaking changes]**: Old import paths for client classes removed — consumers must import from `tinycua_sdk.providers.open_ai`

### `tinycua_sdk/core/providers.py` (DELETE)

#### [DELETE] `tinycua_sdk/core/providers.py`

- **[Description]**: Entire file is deleted — no re-export shim
- **[Rationale]**: All content moved to `tinycua_sdk/providers/providers.py`; no backward-compat debt as this is a pre-release SDK

### Import Updates (Source)

#### [MODIFY] `tinycua_sdk/agent/__init__.py`

- **[Description]**: Change import of `OpenAIChatCompletionsClient`, `OpenAIResponsesClient` from `tinycua_sdk.agent.llm_client` to `tinycua_sdk.providers.open_ai`
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tinycua_sdk/agent/executor.py`

- **[Description]**: Change import of `ProviderRegistry`, `get_provider_registry` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.providers`
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tinycua_sdk/agent/llm_model.py`

- **[Description]**: Change import of `resolve_provider` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.providers`
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tinycua_sdk/core/__init__.py`

- **[Description]**: Remove all imports from `tinycua_sdk.core.providers` (which is deleted). Keep only `tinycua_sdk.core.exceptions` imports.
- **[Rationale]**: No re-export shim; consumers must import from `tinycua_sdk.providers` instead

### Import Updates (Tests)

#### [MODIFY] `tests/unit/test_llm_client.py`

- **[Description]**: Change imports: `OpenAIResponsesClient` from `tinycua_sdk.agent.llm_client` → `tinycua_sdk.providers.open_ai`. `_normalize_responses_event` from `tinycua_sdk.agent.llm_client` → `tinycua_sdk.providers.open_ai`. `LLMClient`, `_build_payload` remain from `tinycua_sdk.agent.llm_client`.
- **[Rationale]**: Follows the new canonical import paths for moved symbols

#### [MODIFY] `tests/unit/test_providers.py`

- **[Description]**: Change imports from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.providers`
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tests/unit/test_provider_switching.py`

- **[Description]**: Change imports of `ProviderInfo`, `ProviderRegistry`, `get_provider_registry` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.providers`. `LLMClient` import remains from `tinycua_sdk.agent.llm_client`.
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tests/unit/test_provider_registry.py`

- **[Description]**: Change imports of `ProviderInfo`, `ProviderRegistry` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.providers`. `LLMClient` import remains from `tinycua_sdk.agent.llm_client`.
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tests/unit/test_openai_chat_client.py`

- **[Description]**: Change import of `OpenAIChatCompletionsClient` from `tinycua_sdk.agent.llm_client` to `tinycua_sdk.providers.open_ai`
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tests/unit/test_executor_integration.py`

- **[Description]**: Change imports of `ProviderInfo`, `ProviderRegistry` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.providers`. `LLMClient` import remains from `tinycua_sdk.agent.llm_client`.
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tests/unit/conftest.py`

- **[Description]**: Change all imports of `OpenAIResponsesClient` from `tinycua_sdk.agent.llm_client` to `tinycua_sdk.providers.open_ai`
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tests/integration/test_provider_switching.py`

- **[Description]**: Change imports of `ProviderInfo`, `ProviderRegistry`, `get_provider_registry` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.providers`. `LLMClient` import remains from `tinycua_sdk.agent.llm_client`.
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tests/integration/test_openai_chat_completions_provider.py`

- **[Description]**: Change imports of `OpenAIChatCompletionsClient`, `OpenAIResponsesClient` from `tinycua_sdk.agent.llm_client` to `tinycua_sdk.providers.open_ai`. Change import of `get_provider_registry` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.providers`.
- **[Rationale]**: Follows the new canonical import paths

#### [MODIFY] `tests/integration/test_language_model.py`

- **[Description]**: Change import of `resolve_provider` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.providers`
- **[Rationale]**: Follows the new canonical import paths

### `tinycua_sdk/core/__init__.py` (MODIFY)

#### [MODIFY] `tinycua_sdk/core/__init__.py`

- **[Description]**: Remove imports from `tinycua_sdk.core.providers`. Only `from tinycua_sdk.core.exceptions` remains.
- **[Rationale]**: No backward-compat shims for deleted module

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua_sdk/providers/` | **New** | New package with `__init__.py`, `providers.py`, `open_ai.py` |
| `tinycua_sdk/providers/providers.py` | **New** | Moved from `core/providers.py` (verbatim + import fix) |
| `tinycua_sdk/providers/open_ai.py` | **New** | Extracted from `agent/llm_client.py` (client classes + utilities) |
| `tinycua_sdk/agent/llm_client.py` | **Modify** | Removed client classes and provider utilities; keeps `LLMClient` ABC + shared utilities |
| `tinycua_sdk/core/providers.py` | **Delete** | Removed — content moved to `providers/providers.py` |
| `tinycua_sdk/core/__init__.py` | **Modify** | Removed provider re-exports |
| Various source/tests | **Modify** | Updated import paths |

## Data Model Changes

No new types or modified interfaces. Pure file reorganization — all classes, functions, and constants retain their exact interface.

## API Changes

### New Import Paths

| Symbol | Old Path | New Path |
|--------|----------|----------|
| `OpenAIResponsesClient` | `tinycua_sdk.agent.llm_client` | `tinycua_sdk.providers.open_ai` |
| `OpenAIChatCompletionsClient` | `tinycua_sdk.agent.llm_client` | `tinycua_sdk.providers.open_ai` |
| `resolve_provider` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `normalize_base_url` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `ProviderRegistry` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `get_provider_registry` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `OPENAI_COMPATIBLE` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `OPENAI_RESPONSES` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `OPENAI_CHAT_COMPLETIONS` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `DEFAULT_BASE_URL` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `OPENAI_BASE_URL` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `ProviderFactory` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `ProviderInfo` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `VALID_PROVIDERS` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `_PROVIDER_ALIASES` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `LLMClient` | `tinycua_sdk.agent.llm_client` | **Unchanged** |

### Convenience Namespace

`tinycua_sdk.providers` re-exports key symbols:
```python
from tinycua_sdk.providers import OpenAIResponsesClient, OpenAIChatCompletionsClient, resolve_provider
```

### Error Handling

| Error Case | Exception | Notes |
|------------|-----------|-------|
| Import from old `core.providers` | `ModuleNotFoundError` | File deleted — clear error on missing module |
| Import `OpenAIResponsesClient` from `agent.llm_client` | `ImportError` | Symbol removed from module |

## Dependencies

### External Dependencies

No new external dependencies. The `httpx` import was only used by the now-extracted client classes — it's removed from `agent/llm_client.py` but remains as an implicit dependency through the OpenAI SDK.

### Internal Dependencies

- [ ] Depends on completion of prior SDK stabilization (no active dependencies — all changes are in `tinycua-sdk` only)
- [ ] Blocks addition of future providers (e.g., Anthropic, Google Vertex)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missed import reference causes runtime `ImportError` | High | Full test suite run catches this; CI pipeline with coverage ensures all paths exercised |
| Circular import between `providers/open_ai.py` and `providers/providers.py` | High | Deferred local imports used in factory functions; `normalize_base_url` imported at top level but does not depend on `open_ai.py` — verified DAG with no cycle |
| Test file imports missed during update | Medium | Full test suite run (`uv run pytest tests/unit/`) catches any stale import paths |
| `core/__init__.py` consumers break | Low (pre-release) | No backward-compat shims per spec; breaking change expected for pre-1.0 SDK |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-19*
