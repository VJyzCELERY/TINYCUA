# Design Document: Reorganize Client Module — Extract Provider Implementations

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-19

---

## Overview

Restructure the SDK's provider-related code by extracting provider implementations and resolution utilities into a dedicated `tinycua_sdk/providers/` package. The `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` classes move from `agent/llm_client.py` to `providers/open_ai.py`. The `core/providers.py` module is split into focused sub-modules: `providers/constants.py` (constants), `providers/registry.py` (`ProviderRegistry`, `get_provider_registry`), and `providers/utility.py` (`resolve_provider`, `normalize_base_url`, `ProviderInfo`, `ProviderFactory`). The `LLMClient` ABC remains in `agent/llm_client.py`. Old files (`core/providers.py`) are deleted; old class locations (`agent/llm_client.py`) are cleaned up — no backward-compatible re-export shims are left behind.

**Affected subproject**: `tinycua-sdk` only.

---

## Architecture

### Current Layout

```
tinycua_sdk/
├── core/
│   ├── __init__.py        # Re-exports from core.providers (will be cleaned up)
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
│   ├── llm_model.py        # Imports resolve_provider from providers.utility
│   ├── executor.py         # Imports ProviderRegistry/get_provider_registry from providers.registry
│   └── ...
└── providers/              # ← NEW package
    ├── __init__.py         # Convenience re-exports from all sub-modules
    ├── constants.py        # ← MOVED FROM: core/providers.py (OPENAI_COMPATIBLE, DEFAULT_BASE_URL, ...)
    ├── registry.py         # ← MOVED FROM: core/providers.py (ProviderRegistry, get_provider_registry)
    ├── utility.py          # ← MOVED FROM: core/providers.py (resolve_provider, normalize_base_url, ...)
    └── open_ai.py          # ← MOVED FROM: agent/llm_client.py (OpenAIResponsesClient + OpenAIChatCompletionsClient)
```

### File Movement Summary

| Source | Destination | Action |
|--------|-------------|--------|
| `core/providers.py` (partial: constants) | `providers/constants.py` | Extract constants, then DELETE source |
| `core/providers.py` (partial: `ProviderRegistry`, `get_provider_registry`) | `providers/registry.py` | Extract registry, then DELETE source |
| `core/providers.py` (partial: `resolve_provider`, `normalize_base_url`, `ProviderInfo`, `ProviderFactory`) | `providers/utility.py` | Extract utilities, then DELETE source |
| `agent/llm_client.py` (partial: `OpenAIResponsesClient` + `OpenAIChatCompletionsClient`) | `providers/open_ai.py` | Extract both classes, then REMOVE from source |
| `agent/llm_client.py` | — | Keep `LLMClient` ABC only |

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/core/providers.py` | **Deleted** | Entire file removed |
| `tinycua_sdk/core/__init__.py` | **Modified** | Remove all imports from `tinycua_sdk.core.providers` — only `core.exceptions` imports remain |
| `tinycua_sdk/agent/llm_client.py` | **Modified** | Removes `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` classes and helpers; keeps `LLMClient` ABC; removes both from `__all__` |
| `tinycua_sdk/agent/__init__.py` | **Modified** | Changes `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` import source to `tinycua_sdk.providers.open_ai` |
| `tinycua_sdk/agent/executor.py` | **Modified** | Updates imports of `ProviderRegistry` and `get_provider_registry` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.registry` |
| `tinycua_sdk/agent/llm_model.py` | **Modified** | Updates import of `resolve_provider` from `tinycua_sdk.core.providers` to `tinycua_sdk.providers.utility` |
| `tinycua_sdk/providers/__init__.py` | **New** | Package init with convenience re-exports from all sub-modules |
| `tinycua_sdk/providers/constants.py` | **New** | Constants moved from `core/providers.py` |
| `tinycua_sdk/providers/registry.py` | **New** | `ProviderRegistry`, `get_provider_registry` moved from `core/providers.py` |
| `tinycua_sdk/providers/utility.py` | **New** | `resolve_provider`, `normalize_base_url`, `ProviderInfo`, `ProviderFactory` moved from `core/providers.py` |
| `tinycua_sdk/providers/open_ai.py` | **New** | Contains `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` (extracted from `agent/llm_client.py`) |
| `tests/unit/test_providers.py` | **Modified** | Updates import source to `providers.utility` / `providers.registry` / `providers.constants` |
| `tests/unit/test_llm_client.py` | **Modified** | Updates import source for `OpenAIResponsesClient` |
| `tests/unit/conftest.py` | **Modified** | Updates mock import reference (if any) |
| `tests/integration/conftest.py` | None | No references to `core.providers` — local `_build_auth_headers()` is self-contained |
| `tests/unit/test_provider_switching.py` | **Modified** | Update imports from `core.providers` to `providers.registry` / `providers.utility` / `providers.constants` |
| `tests/unit/test_provider_registry.py` | **Modified** | Update imports from `core.providers` to `providers.registry` |
| `tests/unit/test_openai_chat_client.py` | **Modified** | Update import of `OpenAIChatCompletionsClient` from `agent.llm_client` to `providers.open_ai` |
| `tests/unit/test_executor_integration.py` | **Modified** | Update imports from `core.providers` to `providers.registry` / `providers.utility` |
| `tests/integration/test_provider_switching.py` | **Modified** | Update imports from `core.providers` to `providers.registry` / `providers.utility` |
| `tests/integration/test_openai_chat_completions_provider.py` | **Modified** | Update imports of both client classes from `agent.llm_client` to `providers.open_ai`; import `get_provider_registry` from `core.providers` to `providers.registry` |
| `tests/integration/test_language_model.py` | **Modified** | Update import of `resolve_provider` from `core.providers` to `providers.utility` |

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
| `OPENAI_COMPATIBLE` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.constants` |
| `OPENAI_RESPONSES` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.constants` |
| `OPENAI_CHAT_COMPLETIONS` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.constants` |
| `DEFAULT_BASE_URL` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.constants` |
| `OPENAI_BASE_URL` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.constants` |
| `_PROVIDER_ALIASES` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.constants` |
| `ProviderRegistry` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.registry` |
| `get_provider_registry` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.registry` |
| `resolve_provider` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.utility` |
| `normalize_base_url` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.utility` |
| `ProviderInfo` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.utility` |
| `ProviderFactory` | `tinycua_sdk.core.providers` | `tinycua_sdk.providers.utility` |
| `LLMClient` | `tinycua_sdk.agent.llm_client` | **Unchanged** |

### Convenience Namespace

`tinycua_sdk.providers` (via `__init__.py`) re-exports key symbols from all sub-modules for ergonomic access:

```python
from tinycua_sdk.providers import (
    OpenAIResponsesClient, OpenAIChatCompletionsClient,
    resolve_provider, normalize_base_url,
    ProviderRegistry, get_provider_registry,
    DEFAULT_BASE_URL, OPENAI_COMPATIBLE,
)
```

### Error Handling

| Error Case | Exception | Notes |
|------------|-----------|-------|
| Import from old `core.providers` | `ModuleNotFoundError` | File deleted — clear error on missing module |
| Import `OpenAIResponsesClient` or `OpenAIChatCompletionsClient` from `agent.llm_client` | `ImportError` | Symbols removed from module |

---

## Implementation Phases

### Phase 1 — Create `providers/` package with moved code

- [ ] Create `tinycua_sdk/providers/__init__.py` with convenience re-exports from all sub-modules
- [ ] Create `tinycua_sdk/providers/constants.py` — extract constants from `core/providers.py`:
  - `OPENAI_COMPATIBLE`, `OPENAI_RESPONSES`, `OPENAI_CHAT_COMPLETIONS`, `DEFAULT_BASE_URL`, `OPENAI_BASE_URL`, `_PROVIDER_ALIASES`
- [ ] Create `tinycua_sdk/providers/registry.py` — extract `ProviderRegistry` and `get_provider_registry` from `core/providers.py`
- [ ] Create `tinycua_sdk/providers/utility.py` — extract `resolve_provider`, `normalize_base_url`, `ProviderInfo`, `ProviderFactory` from `core/providers.py`. Update any internal import paths (deferred imports from `tinycua_sdk.agent.llm_client` → `tinycua_sdk.providers.open_ai`)
- [ ] Create `tinycua_sdk/providers/open_ai.py` — copy `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` and their helper methods from `agent/llm_client.py`. Update imports:
  - `normalize_base_url` → from `tinycua_sdk.providers.utility`
  - `LanguageModel` → from `tinycua_sdk.agent.llm_model`
- [ ] Verify new files are importable: `uv run python -c "from tinycua_sdk.providers import OpenAIResponsesClient, OpenAIChatCompletionsClient, resolve_provider, ProviderRegistry, DEFAULT_BASE_URL"`

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
- [ ] `agent/executor.py`: Change imports to `from tinycua_sdk.providers.registry import ProviderRegistry, get_provider_registry`
- [ ] `agent/llm_model.py`: Change import to `from tinycua_sdk.providers.utility import resolve_provider`
- [ ] `tests/unit/test_llm_client.py`: Change imports for `OpenAIResponsesClient`, `_normalize_responses_event` to `from tinycua_sdk.providers.open_ai`; `LLMClient` remains from `tinycua_sdk.agent.llm_client`; `_build_payload` from `tinycua_sdk.providers.open_ai`
- [ ] `tests/unit/test_providers.py`: Change imports to `from tinycua_sdk.providers.utility import ...` / `from tinycua_sdk.providers.registry import ...` / `from tinycua_sdk.providers.constants import ...`
- [ ] `tests/unit/conftest.py`: Update any reference to `OpenAIResponsesClient` to use new path
- [ ] `tests/integration/conftest.py`: Update any reference

### Phase 5 — Full verification

- [ ] Run `uv run pytest tests/` — all tests pass
- [ ] Run smoke test: `uv run python -c "from tinycua_sdk.providers.open_ai import OpenAIResponsesClient, OpenAIChatCompletionsClient; from tinycua_sdk.providers.utility import resolve_provider; from tinycua_sdk.providers.registry import ProviderRegistry; from tinycua_sdk.providers.constants import DEFAULT_BASE_URL; print('new paths OK')"`

---

## File Change Details

### `tinycua_sdk/providers/__init__.py` (new)

```python
"""Provider-specific LLM client implementations."""
from tinycua_sdk.providers.constants import (
    DEFAULT_BASE_URL,
    OPENAI_BASE_URL,
    OPENAI_CHAT_COMPLETIONS,
    OPENAI_COMPATIBLE,
    OPENAI_RESPONSES,
)
from tinycua_sdk.providers.registry import ProviderRegistry, get_provider_registry
from tinycua_sdk.providers.utility import (
    normalize_base_url,
    ProviderFactory,
    ProviderInfo,
    resolve_provider,
)
from tinycua_sdk.providers.open_ai import OpenAIResponsesClient, OpenAIChatCompletionsClient

__all__ = [
    "DEFAULT_BASE_URL",
    "OPENAI_BASE_URL",
    "OPENAI_CHAT_COMPLETIONS",
    "OPENAI_COMPATIBLE",
    "OPENAI_RESPONSES",
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

### `tinycua_sdk/providers/constants.py` (new — extracted from `core/providers.py`)

Straight copy of constants. No internal SDK imports — only stdlib.

Constants:
- `OPENAI_COMPATIBLE`, `OPENAI_RESPONSES`, `OPENAI_CHAT_COMPLETIONS`
- `DEFAULT_BASE_URL`, `OPENAI_BASE_URL`
- `_PROVIDER_ALIASES` (private — NOT in `__all__`)

### `tinycua_sdk/providers/registry.py` (new — extracted from `core/providers.py`)

Contains `ProviderRegistry` class and `get_provider_registry()` function. Has internal dependencies:
- `tinycua_sdk.core.exceptions.ProviderConfigurationError` → unchanged (core package is not moved)
- `tinycua_sdk.providers.constants.OPENAI_COMPATIBLE` → **update from** `core.providers` **to** `providers.constants`
- `tinycua_sdk.providers.utility.normalize_base_url` → **update from** `core.providers` **to** `providers.utility`

### `tinycua_sdk/providers/utility.py` (new — extracted from `core/providers.py`)

Contains `resolve_provider()`, `normalize_base_url()`, `ProviderInfo`, `ProviderFactory`. Has internal dependencies:
- `tinycua_sdk.core.exceptions.ProviderNotSupportedError` → unchanged (core package is not moved)
- `tinycua_sdk.agent.llm_client.LLMClient` (TYPE_CHECKING only) → unchanged (LLMClient stays in agent)
- `tinycua_sdk.agent.llm_model.LanguageModel` (TYPE_CHECKING only) → unchanged (LanguageModel stays in agent)
- `tinycua_sdk.agent.llm_client.OpenAIResponsesClient` (deferred in `_openai_responses_factory`) → **update to** `tinycua_sdk.providers.open_ai`
- `tinycua_sdk.agent.llm_client.OpenAIChatCompletionsClient` (deferred in `_openai_chat_completions_factory`) → **update to** `tinycua_sdk.providers.open_ai`

Since `utility.py` depends on `providers/open_ai.py` (via deferred factory imports), these files must be created together in Phase 1 before imports resolve.

### `tinycua_sdk/providers/open_ai.py` (new — extracted from `agent/llm_client.py`)

Contains:
- `OpenAIResponsesClient(LLMClient)` and `OpenAIChatCompletionsClient(LLMClient)` classes
- All helper methods, dataclasses, and constants for both classes
- Imports:
  - `from tinycua_sdk.providers.utility import normalize_base_url`
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

2. **Decision**: Split `core/providers.py` into three focused sub-modules: `providers/constants.py`, `providers/registry.py`, `providers/utility.py`
   - **Reason**: Avoids the awkward `tinycua_sdk.providers.providers` import path. Each sub-module has a clear, single responsibility: constants are configuration values, the registry manages provider lifecycle, and utility functions provide resolution and normalization. This follows the principle of focused modules and makes the package more navigable.
   - **Alternatives Considered**: Single `providers/providers.py` — rejected because the duplicate module name (`providers.providers`) is confusing and the file would bundle unrelated concerns (constants, registry, utilities) into one module.

3. **Decision**: Keep `LLMClient` ABC in `agent/llm_client.py`
   - **Reason**: The ABC is tightly coupled to the agent loop system (consumed by `BaseLoop` and `Agent.run()`). The spec's scope is to extract *provider implementations*, not the interface. Moving the ABC would create a circular dependency risk (`providers` importing from `agent` for `LLMClient`, and `agent` importing from `providers` for concrete clients).
   - **Alternatives Considered**: Move ABC to `providers/base.py` — rejected because `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` inherit from `LLMClient`, creating `providers` → `agent` → `providers` if the ABC moves to `providers` and `agent/loop.py` still imports from `agent/llm_client.py`.

4. **Decision**: Move `_build_payload` to `providers/open_ai.py` alongside its dependencies
   - **Reason**: `_build_payload` directly calls `_translate_messages`, `_translate_tools`, `_SUPPORTED_FIELDS`, and `_FIELD_MAP` — all of which move to `providers/open_ai.py`. Keeping `_build_payload` in `agent/llm_client.py` would create a NameError at runtime since those symbols would be undefined. Moving it to `providers/open_ai.py` is the only consistent approach. `_build_payload` has zero production callers in `agent/llm_client.py` (only test code imports it), so there is no dependency edge concern.
   - **Alternatives Considered**: Keep in `agent/llm_client.py` with its dependencies — rejected because that would defeat the purpose of extracting provider-specific code into the `providers/` package.

5. **Decision**: `agent/llm_client.py` removes `httpx` import entirely
   - **Reason**: The `httpx` import was only used by `OpenAIResponsesClient` and `OpenAIChatCompletionsClient`. The `LLMClient` ABC is pure abstract (uses only `abc`, `collections.abc`, `typing`). Removing it cleans up the module's dependency footprint.
   - **Verification**: Confirm `grep -rn "httpx" tinycua_sdk/agent/` returns no results after removal.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Missed import reference causes runtime `ImportError` | Medium | High | Full test suite run in Phase 5 catches this; moved symbols will not be found at the old location, so any stale import causes an immediate `ImportError` at load time |
| Circular import between `providers/open_ai.py` and `agent/llm_model.py` | Low | High | `open_ai.py` imports `LanguageModel` from `agent/llm_model.py`; `llm_model.py` imports `resolve_provider` from `providers/utility.py`. This is a DAG with no cycle (`providers` → `agent` is not reciprocated). Verify with `uv run python -c "import tinycua_sdk"` |
| `agent/llm_client.py` still needs `httpx` for some future use | Low | Low | Easily re-added when needed — not a reason to keep unused imports |
| `core/providers.py` deletion breaks a downstream consumer not in this repo | Low | Low (pre-release SDK) | No public consumers — this is a pre-1.0 SDK; breaking changes are expected |

---

## References

- Spec: `./spec.md`
- Current `core/providers.py`: `src/tinycua-sdk/tinycua_sdk/core/providers.py`
- Current `agent/llm_client.py`: `src/tinycua-sdk/tinycua_sdk/agent/llm_client.py`
- Current tests: `tests/unit/test_providers.py`, `tests/unit/test_llm_client.py`
- Integration tests: `tests/integration/conftest.py`
