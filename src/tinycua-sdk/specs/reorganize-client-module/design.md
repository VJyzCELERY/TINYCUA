# Design Document: Reorganize Client Module — Extract Provider Implementations

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-19

---

## Overview

Restructure the SDK's provider-related code by extracting provider implementations and resolution utilities into a dedicated `tinycua_sdk/providers/` package. The `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` classes move from `agent/llm_client.py` to `providers/open_ai.py`, and provider resolution utilities move from `core/providers.py` to `providers/providers.py`. The `LLMClient` ABC remains in `agent/llm_client.py`. Old files (`core/providers.py`) are deleted; old class locations (`agent/llm_client.py`) are cleaned up — no backward-compatible re-export shims are left behind.

**Affected subproject**: `tinycua-sdk` only.

---

## Architecture

### Current Layout

```
tinycua_sdk/
├── core/
│   ├── __init__.py        # Core SDK abstractions (currently empty)
│   ├── exceptions.py
│   └── providers.py       # resolve_provider(), normalize_base_url(), constants
├── agent/
│   ├── __init__.py         # Re-exports LLMClient + OpenAIResponsesClient + OpenAIChatCompletionsClient
│   ├── llm_client.py       # LLMClient ABC + OpenAIResponsesClient + OpenAIChatCompletionsClient
│   ├── llm_model.py        # Imports resolve_provider from core.providers
│   ├── executor.py         # Imports both client classes from agent.llm_client
│   └── ...
└── ...
```

### Proposed Layout

```
tinycua_sdk/
├── core/
│   ├── __init__.py         # Modified — remove core.providers imports
│   ├── exceptions.py       # Unchanged
│   └── providers.py        # ← DELETED
├── agent/
│   ├── __init__.py         # Re-exports LLMClient; re-exports both client classes via providers path
│   ├── llm_client.py       # ← ONLY: LLMClient ABC (no more client classes)
│   ├── llm_model.py        # Imports resolve_provider from providers.providers
│   ├── executor.py         # Imports both client classes from providers.open_ai
│   └── ...
└── providers/              # ← NEW package
    ├── __init__.py         # Convenience re-exports
    ├── providers.py        # ← MOVED FROM: core/providers.py (resolve_provider, normalize_base_url, constants)
    └── open_ai.py          # ← MOVED FROM: agent/llm_client.py (OpenAIResponsesClient + OpenAIChatCompletionsClient)
```

### File Movement Summary

| Source | Destination | Action |
|--------|-------------|--------|
| `core/providers.py` | `providers/providers.py` | Move contents, then DELETE source |
| `agent/llm_client.py` (partial: `OpenAIResponsesClient` + `OpenAIChatCompletionsClient`) | `providers/open_ai.py` | Extract both classes, then REMOVE from source |
| `agent/llm_client.py` | — | Keep `LLMClient` ABC only |

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/core/providers.py` | **Deleted** | Entire file removed |
| `tinycua_sdk/core/__init__.py` | **Modified** | Remove all imports from `tinycua_sdk.core.providers` — only `core.exceptions` imports remain |
| `tinycua_sdk/agent/llm_client.py` | **Modified** | Removes `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` classes and helpers; keeps `LLMClient` ABC; removes both from `__all__` |
| `tinycua_sdk/agent/__init__.py` | **Modified** | Changes `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` import source to `tinycua_sdk.providers.open_ai` |
| `tinycua_sdk/agent/executor.py` | **Modified** | Updates imports of `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` |
| `tinycua_sdk/agent/llm_model.py` | **Modified** | Updates import of `resolve_provider` |
| `tinycua_sdk/providers/__init__.py` | **New** | Package init with convenience re-exports |
| `tinycua_sdk/providers/providers.py` | **New** | Moved from `core/providers.py` |
| `tinycua_sdk/providers/open_ai.py` | **New** | Contains `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` (extracted from `agent/llm_client.py`) |
| `tests/unit/test_providers.py` | **Modified** | Updates import source |
| `tests/unit/test_llm_client.py` | **Modified** | Updates import source for `OpenAIResponsesClient` |
| `tests/unit/conftest.py` | **Modified** | Updates mock import reference (if any) |
| `tests/integration/conftest.py` | None | No references to `core.providers` — local `_build_auth_headers()` is self-contained |
| `tests/unit/test_provider_switching.py` | **Modified** | Update imports from `core.providers` to `providers.providers` |
| `tests/unit/test_provider_registry.py` | **Modified** | Update imports from `core.providers` to `providers.providers` |
| `tests/unit/test_openai_chat_client.py` | **Modified** | Update import of `OpenAIChatCompletionsClient` from `agent.llm_client` to `providers.open_ai` |
| `tests/unit/test_executor_integration.py` | **Modified** | Update imports from `core.providers` to `providers.providers` |
| `tests/integration/test_provider_switching.py` | **Modified** | Update imports from `core.providers` to `providers.providers` |
| `tests/integration/test_openai_chat_completions_provider.py` | **Modified** | Update imports of both client classes from `agent.llm_client` to `providers.open_ai`; import `get_provider_registry` from `core.providers` to `providers.providers` |
| `tests/integration/test_language_model.py` | **Modified** | Update import of `resolve_provider` from `core.providers` to `providers.providers` |

---

## Data Model

No new entities or schema changes. This is a pure file reorganization — all classes, functions, and constants retain their exact interface.

---

## API / Interface Contracts

### New / Modified Import Paths

| Symbol | Old Path | New Path |
|--------|----------|----------|
| `OpenAIResponsesClient` | `tinycua_sdk.agent.llm_client` | `tinycua_sdk.providers.open_ai` |
| `OpenAIChatCompletionsClient` | `tinycua_sdk.agent.llm_client` | `tinycua_sdk.providers.open_ai` |
| `resolve_provider` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `normalize_base_url` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `OPENAI_COMPATIBLE` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `DEFAULT_BASE_URL` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `OPENAI_RESPONSES` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `OPENAI_CHAT_COMPLETIONS` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `ProviderRegistry` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `get_provider_registry` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `ProviderInfo` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `ProviderFactory` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `OPENAI_BASE_URL` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `_PROVIDER_ALIASES` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.providers` |
| `LLMClient` | `tinycua_sdk.agent.llm_client` | **Unchanged** |

### Convenience Namespace

`tinycua_sdk.providers` (via `__init__.py`) re-exports key symbols for ergonomic access:

```python
from tinycua_sdk.providers import OpenAIResponsesClient, OpenAIChatCompletionsClient, resolve_provider
```

### Error Handling

| Error Case | Exception | Notes |
|------------|-----------|-------|
| Import from old `core.providers` | `ModuleNotFoundError` | File deleted — clear error on missing module |
| Import `OpenAIResponsesClient` or `OpenAIChatCompletionsClient` from `agent.llm_client` | `ImportError` | Symbols removed from module |

---

## Implementation Phases

### Phase 1 — Create `providers/` package with moved code

- [ ] Create `tinycua_sdk/providers/__init__.py` with convenience re-exports
- [ ] Create `tinycua_sdk/providers/providers.py` — copy `core/providers.py` content verbatim (no behavioral changes). Update any internal import paths if needed.
- [ ] Create `tinycua_sdk/providers/open_ai.py` — copy `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` and their helper methods from `agent/llm_client.py`. Update imports:
  - `normalize_base_url` → from `tinycua_sdk.providers.providers`
  - `LanguageModel` → from `tinycua_sdk.agent.llm_model`
- [ ] Verify new files are importable: `uv run python -c "from tinycua_sdk.providers import OpenAIResponsesClient, OpenAIChatCompletionsClient, resolve_provider"`

### Phase 2 — Clean up `agent/llm_client.py`

- [ ] Remove `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` classes and all their helper methods
- [ ] Remove `httpx` import (verify it's not used by `LLMClient` ABC — it is not)
- [ ] Remove `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` from `__all__` — only `LLMClient` remains
- [ ] Run `uv run pytest tests/unit/test_llm_client.py` — tests pass (they now import `OpenAIResponsesClient` from the new location)

### Phase 3 — Delete `core/providers.py`

- [ ] Delete `tinycua_sdk/core/providers.py`
- [ ] Verify `core/__init__.py` does not reference it
- [ ] Run `uv run pytest tests/unit/test_providers.py` — tests pass (they now import from the new location)

### Phase 4 — Update all internal imports

- [ ] `agent/__init__.py`: Change imports to `from tinycua_sdk.providers.open_ai import OpenAIResponsesClient, OpenAIChatCompletionsClient`
- [ ] `agent/executor.py`: Change imports to `from tinycua_sdk.providers.open_ai import OpenAIResponsesClient, OpenAIChatCompletionsClient`
- [ ] `agent/llm_model.py`: Change import to `from tinycua_sdk.providers.providers import resolve_provider`
- [ ] `tests/unit/test_llm_client.py`: Change imports for `OpenAIResponsesClient`, `_normalize_responses_event` to `from tinycua_sdk.providers.open_ai`; `LLMClient`, `_build_payload` remain from `tinycua_sdk.agent.llm_client`
- [ ] `tests/unit/test_providers.py`: Change import to `from tinycua_sdk.providers.providers import ...`
- [ ] `tests/unit/conftest.py`: Update any reference to `OpenAIResponsesClient` to use new path
- [ ] `tests/integration/conftest.py`: Update any reference

### Phase 5 — Full verification

- [ ] Run `uv run pytest tests/` — all tests pass
- [ ] Run smoke test: `uv run python -c "from tinycua_sdk.providers.open_ai import OpenAIResponsesClient, OpenAIChatCompletionsClient; print('new paths OK')"`
- [ ] Run negative smoke test: `uv run python -c "from tinycua_sdk.agent.llm_client import OpenAIResponsesClient" 2>&1 | grep -q ImportError && echo 'old path correctly removed'`

---

## File Change Details

### `tinycua_sdk/providers/__init__.py` (new)

```python
"""Provider-specific LLM client implementations."""
from tinycua_sdk.providers.providers import (
    DEFAULT_BASE_URL,
    OPENAI_BASE_URL,
    OPENAI_CHAT_COMPLETIONS,
    OPENAI_COMPATIBLE,
    OPENAI_RESPONSES,
    _PROVIDER_ALIASES,
    get_provider_registry,
    normalize_base_url,
    ProviderFactory,
    ProviderInfo,
    ProviderRegistry,
    resolve_provider,
)
from tinycua_sdk.providers.open_ai import OpenAIResponsesClient, OpenAIChatCompletionsClient

__all__ = [
    "DEFAULT_BASE_URL",
    "OPENAI_BASE_URL",
    "OPENAI_CHAT_COMPLETIONS",
    "OPENAI_COMPATIBLE",
    "OPENAI_RESPONSES",
    "_PROVIDER_ALIASES",
    "OpenAIResponsesClient",
    "OpenAIChatCompletionsClient",
    "ProviderFactory",
    "ProviderInfo",
    "ProviderRegistry",
    "get_provider_registry",
    "normalize_base_url",
    "resolve_provider",
]
```

### `tinycua_sdk/providers/providers.py` (new — verbatim from `core/providers.py`)

Identical content to the current `core/providers.py`. This module has no internal dependency on `tinycua_sdk` packages (all imports are stdlib), so a straight copy is sufficient:

- `resolve_provider()`
- `normalize_base_url()`
- Constants: `OPENAI_COMPATIBLE`, `DEFAULT_BASE_URL`, `_PROVIDER_ALIASES`
- `__all__`

### `tinycua_sdk/providers/open_ai.py` (new — extracted from `agent/llm_client.py`)

Contains:
- `OpenAIResponsesClient(LLMClient)` and `OpenAIChatCompletionsClient(LLMClient)` classes
- All helper methods, dataclasses, and constants for both classes
- Imports:
  - `from tinycua_sdk.providers.providers import normalize_base_url`
  - `from tinycua_sdk.agent.llm_model import LanguageModel`
  - `from tinycua_sdk.agent.llm_client import LLMClient`
  - `httpx`, `json`, `ABC`, `AsyncIterator`, `Any` (stdlib/third-party)
- `__all__ = ["OpenAIResponsesClient", "OpenAIChatCompletionsClient"]`

### `tinycua_sdk/agent/llm_client.py` (modified)

Before:
```python
"""LLM client ABC and OpenAI-compatible implementation."""
...
from tinycua_sdk.core.providers import normalize_base_url
...
class LLMClient(ABC): ...
class OpenAIResponsesClient(LLMClient): ...   # ← REMOVE
class OpenAIChatCompletionsClient(LLMClient): ...  # ← REMOVE
...

__all__ = ["LLMClient", "OpenAIResponsesClient", "OpenAIChatCompletionsClient"]
```

After:
```python
"""LLM client ABC."""
...
class LLMClient(ABC): ...
...

__all__ = ["LLMClient"]
```

### `tinycua_sdk/core/providers.py` (deleted)

Removed entirely. No replacement.

---

## Technical Decisions

1. **Decision**: Delete `core/providers.py` entirely rather than leaving a re-export shim
   - **Reason**: No backward-compat debt. The SDK is pre-release, so all internal consumers are updated in a single atomic change set. Keeping shims would require ongoing maintenance with no benefit.
   - **Alternatives Considered**: Re-export shim — rejected because it leaves dead import paths that can silently rot.

2. **Decision**: Name the provider resolution file `providers/providers.py` (duplicate name)
   - **Reason**: This keeps the import path `tinycua_sdk.providers.providers` which is self-documenting ("import providers from providers"). Alternatives like `providers/registry.py` or `providers/utils.py` were considered but `providers.py` is the most discoverable.
   - **Alternatives Considered**: `providers/registry.py` — rejected because the module is not a registry; it contains resolution utilities and constants.

3. **Decision**: Keep `LLMClient` ABC in `agent/llm_client.py`
   - **Reason**: The ABC is tightly coupled to the agent loop system (consumed by `BaseLoop` and `Agent.run()`). The spec's scope is to extract *provider implementations*, not the interface. Moving the ABC would create a circular dependency risk (`providers` importing from `agent` for `LLMClient`, and `agent` importing from `providers` for concrete clients).
   - **Alternatives Considered**: Move ABC to `providers/base.py` — rejected because `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` inherit from `LLMClient`, creating `providers` → `agent` → `providers` if the ABC moves to `providers` and `agent/loop.py` still imports from `agent/llm_client.py`.

4. **Decision**: Keep `_build_payload` helper in `agent/llm_client.py` (not moved to `providers/`)
   - **Reason**: `_build_payload` is a general-purpose OpenAI API payload builder that is also consumed by `LLMClient`-related utilities still in `agent/llm_client.py`. Moving it to `providers/open_ai.py` would require those remaining utilities to import from `providers/`, creating an unnecessary dependency edge in the opposite direction. Since `_build_payload` is small (~20 lines) and its only dependency is `typing`, keeping it in place minimizes churn while preserving clean module boundaries.
   - **Alternatives Considered**: Move to `providers/open_ai.py` — rejected because remaining `agent/llm_client.py` utilities would then depend on `providers/`.

5. **Decision**: `agent/llm_client.py` removes `httpx` import entirely
   - **Reason**: The `httpx` import was only used by `OpenAIResponsesClient` and `OpenAIChatCompletionsClient`. The `LLMClient` ABC is pure abstract (uses only `abc`, `collections.abc`, `typing`). Removing it cleans up the module's dependency footprint.
   - **Verification**: Confirm `grep -rn "httpx" tinycua_sdk/agent/` returns no results after removal.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Missed import reference causes runtime `ImportError` | Medium | High | Full test suite run in Phase 5 catches this; negative smoke test explicitly verifies old paths fail |
| Circular import between `providers/open_ai.py` and `agent/llm_model.py` | Low | High | `open_ai.py` imports `LanguageModel` from `agent/llm_model.py`; `llm_model.py` imports `resolve_provider` from `providers/providers.py`. This is a DAG with no cycle (`providers` → `agent` is not reciprocated). Verify with `uv run python -c "import tinycua_sdk"` |
| `agent/llm_client.py` still needs `httpx` for some future use | Low | Low | Easily re-added when needed — not a reason to keep unused imports |
| `core/providers.py` deletion breaks a downstream consumer not in this repo | Low | Low (pre-release SDK) | No public consumers — this is a pre-1.0 SDK; breaking changes are expected |

---

## References

- Spec: `./spec.md`
- Current `core/providers.py`: `src/tinycua-sdk/tinycua_sdk/core/providers.py`
- Current `agent/llm_client.py`: `src/tinycua-sdk/tinycua_sdk/agent/llm_client.py`
- Current tests: `tests/unit/test_providers.py`, `tests/unit/test_llm_client.py`
- Integration tests: `tests/integration/conftest.py`
