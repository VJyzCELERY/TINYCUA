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
- A single `LLMClient` ABC with an httpx-based client tightly coupled to OpenAI's Responses API format
- No mechanism to support non-OpenAI providers (Google, etc.)
- No canonical SSE event schema — normalization logic is embedded inside the existing client with no formal contract
- No raw SSE pass-through stream for external consumers
- `providers.py` only handles URL normalization and aliases — no provider registry or client factory
- The `StreamEvent` model (`models/response.py`) and `events.py` TypedDicts have overlapping but inconsistent event definitions

### Non-Goals

- Building provider SDKs from scratch (we delegate to official PyPI packages)
- Non-SSE transport protocols (initial scope is SSE only)
- Supporting providers that do not offer official Python SDKs (community SDKs may be added later via extensions)
- The Agent Loop itself will be updated to consume the new canonical event schema (content.delta, content.done, tool_call.started, etc.) — the loop must be modified for the new provider system
- Provider-specific response models beyond what the canonical format requires

### Constraints

- Must honor each provider's official SDK interface — no custom wrappers that break upgrade compatibility
- **Phase 1 is a breaking refactoring**: The existing `LLMClient` ABC is refactored in-place — `chat()` becomes concrete and delegates to an abstract `_chat_impl()`. Existing subclasses must be updated to implement `_chat_impl()`. The `OpenAICompatibleClient` must be updated to match the new contract in Phase 1. **Backward compatibility is not maintained.** No deprecation shim or backward-compatibility layer is provided. Users should migrate to `"openai-responses"` or update their custom subclasses before Phase 2.
- **Phase 1 default provider change**: `LanguageModel.provider` default changes from `"openai-compatible"` to `"openai-responses"`. `LanguageModel()` with no explicit provider now resolves to the `"openai-responses"` provider via `ProviderRegistry`. Old defaults (`"openai"`, `"openai-compatible"`) are no longer registered — they raise `ProviderNotSupportedError`. Callers must explicitly pass `provider="openai-responses"` or update their configuration.
- **Phase 1 default base URL**: `normalize_base_url(None, "openai-responses")` returns the OpenAI API base URL (`https://api.openai.com/v1`) by default, matching the behavior of the existing `"openai"` provider. Local development users must set an explicit `base_url` to override.
- The canonical SSE event schema must be provider-agnostic — no OpenAI-specific field names
- Raw SSE pass-through must be delivered as paired `(canonical_event, raw_event)` tuples in the same async iterator. The `canonical_event` slot MAY be `None` for provider-native raw events that have no canonical semantic equivalent. All provider SDK stream events MUST be yielded in arrival order when `raw_events=True`. The raw event is a lossless representation of the provider's original SDK event object
- Providers must be resolvable from a `LanguageModel.provider` string

---

## User Scenarios & Testing

### Primary Scenario

A developer building an agent application wants to use OpenAI's Responses API. They configure a `LanguageModel` with `provider="openai-responses"` and the SDK automatically selects the OpenAI Responses API provider client. Later, when OpenAI Chat Completions API support is added, they can switch to `provider="openai"` instead. The Agent Loop consumes canonical events regardless of which provider is active.

### Acceptance Scenarios

#### Phase 1 — Schema, Registry, and Contract (Current Phase)

1. **Given** a `LanguageModel` with a registered provider string, **When** `ProviderRegistry.create_client(model_config)` is called, **Then** a configured `LLMClient`-conforming instance is returned, ready for use.

2. **Given** a `LanguageModel` with a registered provider string, **When** a client is resolved via `ProviderRegistry.create_client(model_config)` and `client.chat()` is called with a simple message list, **Then** the returned response conforms to `LLMResponse` (non-streaming) or the async iterator yields `LLMEvent` items (streaming), regardless of which provider is configured.

3. **Given** an unsupported provider string, **When** `ProviderRegistry.create_client(model_config)` is called, **Then** a `ProviderNotSupportedError` is raised indicating which providers are supported — the error is raised at registry resolution, not during the `chat()` call.

4. **Given** a provider registered with `ProviderRegistry.register()`, **When** `ProviderRegistry.list_providers()` is called, **Then** the registered provider appears in the returned list with its metadata.

#### Phase 2 — Provider SDK Integration (Future Milestone)

5. **Given** a `LanguageModel` with `provider="openai-responses"`, **When** `ProviderRegistry.create_client(model_config)` is called, the returned `LLMClient` instance's `chat()` method invokes the OpenAI Responses API provider client, normalizing the Responses API stream events into the canonical schema. The Agent Loop calls only `chat()` on the resolved client — it does not directly invoke the registry.

6. **Given** a streaming request with `stream=True` and `raw_events=True`, **When** the async iterator is consumed, **Then** each yielded item is a `(canonical_event, raw_event)` tuple where the raw event is the provider's original SDK event object (lossless).

7. **Given** a `tool_call.ready` event is received and the Agent Loop executes the tool, **When** a `ToolResultMessage` with the matching `call_id` is appended to the messages list and `chat()` is called again, **Then** the provider client correctly translates the tool result into the provider SDK's continuation format (e.g., `previous_response_id` + `function_call_output` for OpenAI Responses API) and the model continues the interaction — the Agent Loop does not manage any provider-specific fields.

### Edge Cases

- What happens when a provider SDK version changes and breaks the normalizer? The normalizer should be version-pinned or tested against known SDK versions.
- How does the system handle providers that don't support streaming? The provider client raises `ProviderApiError("Provider does not support streaming")` when `stream=True` is requested and the provider has no streaming capability.
- What is the behavior with empty/null API keys? Provider SDKs should raise appropriate auth errors.
- How are rate limits and retries handled? Delegated to provider SDK retry mechanisms.
- What happens when a provider has no tool-call support? The canonical event stream omits tool-related events.
- Does the tool-call streaming have a defined event order? Yes — the design defines a normative state machine: providers MUST emit exactly one `tool_call.ready` per executable tool call, and the Agent Loop MUST execute tools only from `tool_call.ready` events. `tool_call.arguments.done` is informational only and is NOT an execution trigger.
- How does the Agent Loop submit tool results back to the provider? By appending a `ToolResultMessage` (with `call_id` from `tool_call.ready`) to the messages list and calling `chat()` again. Each provider client handles the provider-specific continuation mechanism internally (e.g., `previous_response_id` for OpenAI Responses API) — the loop never manages provider-specific state.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST define a provider-agnostic `LLMClient` abstract base class with `chat()` and `close()` methods that all providers implement. The `chat()` method MUST accept `list[LLMMessage]` and `list[LLMToolSpec] | None` as input parameters (not raw `dict` types) to ensure provider-neutral messaging.
- **FR-002**: Each supported provider MUST have a concrete `LLMClient` subclass that wraps the provider's official Python SDK.
- **FR-003**: The system MUST provide a **provider registry** that maps provider identifiers (e.g., `"openai-responses"`, `"openai"`) to their client implementations.
- **FR-004**: The provider selection MUST be driven by `LanguageModel.provider` at runtime with no code changes.
- **FR-005**: The system MUST define a **canonical SSE event schema** — a formal set of event types and shapes that all provider normalizers output.
- **FR-006**: Each provider client MUST include an **SSE normalizer** that converts the provider's raw stream events into the canonical schema.
- **FR-007**: The system MUST expose a **raw SSE pass-through** mode where the async iterator yields paired `(canonical_event, raw_event)` tuples so consumers can access provider-native events alongside canonical events. Every provider SDK stream event MUST be yielded in arrival order when `raw_events=True`; provider-native events without a canonical equivalent use `None` in the canonical slot.
- **FR-008**: The `LanguageModel` model MUST support new provider-specific configuration fields without breaking existing providers.
- **FR-009**: The system MUST raise a clear, actionable error when an unsupported or misspelled provider identifier is used.
- **FR-010**: The system MUST support provider SDK initialization (API keys, base URLs, timeouts) from `LanguageModel` configuration.
- **FR-011**: The system MUST define a normative tool-call streaming state machine that specifies event ordering — providers MUST emit exactly one execution-trigger event (`tool_call.ready`) per executable tool call, and the Agent Loop MUST execute tools only from that event.
- **FR-012**: The system MUST define canonical input types (`LLMMessage` discriminated union, `LLMToolSpec`) that all `LLMClient.chat()` calls accept, so the Agent Loop never constructs provider-specific message dicts.
- **FR-013**: The system MUST define a tool-result continuation contract where the Agent Loop submits tool outputs by appending `ToolResultMessage` (with `call_id` from `tool_call.ready`) to the messages list, and each provider client internally translates this into the provider SDK's continuation mechanism (e.g., `previous_response_id` for OpenAI Responses API). The `chat()` method MUST handle continuation internally — there must be no separate `continue_with_tools()` method.

### Key Entities

- **LLMClient (ABC)**: Abstract base class for all provider clients. Defines `chat()` (with streaming support), `close()`, and the canonical event contract.
- **Provider Client**: Concrete implementation of `LLMClient` wrapping a specific provider SDK (e.g., `OpenAIResponsesClient`, `OpenAIChatClient`).
- **SSE Normalizer**: Per-provider component that maps raw SDK stream events to canonical schema events and exposes raw pass-through.
- **Provider Registry**: Runtime mapping of provider strings to client factories, with validation and error handling.
- **Canonical Event**: A typed event dict adhering to the canonical schema — provider-agnostic, consumable by the Agent Loop.
- **Canonical Message**: A discriminated union of typed message dicts (`SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolResultMessage`) that all provider clients accept as input. Provider clients translate these into their SDK's native message format.
- **Canonical Tool Spec**: A typed tool definition dict (`name`, `description`, `parameters`) in provider-neutral form that all provider clients accept.
- **Tool Result Continuation**: The pattern where the Agent Loop submits tool outputs by appending `ToolResultMessage` (with `call_id` from `tool_call.ready`) to the message list. Each provider client owns the SDK-specific continuation state internally.
- **Raw SSE Stream**: When `raw_events=True`, each yielded item is a `(canonical_event, raw_event)` tuple where the raw event is the provider's original SDK event object (lossless, not a dict conversion).

---

## Success Criteria

### Phase 1 (Immediate) Criteria

- [x] **Canonical SSE schema defined**: All canonical event TypedDicts (`ContentDeltaEvent`, `ContentDoneEvent`, `ToolCall*`, `Response*`, `LLMResponse`, `RawSseEvent`, `TokenUsage`) are defined and the `LLMEvent` discriminated union type alias type-checks correctly.
- [x] **Canonical input types defined**: `LLMMessage` (discriminated union of `SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolResultMessage`) and `LLMToolSpec` TypedDicts are defined and type-check correctly.
- [x] **LLMClient ABC contract**: The refactored `LLMClient` ABC with `chat()` and `close()` compiles and documents the canonical event return types and tool-call state machine rules.
- [x] **ProviderRegistry contract**: The registry provides `register()`, `create_client()`, `list_providers()`, `is_supported()`, and `reset()` methods; unsupported provider strings raise clear errors.
- [x] **Error classes**: `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` are defined and raised appropriately.
- [x] **Phase 1 unit tests pass**: Canonical schema validation, registry behavior, error cases all pass without any provider SDK installed.
- [x] **Phase 1 integration tests pass**: Provider switching via `LanguageModel.provider` passes at the compile-time/contract level.
- [x] **Breaking change documented**: The in-place `LLMClient` refactoring is documented as an intentional breaking change. Existing subclasses must add `_chat_impl()`. Migration path from legacy identifiers (`"openai"`, `"openai-compatible"`) to `"openai-responses"` is documented. The old `OpenAICompatibleClient` is updated to match the new contract in Phase 1 (not deferred to Phase 2).

### Full Roadmap Criteria (including Future Phases)

- [ ] **Provider-agnostic chat**: A single `LLMClient.chat()` call works identically (from the caller's perspective) across different providers (OpenAI Responses API, future OpenAI Chat Completions API, etc.).
- [ ] **Streaming normalization**: Streaming events from supported providers are normalized to the canonical schema with no provider-specific field leaks.
- [ ] **Raw pass-through**: Consumers can opt into raw SSE streams and receive the provider's native event format.
- [ ] **Config-driven switching**: Changing `LanguageModel.provider` switches the provider client without code changes (Phase 1 enables the switching infrastructure; Phase 2+ adds the actual implementations).
- [ ] **Full provider tests pass**: All unit and integration tests for the new provider system pass.

---

## Testing Plan

### Phase 1 Tests (Schema, Registry, Contract — No Provider SDK Mocking)

**Unit Tests — Phase 1**:

- Test canonical schema TypedDicts/type-alias type-checks: `ContentDeltaEvent`, `ContentDoneEvent`, `ToolCall*`, `Response*`, `LLMResponse`, `RawSseEvent`, `TokenUsage` — all required shapes and import correctly
- Test canonical input types type-checks: `SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolResultMessage`, `LLMMessage` discriminated union, `LLMToolSpec`
- Test `ProviderRegistry` behavior: `register()`, `create_client()`, `list_providers()`, `is_supported()`, `reset()` work correctly
- Test unsupported provider strings raise `ProviderNotSupportedError`
- Test `LanguageModel.provider` field drives client selection at the registry/contract level (no actual provider SDK)
- Test `raw_events=True` with `stream=False` raises `ValueError`
- Test error classes (`ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError`) can be imported and raised

**Integration Tests — Phase 1**:

- Test registry provider switching via `LanguageModel.provider` at compile-time/contract level (use fake/mock LLMClient implementations, no provider SDKs)
- Verify the `LLMClient` ABC compiles with correct canonical input and output type signatures

### Phase 2+ Tests (Provider SDK Integration)

**Unit Tests — Phase 2+**:

- Test each provider client's `chat()` (non-streaming) returns expected canonical response shape
- Test each provider normalizer maps all known provider event types to canonical equivalents
- Test tool-result continuation: submit `ToolResultMessage` with matching `call_id` and verify the provider client translates it into the correct SDK continuation format (e.g., `previous_response_id` for OpenAI Responses API)
- Test raw pass-through stream yields identical events to the provider SDK's raw output
- Test edge cases: empty responses, connection errors, auth failures, rate limits

**Integration Tests — Phase 2+**:

- Test end-to-end chat flow with mocked provider SDK responses for each provider
- Test streaming end-to-end: raw events pass through, canonical events are normalized
- Test provider switching at runtime via config changes
- Verify that existing integration tests (`test_custom_agent_loop.py`, `test_language_model.py`) still pass

**Manual Tests — Phase 2+**:

- Run against real OpenAI API endpoints with a test API key to verify end-to-end streaming and normalization

---

## Status Tracker

| Item | Status | Phase | Notes |
|------|--------|-------|-------|
| Spec & Design | Complete | Phase 1 | All questions resolved, ready for planning |
| Canonical SSE Schema | Complete | Phase 1 | Formal TypedDict definitions complete; `LLMEvent` union type-checks correctly |
| LLMClient ABC | Complete | Phase 1 | Refactored contract with canonical event return types; `OpenAICompatibleClient` updated |
| Provider Registry | Complete | Phase 1 | Singleton registry with factory, validation, reset; `openai-responses` pre-registered |
| Error Classes | Complete | Phase 1 | `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` defined and wired |
| Upgrade Guide & Migration Docs | Complete | Phase 1 | Breaking change documented; migration path from legacy identifiers to `openai-responses` |
| Unit Tests (Phase 1) | Complete | Phase 1 | Schema (output + input types), registry, error cases, contract tests all pass |
| Integration Tests (Phase 1) | Complete | Phase 1 | Compile-time contract tests for registry switching |
| OpenAI Responses API Provider | Complete | Phase 1 | `openai-responses` client via `OpenAICompatibleClient`; httpx-based, no `openai` PyPI SDK |
| Raw SSE Pass-Through | Complete | Phase 1 | Paired tuple mode; unknown events use `None` canonical slot |
| Agent Loop Migration | Complete | Phase 1 | `loop.py` consumes canonical event schema with tool-call ready-gating |
| Unit/Integration Tests (Phase 2+) | TODO | Phase 2+ | Provider-specific mocked and end-to-end tests |

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
   - **Decision**: The return signature for streaming with `raw_events=True` is `AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]`. Each yielded tuple pairs a canonical event (or `None` for raw-only provider events) with its corresponding raw provider event (or `None` for synthetic canonical events). Provider SDK events that have no canonical semantic equivalent are yielded with `None` in the canonical slot. All provider SDK stream events are yielded in arrival order when `raw_events=True`.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain — questions resolved
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
