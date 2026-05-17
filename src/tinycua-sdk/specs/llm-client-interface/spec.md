# Feature Specification: Unified LLM Client Interface with Swappable Providers

**Status**: Complete
**Created**: 2026-05-17
**Last Updated**: 2026-05-17
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Provide a unified **Agent + LLM Client** architecture so that the TINYCUA SDK can:
- Support multiple LLM providers (OpenAI Responses API, OpenAI Chat Completions API, etc.) through a single, consistent interface
- Delegate to each provider's official SDK (e.g., `openai` PyPI powers both `openai-responses` and `openai` provider clients) rather than rebuilding HTTP-level clients
- Normalize provider-specific SSE event streams into a canonical format for internal consumption (Agent Loop)
- Expose raw SSE event streams as a pass-through for consumers that need provider-native formats
- Allow users to swap providers by configuration alone (e.g., change a config field) without code changes

### Gaps

Today the SDK has:
- A single `LLMClient` ABC and `OpenAICompatibleClient` that uses httpx directly — tightly coupled to OpenAI's Responses API format
- No mechanism to support non-OpenAI providers (Google, etc.)
- No canonical SSE event schema — normalization logic (`_normalize_responses_event`) is embedded inside `OpenAICompatibleClient` with no formal contract
- No raw SSE pass-through stream for external consumers
- `providers.py` only handles URL normalization and aliases — no provider registry or client factory
- The `StreamEvent` model (`models/response.py`) and `events.py` TypedDicts have overlapping but inconsistent event definitions

### Non-Goals

- Building provider SDKs from scratch (we delegate to official PyPI packages)
- Non-SSE transport protocols (initial scope is SSE only)
- Supporting providers that do not offer official Python SDKs (community SDKs may be added later via extensions)
- Refactoring the Agent Loop itself — the loop continues consuming canonical events as it does today
- Provider-specific response models beyond what the canonical format requires

### Constraints

- Must honor each provider's official SDK interface — no custom wrappers that break upgrade compatibility
- Backward compatibility: existing code using `LLMClient`, `OpenAICompatibleClient`, and `StreamEvent` must continue to work during a deprecation period
- The canonical SSE event schema must be provider-agnostic — no OpenAI-specific field names
- Raw SSE pass-through must be a separate stream that delivers the provider's original event format unchanged
- Providers must be resolvable from a `LanguageModel.provider` string

---

## User Scenarios & Testing

### Primary Scenario

A developer building an agent application wants to use OpenAI's Responses API. They configure a `LanguageModel` with `provider="openai-responses"` and the SDK automatically selects the OpenAI Responses API provider client. Later, when OpenAI Chat Completions API support is added, they can switch to `provider="openai"` instead. The Agent Loop consumes canonical events regardless of which provider is active.

### Acceptance Scenarios

1. **Given** a `LanguageModel` with `provider="openai-responses"`, **When** `LLMClient.chat()` is called, **Then** the OpenAI Responses API provider client is used, normalizing the Responses API stream events into the canonical schema.

2. **Given** a streaming request with `stream=True`, **When** the user requests raw SSE events, **Then** a separate async iterator yields the provider's original event format unchanged.

3. **Given** an unsupported provider string, **When** `LLMClient.chat()` is called, **Then** a clear error is raised indicating which providers are supported.

### Edge Cases

- What happens when a provider SDK version changes and breaks the normalizer? The normalizer should be version-pinned or tested against known SDK versions.
- How does the system handle providers that don't support streaming? The canonical stream should yield a single completed event.
- What is the behavior with empty/null API keys? Provider SDKs should raise appropriate auth errors.
- How are rate limits and retries handled? Delegated to provider SDK retry mechanisms.
- What happens when a provider has no tool-call support? The canonical event stream omits tool-related events.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST define a provider-agnostic `LLMClient` abstract base class with `chat()` and `close()` methods that all providers implement.
- **FR-002**: Each supported provider MUST have a concrete `LLMClient` subclass that wraps the provider's official Python SDK.
- **FR-003**: The system MUST provide a **provider registry** that maps provider identifiers (e.g., `"openai-responses"`, `"openai"`) to their client implementations.
- **FR-004**: The provider selection MUST be driven by `LanguageModel.provider` at runtime with no code changes.
- **FR-005**: The system MUST define a **canonical SSE event schema** — a formal set of event types and shapes that all provider normalizers output.
- **FR-006**: Each provider client MUST include an **SSE normalizer** that converts the provider's raw stream events into the canonical schema.
- **FR-007**: The system MUST expose a **raw SSE pass-through** stream alongside the canonical stream so consumers can access provider-native events.
- **FR-008**: The `LanguageModel` model MUST support new provider-specific configuration fields without breaking existing providers.
- **FR-009**: The system MUST raise a clear, actionable error when an unsupported or misspelled provider identifier is used.
- **FR-010**: The system MUST support provider SDK initialization (API keys, base URLs, timeouts) from `LanguageModel` configuration.

### Key Entities

- **LLMClient (ABC)**: Abstract base class for all provider clients. Defines `chat()` (with streaming support), `close()`, and the canonical event contract.
- **Provider Client**: Concrete implementation of `LLMClient` wrapping a specific provider SDK (e.g., `OpenAIResponsesClient`, `OpenAIChatClient`).
- **SSE Normalizer**: Per-provider component that maps raw SDK stream events to canonical schema events and exposes raw pass-through.
- **Provider Registry**: Runtime mapping of provider strings to client factories, with validation and error handling.
- **Canonical Event**: A typed event dict adhering to the canonical schema — provider-agnostic, consumable by the Agent Loop.
- **Raw SSE Stream**: An async iterator yielding the provider's original event format unmodified.

---

## Success Criteria

- [ ] **Provider-agnostic chat**: A single `LLMClient.chat()` call works identically (from the caller's perspective) across different providers (OpenAI Responses API, future OpenAI Chat Completions API, etc.).
- [ ] **Streaming normalization**: Streaming events from supported providers are normalized to the canonical schema with no provider-specific field leaks.
- [ ] **Raw pass-through**: Consumers can opt into raw SSE streams and receive the provider's native event format.
- [ ] **Registry error handling**: Unsupported provider strings raise clear errors listing supported options.
- [ ] **Config-driven switching**: Changing `LanguageModel.provider` from `"openai-responses"` to `"openai"` switches the provider client without code changes.
- [ ] **Existing tests pass**: All existing unit and integration tests for `LLMClient`, `OpenAICompatibleClient`, and the Agent Loop continue to pass.
- [ ] **Backward compatibility**: The existing `OpenAICompatibleClient` class remains importable and functional (deprecated but not removed).

---

## Testing Plan

### Unit Tests

- Test each provider client's `chat()` (non-streaming) returns expected canonical response shape
- Test each provider normalizer maps all known provider event types to canonical equivalents
- Test raw pass-through stream yields identical events to the provider SDK's raw output
- Test provider registry: valid providers resolve correctly, invalid providers raise clear errors
- Test `LanguageModel` provider field drives client selection
- Test edge cases: empty responses, connection errors, auth failures, rate limits

### Integration Tests

- Test end-to-end chat flow with mocked provider SDK responses for each provider
- Test streaming end-to-end: raw events pass through, canonical events are normalized
- Test provider switching at runtime via config changes
- Verify that existing integration tests (`test_custom_agent_loop.py`, `test_language_model.py`) still pass

### Manual Tests

- Run against real OpenAI API endpoints with a test API key to verify end-to-end streaming and normalization

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec & Design | Complete | All questions resolved, ready for planning |
| Provider Registry | TODO | |
| Canonical SSE Schema | TODO | |
| OpenAI Responses API Provider | TODO | `openai-responses` ID |
| Raw SSE Pass-Through | TODO | |
| Backward Compat Shims | TODO | |
| Unit Tests | TODO | |
| Integration Tests | TODO | |

---

## Resolved Questions

0. **Provider naming convention: `openai-responses` vs `openai`**
   - **Status**: Decided
   - **Decision**: The existing `/responses`-based client becomes the **OpenAI Responses API** provider with ID `openai-responses`. The `openai` provider ID is reserved for the future **OpenAI Chat Completions API** provider. This avoids confusion and allows both to coexist — Responses API (newer, `/responses` endpoint) and Chat Completions API (standard, `/chat/completions` endpoint).

1. **Provider SDK version pinning**
   - **Status**: Decided
   - **Decision**: Pin major versions in `pyproject.toml` dependency declarations. Each provider SDK dependency declares its minimum major version, and upgrades are deliberate (not automatic).

2. **Raw pass-through: how to correlate canonical events with raw events**
   - **Status**: Decided
   - **Decision**: The return signature for streaming with `raw_events=True` is `AsyncIterator[tuple[CanonicalEvent, RawEvent | None]]`. Each yielded tuple pairs the canonical event with its corresponding raw provider event. When there is no corresponding raw event (e.g., synthetic events), the raw slot is `None`.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain — questions resolved
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
