# Feature Specification: Reorganize Client Module — Extract Provider Implementations

**Status**: Draft
**Created**: 2026-05-19
**Last Updated**: 2026-05-19
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Provide a clear module boundary for provider-specific LLM implementations by extracting them from `agent/` and `core/` into a dedicated `providers/` package, so that:

- Adding a new provider (e.g., Anthropic, Google Vertex) means adding a file to `providers/` rather than modifying `agent/llm_client.py` or `core/providers.py`
- The `LLMClient` ABC remains in `agent/llm_client.py` as the single import point for consumers that only need the abstract interface
- Provider resolution utilities (aliases, URL normalization) live alongside provider implementations
- Import paths are intuitive: `tinycua_sdk.providers.open_ai.OpenAIResponsesClient` and `tinycua_sdk.providers.open_ai.OpenAIChatCompletionsClient` vs the current `tinycua_sdk.agent.llm_client.OpenAIResponsesClient` and `tinycua_sdk.agent.llm_client.OpenAIChatCompletionsClient`

### Gaps

1. **Mixed concerns in `agent/llm_client.py`**: The file contains both the `LLMClient` ABC and the `OpenAIResponsesClient` + `OpenAIChatCompletionsClient` concrete implementations (~250 lines total for both concrete classes vs ~30 for the ABC). A consumer that only needs the abstract interface gets the concrete implementations transitively.

2. **`core/providers.py` is an orphan**: Provider resolution utilities (`resolve_provider`, `normalize_base_url`) live in `core/` with no sibling modules — `core/` contains only `exceptions.py` and `providers.py`. This makes the `core` package feel like a catch-all rather than a cohesive namespace.

3. **No discovered extension pattern**: There is no convention dictating where new provider clients should be placed. Adding an Anthropic provider would likely result in either more bloat in `agent/llm_client.py` or another orphan module.

4. **Exports from `agent/__init__.py` include provider-specific classes**: `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` are re-exported from `tinycua_sdk.agent`, coupling the agent package to specific provider implementations.

### Non-Goals

- Changing any runtime behavior (identical code, only new file locations)
- Modifying the `LLMClient` ABC interface in any way
- Adding new provider implementations (Anthropic, etc.) — this is purely a reorganization
- Changing the `Agent`, `BaseLoop`, or `AgentExecutor` public API
- Changing external dependency configuration (pyproject.toml stays the same)
- Maintaining backward-compatible import shims — old import paths are removed; all consumers are updated in one pass

### Constraints

- All existing tests must pass without behavioral modifications (only import paths change)
- No new runtime dependencies
- The `core/` package must remain valid after `providers.py` is removed
- Every file that imports from the old locations must be updated in the same change set — no gradual migration

---

## User Scenarios & Testing

### Primary Scenario: Finding the OpenAI Client

**As a** developer integrating an OpenAI-compatible LLM,
**I want to** import `OpenAIResponsesClient` or `OpenAIChatCompletionsClient` from an intuitive location under `tinycua_sdk.providers`,
**So that** I don't need to dig through `agent/llm_client.py` to find provider-specific code.

**Given** the SDK is installed,
**When** I write `from tinycua_sdk.providers.open_ai import OpenAIResponsesClient` or `from tinycua_sdk.providers.open_ai import OpenAIChatCompletionsClient`,
**Then** the import resolves correctly and the classes behave identically to before.

### Acceptance Scenarios

**AC-001: Client classes importable from `providers`** — `from tinycua_sdk.providers.open_ai import OpenAIResponsesClient` and `from tinycua_sdk.providers.open_ai import OpenAIChatCompletionsClient` both resolve and instantiate successfully.

**AC-002: Old import paths removed** — `from tinycua_sdk.agent.llm_client import OpenAIResponsesClient` and `from tinycua_sdk.agent.llm_client import OpenAIChatCompletionsClient` each raise `ImportError` (the concrete classes have moved). `LLMClient` ABC still resolves from the same path.

**AC-003: `LLMClient` ABC still in `agent/llm_client.py`** — `from tinycua_sdk.agent.llm_client import LLMClient` resolves to the abstract base class, which is unchanged.

**AC-004: Provider resolution utilities in `providers`** — `resolve_provider()` and `normalize_base_url()` are importable from `tinycua_sdk.providers.providers` and from the convenience `tinycua_sdk.providers` namespace.

**AC-005: All existing tests pass** — The full test suite (`uv run pytest`) passes with only import-path changes.

### Edge Cases

- What if `core/` becomes empty after removing `providers.py`? The `core/` package retains `exceptions.py` — no empty namespace.
- What about transitive imports via `agent/__init__.py`? The `agent` package re-exports `OpenAIResponsesClient` and `OpenAIChatCompletionsClient`; these are replaced with imports from the new `providers` location.
- What if a test file imports from the old path and misses the update? The test suite will fail with `ImportError` — no silent breakage.

---

## Requirements

### Functional Requirements

**Module structure:**

- **FR-001**: A new `tinycua_sdk/providers/` Python package MUST be created with `__init__.py`
- **FR-002**: `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` MUST be extracted from `agent/llm_client.py` into `providers/open_ai.py`
- **FR-003**: `LLMClient` ABC MUST remain in `agent/llm_client.py` — no changes to its interface
- **FR-004**: Provider resolution utilities (`resolve_provider`, `normalize_base_url`, `ProviderRegistry`, `get_provider_registry`, `ProviderInfo`, `ProviderFactory`, `OPENAI_COMPATIBLE`, `OPENAI_RESPONSES`, `OPENAI_CHAT_COMPLETIONS`, `DEFAULT_BASE_URL`, `OPENAI_BASE_URL`, `VALID_PROVIDERS`, `_PROVIDER_ALIASES`) MUST be moved from `core/providers.py` to `providers/providers.py`
- **FR-005**: `core/providers.py` MUST be deleted after its contents are moved — no re-export shim

**Import updates:**

- **FR-006**: All internal imports across `tinycua_sdk/` and `tests/` MUST be updated to import from the new canonical locations
- **FR-007**: `agent/__init__.py` MUST import `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` from `tinycua_sdk.providers.open_ai` instead of `tinycua_sdk.agent.llm_client`
- **FR-008**: `agent/llm_client.py` MUST NOT re-export `OpenAIResponsesClient` or `OpenAIChatCompletionsClient` — remove them from `__all__` and from the module

**Verification:**

- **FR-009**: All existing unit and integration tests MUST pass after the reorganization
- **FR-010**: Smoke tests MUST verify that both `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` can be instantiated from their new canonical import paths
- **FR-011**: Smoke tests MUST verify that the old import paths (`tinycua_sdk.agent.llm_client`) raise `ImportError`

### Key Entities

- **`providers/` package**: New package containing all provider-specific client implementations and resolution utilities
- **`providers/open_ai.py`**: Contains `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` (extracted from `agent/llm_client.py`)
- **`providers/providers.py`**: Contains provider resolution utilities (moved from `core/providers.py`). Note the intentional duplicate name `tinycua_sdk.providers.providers` — the filename is self-documenting ("provider utilities from the providers package").
- **`LLMClient` (ABC)**: Remains in `agent/llm_client.py` — the abstract interface for all LLM clients
- **`core/providers.py`**: Deleted — no replacement shim

---

## Success Criteria

- [ ] **New `providers/` package exists**: Contains `__init__.py`, `open_ai.py`, `providers.py`
- [ ] **Canonical imports resolve**: Both `from tinycua_sdk.providers.open_ai import OpenAIResponsesClient` and `from tinycua_sdk.providers.open_ai import OpenAIChatCompletionsClient` work, and `from tinycua_sdk.providers.providers import resolve_provider` works
- [ ] **Old import paths removed**: `from tinycua_sdk.agent.llm_client import OpenAIResponsesClient` and `from tinycua_sdk.agent.llm_client import OpenAIChatCompletionsClient` raise `ImportError`; `from tinycua_sdk.core.providers import resolve_provider` also raises `ImportError`
- [ ] **All tests pass**: `uv run pytest tests/` passes with only import-path changes (no behavioral changes)
- [ ] **No dead code**: `core/providers.py` is deleted; `agent/llm_client.py` no longer references `OpenAIResponsesClient` or `OpenAIChatCompletionsClient`

---

## Testing Plan

### Unit Tests

- No new behavioral unit tests needed. New smoke tests in `tests/unit/test_import_sanity.py` (per FR-010/FR-011) verify import path correctness — both that new paths resolve and that old paths raise `ImportError`.
- Existing tests continue to pass after import updates
- The existing `test_providers.py` tests must pass from the new `providers/providers.py` location
- The existing `test_llm_client.py` tests for `OpenAIResponsesClient` and `OpenAIChatCompletionsClient` must pass after import updates

### Integration Tests

- No new integration tests needed; existing integration tests pass after import updates

### Manual Tests

- Verify that `from tinycua_sdk.providers.open_ai import OpenAIResponsesClient, OpenAIChatCompletionsClient` resolves in a Python interpreter
- Verify that `from tinycua_sdk.agent.llm_client import OpenAIResponsesClient` and `from tinycua_sdk.agent.llm_client import OpenAIChatCompletionsClient` each raise `ImportError`

---

## Open Questions

None.
