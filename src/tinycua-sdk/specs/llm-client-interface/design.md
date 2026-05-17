# Design Document: Unified LLM Client Interface with Swappable Providers

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-05-17

---

## Overview

This design introduces a unified **Agent + LLM Client** architecture for the TINYCUA SDK. Instead of rebuilding HTTP-level clients for each provider, we delegate to each provider's official Python SDK (e.g., `openai` PyPI) and wrap them behind a common `LLMClient` abstract base class. Each provider client includes an **SSE normalizer** that converts provider-specific streaming events into a canonical format consumed by the Agent Loop, while simultaneously exposing a **raw SSE pass-through** for consumers that need provider-native events. A **provider registry** maps configuration-driven provider identifiers to concrete client implementations, enabling provider switching via `LanguageModel.provider` alone.

The affected subproject is `tinycua-sdk`. The existing `OpenAICompatibleClient` (httpx-based, `/responses` endpoint) will be replaced by a properly normalized **OpenAI Responses API** provider with ID `openai-responses`, wrapping the `openai` PyPI SDK's Responses API. The `openai` provider ID is reserved for a future **OpenAI Chat Completions API** provider. A backward-compatibility shim deprecates `OpenAICompatibleClient` while keeping it importable.

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
| `tinycua_sdk/models/response.py` | Modified — StreamEvent | May add raw event fields |
| `tinycua_sdk/agent/loop.py` | Unchanged | Continues consuming canonical events |
| `tinycua_sdk/providers/openai_responses/` | New | OpenAI Responses API provider client + normalizer; registered as `"openai-responses"` |
| `tinycua_sdk/providers/openai_chat/` | New | OpenAI Chat Completions API provider client (future phase, ID `"openai"`) |


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
    id: str
    name: str

class ToolCallArgumentsDeltaEvent(CanonicalEvent):
    """Partial tool call arguments."""
    type: Literal["tool_call.arguments.delta"]
    id: str
    arguments: str

class ToolCallArgumentsDoneEvent(CanonicalEvent):
    """Tool call arguments complete."""
    type: Literal["tool_call.arguments.done"]
    id: str
    arguments: str

class ResponseUsageEvent(CanonicalEvent):
    """Token usage information."""
    type: Literal["response.usage"]
    usage: dict

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
    tool_calls: list[dict] | None          # List of {id, call_id, name, arguments}
    usage: dict | None                     # Token usage {input_tokens, output_tokens, ...}
    finish_reason: str | None              # "stop", "tool_calls", "length", etc.
    model: str                             # Model name that generated the response
```

```python
# ──────────────────────────────────────────────
# Raw pass-through event (paired with canonical)
# ──────────────────────────────────────────────

class RawSseEvent(TypedDict):
    """Raw provider-native SSE event wrapper.

    This is NOT a CanonicalEvent — it is yielded alongside the canonical
    event as a separate element in the (canonical, raw) tuple when
    raw_events=True.
    """
    provider: str       # e.g., "openai-responses"
    raw_event: dict     # unmodified provider-native event dict
```

```python
# ──────────────────────────────────────────────
# Provider Registry
# ──────────────────────────────────────────────

@dataclass
class ProviderInfo:
    """Registered provider metadata."""
    id: str                                    # canonical identifier, e.g. "openai-responses"
    client_class: type[LLMClient]              # concrete client implementation
    description: str                           # human-readable
    supported_models: list[str] | None = None  # optional model filter
```

### Schema Changes

- **`LanguageModel`**: No breaking changes. New `provider`-specific fields may be added as optional Pydantic fields (e.g., `openai_chat_params`).
- **`StreamEvent`** (in `models/response.py`): No changes needed — raw pass-through is handled via the paired tuple API, not by embedding raw events into the canonical stream.
- **`events.py`**: Existing TypedDicts consolidated into the canonical schema above. Deprecated aliases retained for backward compatibility.

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
    ) -> CanonicalResponse | AsyncIterator[CanonicalEvent] | AsyncIterator[tuple[CanonicalEvent, RawSseEvent | None]]:
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
    """Registry of available LLM provider clients."""

    def register(self, provider_id: str, client_class: type[LLMClient]) -> None:
        """Register a new provider client."""

    def get_client(self, provider_id: str) -> LLMClient:
        """Get a provider client instance by provider ID.

        Raises:
            ProviderNotSupportedError: If provider_id is not registered.
        """

    def list_providers(self) -> list[ProviderInfo]:
        """List all registered providers with metadata."""

    def is_supported(self, provider_id: str) -> bool:
        """Check if a provider is registered."""

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
| Streaming not supported | `ProviderApiError("Provider does not support streaming")` | Only if provider has no streaming capability |
| SDK incompatibility | `ImportError` or `ProviderApiError` | If SDK is missing or wrong version |

### Raw SSE Pass-Through Contract

When `raw_events=True` and `stream=True`, the async iterator yields paired `(canonical_event, raw_event)` tuples. Every canonical event is paired with its corresponding provider-native event when one exists. Synthetic canonical events (e.g., `response.completed` that the normalizer synthesizes without a raw counterpart) have `None` in the raw slot.

```python
async for canonical, raw in client.chat(..., stream=True, raw_events=True):
    # canonical is always a CanonicalEvent dict — process normally
    if raw is not None:
        # raw is a RawSseEvent dict with provider + raw_event fields
        provider = raw["provider"]   # e.g., "openai-responses"
        raw_data = raw["raw_event"]  # unmodified provider-native event
```

Consumers that want **only** raw events can filter via the canonical event type or the raw slot:

```python
async for canonical, raw in client.chat(..., stream=True, raw_events=True):
    if raw is not None:
        process_raw(raw["raw_event"])
```

---

## Implementation Phases

### Phase 1 — Foundation (This Milestone)

- [ ] **1.1**: Formalize the canonical SSE event schema in `events.py` — define all canonical event TypedDicts, `CanonicalResponse`, and `RawSseEvent`; consolidate existing TypedDicts with backward-compat aliases
- [ ] **1.2**: Refactor `LLMClient` ABC — update `chat()` return type to `CanonicalResponse` (non-streaming) and document canonical event contract in docstring; add `raw_events` parameter
- [ ] **1.3**: Implement `ProviderRegistry` in `core/providers.py` — register, get_client, list, is_supported
- [ ] **1.4**: Implement `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` exception classes in `core/exceptions.py`
- [ ] **1.5**: Build `OpenAIResponsesClient` wrapping the `openai` PyPI SDK Responses API:
      - `chat()` non-streaming via `openai.responses.create()` → normalize SDK response to `CanonicalResponse`
      - `chat()` streaming via `openai.responses.stream()` with SSE normalizer → normalize raw stream events to canonical schema
      - Extract and formalize the existing `_normalize_responses_event()` into the per-provider normalizer
      - Raw pass-through via `raw_events` flag: yield `(canonical, raw)` tuples
      - Register as `"openai-responses"` in `ProviderRegistry`
- [ ] **1.6**: Add backward-compatibility shim — `OpenAICompatibleClient` delegates to `OpenAIResponsesClient` with deprecation warning
- [ ] **1.7**: Write unit tests for:
      - Canonical event schema validation (`CanonicalEvent` subclasses, `CanonicalResponse`, `RawSseEvent`)
      - `ProviderRegistry` behavior (register, resolve, unsupported provider errors)
      - `OpenAIResponsesClient` non-streaming response normalization (mocked SDK)
      - `OpenAIResponsesClient` streaming SSE normalization (mocked SDK)
      - Responses API normalizer: map each raw Responses API event to canonical equivalent
      - Raw pass-through: verify `(canonical, raw)` tuple integrity
      - Error cases: auth failure, connection error, SDK import errors
- [ ] **1.8**: Write integration tests for:
      - End-to-end non-streaming with mocked OpenAI Responses API SDK
      - End-to-end streaming with mocked OpenAI Responses API SDK
      - Provider switching via `LanguageModel.provider` (`"openai-responses"`)
      - Backward compatibility: existing `OpenAICompatibleClient` API still works via delegation shim
- [ ] **1.9**: Update `pyproject.toml` dependencies — add `openai>=1.55` SDK dependency

### Phase 2 — OpenAI Chat Completions API Provider (Post-MVP)

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

5. **Decision**: Backward compatibility via delegation shim, not inheritance.
   - **Reason**: `OpenAICompatibleClient` is used directly in tests and user code. A deprecation warning guides migration without breaking existing callers.
   - **Alternatives Considered**: In-place modification — rejected because the internal architecture changes fundamentally (httpx → SDK).

6. **Decision**: `raw_events` is a `chat()` parameter, not a separate method.
   - **Reason**: Keeps the interface surface small. Raw events are opt-in and only meaningful during streaming. A separate `raw_stream()` method would duplicate the streaming setup logic.

7. **Decision**: Provider naming — `openai-responses` for Responses API, `openai` reserved for future Chat Completions API.
   - **Reason**: The current httpx-based client uses `/responses`, so its SDK-backed replacement should be explicitly named for the Responses API. The `openai` ID is reserved for Chat Completions (the standard/most common OpenAI API). This avoids ambiguity and allows both to coexist when Chat Completions support is added.
   - **Alternatives Considered**: (a) Reuse `openai` for the Responses API — rejected because it would force a breaking rename when Chat Completions is added later. (b) Single `openai` client with auto-detection — rejected because it adds complexity and the two APIs have different request/response shapes.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Provider SDK API changes break the normalizer | Medium | High | Pin SDK major versions; add integration tests that mock SDK responses; document SDK version compatibility |
| Existing `OpenAICompatibleClient` users silently break | Low | High | Deprecation shim with warning; keep old class importable for one release cycle; announce migration path |
| Provider SDK dependency conflicts | Low | Medium | Isolate SDKs as optional extras (`pip install tinycua-sdk[openai]`); document dependency tree |
| Raw pass-through performance overhead (double serialization) | Low | Medium | Raw events are passed by reference (dict), not re-serialized; only pay the cost when `raw_events=True` |
| New canonical schema breaks the Agent Loop | Medium | High | Map existing event types to new canonical names with backward-compat aliases; test the loop against both old and new event formats |
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
