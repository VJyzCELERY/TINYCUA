# Design Document: Unified LLM Client Interface with Swappable Providers

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-05-17

---

## Overview

This design introduces a unified **Agent + LLM Client** architecture for the TINYCUA SDK. Instead of rebuilding HTTP-level clients for each provider, we delegate to each provider's official Python SDK (e.g., `openai` PyPI) and wrap them behind a common `LLMClient` abstract base class. Each provider client includes an **SSE normalizer** that converts provider-specific streaming events into a canonical format consumed by the Agent Loop, while simultaneously exposing a **raw SSE pass-through** for consumers that need provider-native events. A **provider registry** maps configuration-driven provider identifiers to concrete client implementations, enabling provider switching via `LanguageModel.provider` alone.

The affected subproject is `tinycua-sdk`. The existing `OpenAICompatibleClient` (httpx-based, `/responses` endpoint) is **removed** and replaced by a properly normalized **OpenAI Responses API** provider with ID `openai-responses`, wrapping the `openai` PyPI SDK's Responses API. This is a **breaking change**: old provider strings (`"openai"`, `"openai-compatible"`) are NOT supported. The `openai` provider ID is reserved for a future **OpenAI Chat Completions API** provider. No backward-compatibility shim is provided.

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       Consumer Code                          │
│              (Agent Loop / Custom Loop / End User)            │
└──────────┬──────────────────────────────────────┬────────────┘
           │ chat(messages, tools, model_config)  │
           ▼                                      │
┌──────────────────────────┐                     │
│    LLMClient (ABC)       │                     │
│   ┌────────────────────┐ │                     │
│   │  Provider Registry │ │                     │
│   │  get_client(...)   │ │                     │
│   └─────────┬──────────┘ │                     │
└─────────────┼────────────┘                     │
              │ resolves to                      │
              ▼                                  │
┌─────────────────────────────┐                  │
│  Provider Client Instance   │                  │
│  (e.g. OpenAIClient)        │                  │
│  ┌───────────────────────┐  │                  │
│  │   Official Provider   │  │  raw events      │
│  │   SDK (e.g. openai)   │──┼──────────────────┼──▶ Raw SSE Stream
│  └───────────┬───────────┘  │                  │
│              │ SDK events   │                  │
│              ▼              │                  │
│  ┌───────────────────────┐  │                  │
│  │   SSE Normalizer      │  │  canonical       │
│  │   (per-provider)      │──┼──────────────────┼──▶ Canonical Event Stream
│  └───────────────────────┘  │                  │
└─────────────────────────────┘                  │
                                                 ▼
                                        ┌────────────────┐
                                        │  Agent Loop     │
                                        │  (consumes      │
                                        │   canonical)    │
                                        └────────────────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/agent/llm_client.py` | Modified — Refactored | `LLMClient` ABC updated with canonical event contract; `OpenAICompatibleClient` deprecated |
| `tinycua_sdk/agent/events.py` | Modified — Extended | Canonical event TypedDicts formalized; `RawSseEvent` TypedDict added for paired tuples |
| `tinycua_sdk/agent/llm_model.py` | Modified — Extended | May need minor additions for provider-specific config |
| `tinycua_sdk/core/providers.py` | Modified — Extended | Provider registry and client factory logic added |
| `tinycua_sdk/models/response.py` | No changes — usage migrated to CanonicalEvent | StreamEvent itself unchanged (raw pass-through via paired tuples); consumers migrate to CanonicalEvent |
| `tinycua_sdk/agent/loop.py` | Modified (Phase 2) | Updated to consume new canonical event schema (`content.delta`, `content.done`, `tool_call.*`, etc.) |
| `tinycua_sdk/providers/openai_responses/` | New (Phase 2) | OpenAI Responses API provider client + normalizer; registered as `"openai-responses"` |
| `tinycua_sdk/providers/openai_chat/` | New (Phase 3) | OpenAI Chat Completions API provider client (future phase, ID `"openai"`) |

### Provider Migration Table

This is a **breaking change**. The following table documents the migration path for existing provider strings:

| Old Provider String | New Provider String | Migration Action |
|---|---|---|
| `"openai"` | `"openai-responses"` | Replace `provider="openai"` with `provider="openai-responses"`. The `"openai"` ID is now reserved for a future Chat Completions API provider (not yet implemented). |
| `"openai-compatible"` | `"openai-responses"` | Replace `provider="openai-compatible"` with `provider="openai-responses"`. The old httpx-based client is removed entirely. |
| `"openai-responses"` | `"openai-responses"` | No change (new canonical name). |

**Key points**:
- `LanguageModel.provider` validation accepts only `"openai-responses"` (and future registered provider IDs).
- The old `OpenAICompatibleClient` class and its httpx-based implementation are **removed** — no deprecation shim, no backward-compatibility layer.
- Existing `StreamEvent` usage should be migrated to the canonical `CanonicalEvent` schema. The `StreamEvent` model itself remains unchanged (raw pass-through is via the paired tuple API, not by modifying `StreamEvent`).
- The `events.py` TypedDicts are consolidated into the new canonical schema — old TypedDicts are removed.

---

## Data Model

### New Entities

```python
# ──────────────────────────────────────────────
# Canonical SSE Event Schema (TypedDicts)
# ──────────────────────────────────────────────

class CanonicalEvent(TypedDict):
    """Base shape for all canonical stream events."""
    type: str  # canonical event type name

class ContentDeltaEvent(CanonicalEvent):
    """Text content delta from the LLM."""
    type: Literal["content.delta"]
    delta: str
    index: int

class ContentDoneEvent(CanonicalEvent):
    """Text content block completed."""
    type: Literal["content.done"]
    index: int

class ToolCallStartedEvent(CanonicalEvent):
    """New tool call initiated."""
    type: Literal["tool_call.started"]
    id: str                    # Provider output item ID (correlates deltas to a single call)
    call_id: str               # Provider tool call ID — used when submitting tool results
    name: str

class ToolCallArgumentsDeltaEvent(CanonicalEvent):
    """Partial tool call arguments."""
    type: Literal["tool_call.arguments.delta"]
    id: str                    # Provider output item ID (matches ToolCallStartedEvent.id)
    arguments: str

class ToolCallArgumentsDoneEvent(CanonicalEvent):
    """Tool call arguments complete — execution-ready metadata included."""
    type: Literal["tool_call.arguments.done"]
    id: str                    # Provider output item ID
    call_id: str               # Provider tool call ID — used when submitting tool results
    name: str                  # Tool name (copied from the started event for convenience)
    arguments: str             # Final complete JSON arguments

class ToolCallReadyEvent(CanonicalEvent):
    """Tool call ready for execution — all metadata in a single event.

    This is the event the Agent Loop should consume to execute a tool call.
    It carries all necessary data (id, call_id, name, arguments) without
    requiring the consumer to correlate state across multiple partial events.
    """
    type: Literal["tool_call.ready"]
    id: str                    # Provider output item ID
    call_id: str               # Provider tool call ID — used when submitting tool results
    name: str                  # Tool name
    arguments: str             # Final complete JSON arguments

class CanonicalUsage(TypedDict):
    """Provider-agnostic token usage schema.

    Provider normalizers MUST map their SDK's usage fields into these
    canonical field names. Fields marked Optional may be omitted when the
    provider SDK does not report them.
    """
    input_tokens: int | None                # Tokens consumed by the prompt
    output_tokens: int | None               # Tokens generated in the response
    total_tokens: int | None                # input_tokens + output_tokens (when available)

class ResponseUsageEvent(CanonicalEvent):
    """Token usage information."""
    type: Literal["response.usage"]
    usage: CanonicalUsage

class ResponseCompletedEvent(CanonicalEvent):
    """Stream completed successfully."""
    type: Literal["response.completed"]
    finish_reason: str

class ResponseFailedEvent(CanonicalEvent):
    """Stream failed with error."""
    type: Literal["response.failed"]
    error: dict

```

```python
# ──────────────────────────────────────────────
# Canonical Non-Streaming Response
# ──────────────────────────────────────────────

class CanonicalResponse(TypedDict):
    """Normalized response from a non-streaming chat completion.

    Returned by LLMClient.chat() when stream=False. All provider clients
    normalize their SDK's response into this shape.
    """
    content: str | None                    # Text content, None if only tool calls
    tool_calls: list[dict] | None          # List of {id, call_id, name, arguments} — full tool call metadata
    usage: CanonicalUsage | None            # Token usage — normalized to CanonicalUsage schema
    finish_reason: str | None              # "stop", "tool_calls", "length", etc.
    model: str                             # Model name that generated the response
```

```python
# ──────────────────────────────────────────────
# Raw pass-through event (paired with canonical)
# ──────────────────────────────────────────────

class RawSseEvent(TypedDict):
    """Raw provider-native SSE event wrapper — lossless.

    This is NOT a CanonicalEvent — it is yielded alongside the canonical
    event as a second element in the (canonical, raw) tuple when
    raw_events=True. The raw_event field holds the original provider SDK
    event object unchanged (lossless). It is NOT a dict conversion — it is
    the actual SDK object (e.g. an openai.StreamEvent instance), preserving
    all original fields and types.
    """
    provider: str       # e.g., "openai-responses"
    raw_event: Any      # original provider SDK event object, lossless (not a dict)
```

```python
# ──────────────────────────────────────────────
# Provider Registry
# ──────────────────────────────────────────────

ProviderFactory = Callable[[LanguageModel], LLMClient]

@dataclass
class ProviderInfo:
    """Registered provider metadata."""
    id: str                                    # canonical identifier, e.g. "openai-responses"
    factory: ProviderFactory                   # factory creating a configured LLMClient from LanguageModel config
    description: str                           # human-readable
    supported_models: list[str] | None = None  # optional model filter
```

### Schema Changes

- **`LanguageModel`**: No breaking changes. New `provider`-specific fields may be added as optional Pydantic fields (e.g., `openai_chat_params`).
- **`StreamEvent`** (in `models/response.py`): No changes — raw pass-through is handled via the paired tuple API, not by embedding raw events into the canonical stream. Consumers SHOULD migrate from `StreamEvent` to `CanonicalEvent` for new code.
- **`events.py`**: Existing TypedDicts replaced by the canonical schema above. Old TypedDicts are removed — no backward-compat aliases are retained.

---

## API / Interface Contracts

### LLMClient ABC (Refactored)

```python
class LLMClient(ABC):
    """Abstract base for LLM provider clients.

    All provider clients MUST implement this interface. The canonical event
    schema (defined in Data Model) is the contract between provider
    normalizers and event consumers (Agent Loop, custom loops).
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
        stream: bool = False,
        raw_events: bool = False,
    ) -> CanonicalResponse | AsyncIterator[CanonicalEvent] | AsyncIterator[tuple[CanonicalEvent | None, RawSseEvent | None]]:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with role and content.
            tools: Optional list of tool schemas.
            model_config: Language model configuration.
            stream: When True, return an async iterator of canonical events.
            raw_events: When True AND stream=True, yield paired
                        (canonical_event, raw_event) tuples. The raw slot is
                        None for synthetic canonical events that have no
                        corresponding provider event.
                        raw_events=True requires stream=True; if stream=False,
                        a ValueError is raised.

        Returns:
            CanonicalResponse when stream=False — normalized, provider-agnostic dict.
            AsyncIterator[CanonicalEvent] when stream=True, raw_events=False.
            AsyncIterator[tuple[CanonicalEvent, RawSseEvent | None]] when
            stream=True, raw_events=True.

        Raises:
            ProviderNotSupportedError: If the configured provider is not
                registered.
            ProviderAuthError: If credentials are missing or invalid.
            ProviderApiError: For provider SDK-level errors.
        """

    async def close(self) -> None:
        """Close and release provider SDK resources (HTTP sessions, etc.)."""
```

### Provider Registry API

```python
class ProviderRegistry:
    """Registry of available LLM provider clients.

    Providers are registered with a factory function that creates a configured
    client instance from a LanguageModel config. The factory receives the full
    LanguageModel object, enabling the provider to extract API keys, base URLs,
    timeouts, and model-specific settings.
    """

    def register(
        self,
        provider_id: str,
        factory: ProviderFactory,
        metadata: ProviderInfo | None = None,
    ) -> None:
        """Register a new provider with its factory.

        Args:
            provider_id: Canonical provider identifier (e.g. "openai-responses").
            factory: Callable that receives LanguageModel and returns a configured LLMClient.
            metadata: Optional ProviderInfo with description and supported models.
        """

    def create_client(self, model_config: LanguageModel) -> LLMClient:
        """Create a provider client instance from LanguageModel configuration.

        Uses model_config.provider to select the registered factory and
        passes the full model_config to it for provider SDK initialization
        (API keys, base URLs, timeouts, etc.).

        Raises:
            ProviderNotSupportedError: If model_config.provider is not registered.
        """

    def list_providers(self) -> list[ProviderInfo]:
        """List all registered providers with metadata."""

    def is_supported(self, provider_id: str) -> bool:
        """Check if a provider is registered."""

    def reset(self) -> None:
        """Reset the registry — clears all registered providers.

        Useful for testing to avoid test pollution from the singleton instance.
        """

# Singleton registry instance
_provider_registry = ProviderRegistry()
```

### Error Handling

| Error Case | Exception | Notes |
|------------|-----------|-------|
| Unsupported provider | `ProviderNotSupportedError(provider_id, supported=[...])` | Raised during client resolution |
| Missing/invalid API key | `ProviderAuthError("API key not configured")` | Wraps provider SDK auth errors |
| Provider SDK request failure | `ProviderApiError(status_code, message)` | Wraps SDK HTTP/connection errors |
| Invalid messages format | `ValueError("Invalid message format")` | Validated before SDK call |
| `raw_events=True` with `stream=False` | `ValueError("raw_events=True requires stream=True")` | Validated before SDK call |
| Streaming not supported | `ProviderApiError("Provider does not support streaming")` | Only if provider has no streaming capability |
| SDK incompatibility | `ImportError` or `ProviderApiError` | If SDK is missing or wrong version |

### Raw SSE Pass-Through Contract

When `raw_events=True` and `stream=True`, the async iterator yields paired `(canonical_event, raw_event)` tuples. **Every provider SDK stream event is yielded in arrival order** — provider-native events are never silently dropped. The canonical event slot MAY be `None` for provider-native raw events that have no canonical semantic equivalent. Synthetic canonical events (e.g., `response.completed` that the normalizer synthesizes without a raw counterpart) have `None` in the raw slot.

```python
stream = await client.chat(..., stream=True, raw_events=True)
async for canonical, raw in stream:
    if canonical is not None:
        # canonical is a CanonicalEvent dict — process normally
        process_canonical(canonical)
    if raw is not None:
        # raw is a RawSseEvent with provider + lossless raw_event
        provider = raw["provider"]   # e.g., "openai-responses"
        raw_data = raw["raw_event"]  # original provider SDK event object (lossless)
```

Consumers that want **only** raw events can filter via the canonical event type or the raw slot:

```python
stream = await client.chat(..., stream=True, raw_events=True)
async for canonical, raw in stream:
    if raw is not None:
        process_raw(raw["raw_event"])
```

---

## Implementation Phases

> **Note**: Each phase below is an independent implementation stage with its own spec and design document. This design document covers only Phase 1 (Foundation). Subsequent phases will have separate specs and designs.

### Phase 1 — Foundation: Interface, Schema, Registry (This Milestone)

This phase establishes the core abstractions and is **provider-agnostic** — no provider SDK integrations.

- [ ] **1.1**: Formalize the canonical SSE event schema in `events.py` — define all canonical event TypedDicts, `CanonicalResponse`, and `RawSseEvent`; replace existing TypedDicts with new canonical schema
- [ ] **1.2**: Refactor `LLMClient` ABC — update `chat()` return type to `CanonicalResponse` (non-streaming) and document canonical event contract in docstring; add `raw_events` parameter
- [ ] **1.3**: Implement `ProviderRegistry` in `core/providers.py` — register with factory, create_client, list, is_supported, reset
- [ ] **1.4**: Implement `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` exception classes in `core/exceptions.py`
- [ ] **1.5**: Write unit tests for:
      - Canonical event schema validation (`CanonicalEvent` subclasses, `CanonicalResponse`, `RawSseEvent`)
      - `ProviderRegistry` behavior (register, resolve, unsupported provider errors)
      - Error cases: auth failure, SDK import errors (unit-level)
- [ ] **1.6**: Write integration tests for:
      - Provider registry provider switching via `LanguageModel.provider`

### Phase 2 — OpenAI Responses API Provider (Next Milestone)

See separate spec and design for this phase.

- [ ] Build `OpenAIResponsesClient` wrapping the `openai` PyPI SDK Responses API:
      - `chat()` non-streaming via `openai.responses.create()` → normalize SDK response to `CanonicalResponse`
      - `chat()` streaming via `openai.responses.stream()` with SSE normalizer → normalize raw stream events to canonical schema
      - Extract and formalize the existing `_normalize_responses_event()` into the per-provider normalizer
      - Raw pass-through via `raw_events` flag: yield `(canonical, raw)` tuples
      - Register as `"openai-responses"` in `ProviderRegistry`
- [ ] Write unit tests for `OpenAIResponsesClient` (mocked SDK)
- [ ] Write integration tests for end-to-end streaming/non-streaming with mocked SDK
- [ ] Update `pyproject.toml` dependencies — add `openai>=1.55` as a core dependency (primary provider); future non-primary providers use optional extras
- [ ] Update `tinycua_sdk/agent/loop.py` to consume new canonical event schema

### Phase 3 — OpenAI Chat Completions API Provider (Future)

See separate spec and design for this phase.

- [ ] Implement `OpenAIChatClient` wrapping the `openai` PyPI SDK Chat Completions API (`/chat/completions`)
- [ ] Implement Chat Completions SSE normalizer
- [ ] Register as `"openai"` in `ProviderRegistry`

---

## Technical Decisions

1. **Decision**: Delegate to official provider SDKs instead of building HTTP-level clients.
   - **Reason**: Avoids reimplementing auth, retries, rate limiting, and format handling that SDKs already handle. SDKs are maintained by providers and stay in sync with API changes.
   - **Alternatives Considered**: httpx-based custom clients (current approach) — rejected because it requires per-provider HTTP-level implementation and is brittle when APIs change.

2. **Decision**: Provider registry as a singleton with runtime registration.
   - **Reason**: Enables lazy loading and plugin-style provider additions without modifying core code. Users can register custom providers.
   - **Alternatives Considered**: Hardcoded provider map — rejected because it limits extensibility.

3. **Decision**: Canonical event schema as TypedDicts (not Pydantic models).
   - **Reason**: Events flow through async iterators and are consumed as dicts. TypedDicts provide type-checking without overhead of model validation on every event. The Agent Loop already consumes dict-shaped events.
   - **Alternatives Considered**: Pydantic models — rejected due to per-event validation overhead in high-throughput streaming.

4. **Decision**: Raw pass-through as paired `(canonical_event, raw_event | None)` tuples.
   - **Reason**: Provides perfect 1:1 correlation between canonical and raw events without requiring consumers to manage two streams or filter event types. The Agent Loop ignores the raw slot (it only sees `canonical_event`), while consumers that need raw events can access them directly.
   - **Alternatives Considered**: (a) Interleaved single stream with type-based filtering — rejected because it loses the 1:1 correlation between canonical and raw events. (b) Two separate iterators — rejected because it requires the caller to coordinate two async generators in lockstep, which is error-prone.

5. **Decision**: No backward compatibility — breaking change accepted.
   - **Reason**: The internal architecture changes fundamentally (httpx → official SDK). Supporting a backward-compatibility shim would add maintenance burden and delay the migration. The old provider strings (`"openai"`, `"openai-compatible"`) and `OpenAICompatibleClient` are removed. Users must migrate to the new provider IDs.
   - **Alternatives Considered**: (a) Delegation shim with deprecation warning — rejected because it adds complexity without long-term benefit. (b) In-place modification — rejected because the architecture changes are too deep for incremental migration.

6. **Decision**: `raw_events` is a `chat()` parameter, not a separate method.
   - **Reason**: Keeps the interface surface small. Raw events are opt-in and only meaningful during streaming. A separate `raw_stream()` method would duplicate the streaming setup logic.
   - **Validation**: `raw_events=True` requires `stream=True`; calling `chat(stream=False, raw_events=True)` raises `ValueError("raw_events=True requires stream=True")`.

7. **Decision**: Provider naming — `openai-responses` for Responses API, `openai` reserved for future Chat Completions API.
   - **Reason**: The current httpx-based client uses `/responses`, so its SDK-backed replacement should be explicitly named for the Responses API. The `openai` ID is reserved for Chat Completions (the standard/most common OpenAI API). This avoids ambiguity and allows both to coexist when Chat Completions support is added.
   - **Alternatives Considered**: (a) Reuse `openai` for the Responses API — rejected because it would force a breaking rename when Chat Completions is added later. (b) Single `openai` client with auto-detection — rejected because it adds complexity and the two APIs have different request/response shapes.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Provider SDK API changes break the normalizer | Medium | High | Pin SDK major versions; add integration tests that mock SDK responses; document SDK version compatibility |
| Existing `OpenAICompatibleClient` users must migrate | High | High | Document migration path clearly in provider migration table; announce breaking change in release notes |
| Provider SDK dependency conflicts | Low | Medium | First-party provider (`openai`) is a core dependency; additional providers use optional extras (`pip install tinycua-sdk[other-provider]`); document dependency tree |
| Raw pass-through performance overhead (double serialization) | Low | Medium | Raw events are passed by reference (dict), not re-serialized; only pay the cost when `raw_events=True` |
| New canonical schema breaks the Agent Loop | Medium | High | Update the loop to consume new canonical event names (`content.delta`, `content.done`, `tool_call.*`); test the loop against the new schema |
| Provider registry singleton causes test pollution | Low | Medium | Provide `reset()` method for the registry; use per-test setup/teardown in test fixtures |

---

## Resolved Questions

1. **Provider naming: `openai-responses` vs `openai`**: The `/responses`-based client is named `openai-responses`. The `openai` ID is reserved for the future Chat Completions API provider. See Technical Decision #7.

2. **OpenAI SDK version**: Use `openai>=1.55` which supports the Responses API natively. The SDK-backed `OpenAIResponsesClient` wraps `openai.responses.create()` and `openai.responses.stream()` — matching the current `/responses` endpoint used by `OpenAICompatibleClient`.

3. **Non-streaming response normalization**: Both streaming and non-streaming paths normalize into the canonical format. Non-streaming returns `CanonicalResponse` dict; streaming yields `CanonicalEvent` subclasses.

4. **Optional extras vs. core dependency**: `openai` as a core dependency (primary provider), others as optional extras.

5. **Streaming event ordering**: Events are yielded in arrival order. The normalizer is synchronous per-event and does not buffer.

---

## References

- Spec: `./spec.md`
- Existing `LLMClient`: `tinycua_sdk/agent/llm_client.py`
- Existing `events.py`: `tinycua_sdk/agent/events.py`
- Existing `providers.py`: `tinycua_sdk/core/providers.py`
- Existing `LanguageModel`: `tinycua_sdk/agent/llm_model.py`
- Issue #39: SDK Feature Roadmap (https://github.com/VJyzCELERY/TINYCUA/issues/39)
