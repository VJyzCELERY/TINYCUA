# Design Document: Unified LLM Client Interface with Swappable Providers

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-05-17

---

## Overview

This design introduces a unified **Agent + LLM Client** architecture for the TINYCUA SDK. Instead of rebuilding HTTP-level clients for each provider, we delegate to each provider's official Python SDK (e.g., `openai` PyPI) and wrap them behind a common `LLMClient` abstract base class. Each provider client includes an **SSE normalizer** that converts provider-specific streaming events into a canonical format consumed by the Agent Loop, while simultaneously exposing a **raw SSE pass-through** for consumers that need provider-native events. A **provider registry** maps configuration-driven provider identifiers to concrete client implementations, enabling provider switching via `LanguageModel.provider` alone.

The affected subproject is `tinycua-sdk`. The existing `OpenAICompatibleClient` (httpx-based, `/responses` endpoint) will be **removed in Phase 2** and replaced by a properly normalized **OpenAI Responses API** provider with ID `openai-responses`, wrapping the `openai` PyPI SDK's Responses API. This is a **breaking change**: old provider strings (`"openai"`, `"openai-compatible"`) will no longer be supported after Phase 2. The `openai` provider ID is reserved for a future **OpenAI Chat Completions API** provider. No backward-compatibility shim is provided.

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       Consumer Code                          │
│              (Agent Loop / Custom Loop / End User)            │
└──────────┬──────────────────────────────────────┬────────────┘
           │ create_client(model_config)          │
           ▼                                      │
┌──────────────────────────┐                     │
│   ProviderRegistry       │                     │
│   create_client(...)     │                     │
│   register(...)          │                     │
│   list_providers()       │                     │
└──────────┬───────────────┘                     │
           │ returns LLMClient-conforming        │
           │ provider client instance            │
           ▼                                     │
┌─────────────────────────────┐                  │
│  Provider Client Instance   │                  │
│  (implements LLMClient ABC) │                  │
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

### Consumer Entrypoint / Agent Loop Contract

The Agent Loop interacts with the LLM provider system through a universal factory — it does NOT need to know about provider resolution internals.

**Contract**:

1. **Universal entrypoint**: The Agent Loop calls `ProviderRegistry.create_client(model_config)` once per request. This method uses `model_config.provider` to select the correct registered provider factory, instantiates the provider client, and returns an `LLMClient`-conforming instance ready for use.

2. **One method to call**: After resolving a client, the Loop calls `client.chat(messages, tools, stream, raw_events)` on the returned instance. The Loop consumes canonical events from the returned async iterator (or a `CanonicalResponse` for non-streaming). It does NOT inspect provider-specific response types. The provider client uses the configuration that was bound during `create_client()` — `model_config` is not passed to `chat()` because the provider, model, API keys, and other settings are already resolved at construction time.

3. **Provider selection is not the Loop's concern**: The Loop never calls `ProviderRegistry.create_client()` with hardcoded provider strings, never switches providers mid-stream, and never inspects provider identifiers to branch behavior.

4. **Client lifecycle**: The Loop calls `client.close()` when the provider client is no longer needed. The `ProviderRegistry` does not manage client lifecycle — each resolved client is independent.

5. **Acceptance scenario alignment**: Acceptance scenarios call `chat()` on the provider client instance returned by `ProviderRegistry.create_client()`. The provider client already has the correct provider normalizer bound from its construction configuration — no per-call provider selection occurs.

**Design implications**:
- The `LLMClient` ABC defines the interface that all provider clients implement.
- The `ProviderRegistry` is the universal factory — it is NOT part of the `LLMClient` ABC.
- **Bound-client model**: Provider clients receive the full `LanguageModel` object during construction (via the factory) and extract provider-specific settings from it (provider identity, model name, API keys, base URLs, timeouts, etc.). The `chat()` method does NOT accept a `model_config` parameter — configuration is bound once at construction time. To use a different configuration, callers resolve a new client via `ProviderRegistry.create_client()`. This avoids duplicated configuration sources and ensures provider identity cannot diverge between construction and per-request usage.

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
- `LanguageModel.provider` validation in Phase 1 accepts the existing provider strings (`"openai"`, `"openai-compatible"`) alongside `"openai-responses"` for backward compatibility. In Phase 2, validation will accept only registered provider IDs.
- The old `OpenAICompatibleClient` class and its httpx-based implementation will be **removed in Phase 2** — no deprecation shim, no backward-compatibility layer once removed.
- Existing `StreamEvent` usage should be migrated to the canonical `CanonicalEvent` schema. The `StreamEvent` model itself remains unchanged (raw pass-through is via the paired tuple API, not by modifying `StreamEvent`).
- The `events.py` TypedDicts are consolidated into the new canonical schema — old TypedDicts are removed.

---

## Data Model

### New Entities

```python
# ──────────────────────────────────────────────
# Canonical SSE Event Schema (TypedDicts)
# ──────────────────────────────────────────────

# Each concrete event is defined as its own TypedDict with a type: Literal[...]
# field. There is no base TypedDict with type: str — type checkers reject
# TypedDict field overrides since they are invariant. Instead, CanonicalEvent
# is defined as a union type alias below.

class ContentDeltaEvent(TypedDict):
    """Text content delta from the LLM."""
    type: Literal["content.delta"]
    delta: str
    index: int

class ContentDoneEvent(TypedDict):
    """Text content block completed."""
    type: Literal["content.done"]
    index: int

class ToolCallStartedEvent(TypedDict):
    """New tool call initiated."""
    type: Literal["tool_call.started"]
    id: str                    # Provider output item ID (correlates deltas to a single call)
    call_id: str               # Provider tool call ID — used when submitting tool results
    name: str

class ToolCallArgumentsDeltaEvent(TypedDict):
    """Partial tool call arguments."""
    type: Literal["tool_call.arguments.delta"]
    id: str                    # Provider output item ID (matches ToolCallStartedEvent.id)
    arguments: str

class ToolCallArgumentsDoneEvent(TypedDict):
    """Tool call arguments complete — execution-ready metadata included."""
    type: Literal["tool_call.arguments.done"]
    id: str                    # Provider output item ID
    call_id: str               # Provider tool call ID — used when submitting tool results
    name: str                  # Tool name (copied from the started event for convenience)
    arguments: str             # Final complete JSON arguments

class ToolCallReadyEvent(TypedDict):
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

```

```python
class CanonicalUsage(TypedDict):
    """Provider-agnostic token usage schema.

    Provider normalizers MUST map their SDK's usage fields into these
    canonical field names. All keys are present; unavailable values are `None`.
    This ensures consumers can always access the three standard usage fields
    without needing provider-specific defensive code.
    """
    input_tokens: int | None                # Tokens consumed by the prompt
    output_tokens: int | None               # Tokens generated in the response
    total_tokens: int | None                # input_tokens + output_tokens (when available)

class ResponseUsageEvent(TypedDict):
    """Token usage information."""
    type: Literal["response.usage"]
    usage: CanonicalUsage

class ResponseCompletedEvent(TypedDict):
    """Stream completed successfully."""
    type: Literal["response.completed"]
    finish_reason: str

class ResponseFailedEvent(TypedDict):
    """Stream failed with error."""
    type: Literal["response.failed"]
    error: dict

# CanonicalEvent is a discriminated union of all concrete event types.
# Consumers can narrow by checking event["type"] against a Literal value.
CanonicalEvent: TypeAlias = (
    ContentDeltaEvent
    | ContentDoneEvent
    | ToolCallStartedEvent
    | ToolCallArgumentsDeltaEvent
    | ToolCallArgumentsDoneEvent
    | ToolCallReadyEvent
    | ResponseUsageEvent
    | ResponseCompletedEvent
    | ResponseFailedEvent
)

### Canonical Input Types (Request Contract)

In addition to the canonical output event schema, the system defines canonical input types so the Agent Loop communicates with every provider using a uniform message/tool format. This eliminates the need for the loop to construct provider-specific dict shapes.

```python
# ──────────────────────────────────────────────
# Canonical Input Schema (TypedDicts)
# ──────────────────────────────────────────────
# These types define the contract for messages sent TO the provider.
# Provider clients translate these canonical types into their SDK's
# native request format.

class SystemMessage(TypedDict):
    """System-level instruction."""
    role: Literal["system"]
    content: str

class UserMessage(TypedDict):
    """User input."""
    role: Literal["user"]
    content: str

class AssistantMessage(TypedDict):
    """Model assistant response (used for multi-turn context)."""
    role: Literal["assistant"]
    content: str | None

class ToolResultMessage(TypedDict):
    """Tool execution result submitted back to the model.

    The ``call_id`` field MUST carry the value from the corresponding
    ``tool_call.ready.call_id`` received in the canonical output event.
    Provider clients map this to their SDK's continuation mechanism
    (e.g., ``previous_response_id`` + ``function_call_output`` for OpenAI
    Responses API).
    """
    role: Literal["tool_result"]
    call_id: str            # Copied from tool_call.ready.call_id
    content: str            # The tool's output (stringified if necessary)

CanonicalMessage: TypeAlias = (
    SystemMessage
    | UserMessage
    | AssistantMessage
    | ToolResultMessage
)

class CanonicalToolSpec(TypedDict):
    """A tool/function specification in provider-neutral form.

    Provider clients translate this into the SDK's tool definition
    format (e.g., OpenAI ``function`` tool type).
    """
    name: str
    description: str
    parameters: dict  # JSON Schema object
```

### Tool Result Continuation Contract

After the Agent Loop receives a ``tool_call.ready`` event, it executes the named tool and must submit the result back to the provider to continue the model interaction. The continuation contract is designed so the loop never touches provider-specific fields:

1. **Submit via message list**: The Agent Loop constructs a ``ToolResultMessage`` from the tool output and appends it to the ``messages`` list passed to the next ``chat()`` call. The ``call_id`` field MUST be copied from the ``tool_call.ready.call_id`` that triggered execution.

2. **Provider client owns continuation state**: Each provider client is responsible for translating the appended ``ToolResultMessage`` into the provider SDK's continuation mechanism. For example, the OpenAI Responses API provider client maps ``call_id`` + ``content`` to ``function_call_output`` and uses ``previous_response_id`` internally — the Agent Loop never manages these fields.

3. **Multi-turn tool loop**: The Agent Loop iterates:
   - Call ``chat(messages, tools)`` → consume canonical events
   - On ``tool_call.ready`` → execute tool → append ``ToolResultMessage`` to messages
   - Call ``chat(messages, tools)`` again with updated messages (provider client manages continuation internally)
   - Repeat until no more ``tool_call.ready`` events or a ``response.completed`` is received

4. **No separate ``continue_with_tools()`` method**: Continuation is represented entirely by appending canonical tool-result messages to the message list. This keeps the ``LLMClient`` interface simple — there is only one ``chat()`` method, and the loop builds longer message histories across turns.

5. **Validation**: Provider normalizer tests MUST verify that a ``ToolResultMessage`` with the correct ``call_id`` is correctly translated into the provider SDK's expected continuation format.

```python
# Example Agent Loop tool-loop pseudocode using canonical types:
messages: list[CanonicalMessage] = [UserMessage(role="user", content="What is the weather?")]
tools: list[CanonicalToolSpec] = [weather_tool]

while True:
    stream = await client.chat(messages, tools, stream=True)
    async for event in stream:
        if event["type"] == "tool_call.ready":
            result = await execute_tool(event["name"], event["arguments"])
            # Append tool result — provider client handles SDK-specific
            # continuation (previous_response_id, etc.) internally
            messages.append(ToolResultMessage(
                role="tool_result",
                call_id=event["call_id"],
                content=result,
            ))
        elif event["type"] == "response.completed":
            return  # Interaction complete
```

### Tool-Call Streaming State Machine

The canonical tool-call event stream follows a normative state machine to ensure provider-normalizer implementations produce consistent events and Agent Loop consumers react only to the correct execution trigger.

**Rules**:

1. **Progress events (informational)**: Providers MAY emit `tool_call.started` and zero or more `tool_call.arguments.delta` events to indicate incremental progress (streaming arguments). These events carry partial metadata and are intended for progress indicators or UI updates.

2. **Execution trigger**: Providers MUST emit exactly one `tool_call.ready` event per executable tool call. The `tool_call.ready` event carries all execution-ready metadata (`id`, `call_id`, `name`, `arguments`) in a single atomic event.

3. **Agent Loop consumption**: The Agent Loop MUST execute tools only from `tool_call.ready` events. It MUST NOT execute tools from `tool_call.arguments.done` or from state accumulated from `tool_call.arguments.delta` events — doing so risks duplicate execution.

4. **`tool_call.arguments.done` role**: The `tool_call.arguments.done` event is an informational milestone emitted before the corresponding `tool_call.ready` to signal argument collection is complete. It is NOT an execution trigger. Provider normalizers that emit `tool_call.arguments.done` MUST always emit the corresponding `tool_call.ready` immediately afterward.

5. **Normalizer contract**: Each provider normalizer must emit exactly one execution trigger event (`tool_call.ready`) per executable tool call detected in the provider's raw stream. Normalizer tests MUST assert this count.

**Event sequencing example**:
```
tool_call.started      (id="item_1", call_id="call_abc", name="get_weather")
tool_call.arguments.delta (id="item_1", arguments='{"location": "')
tool_call.arguments.delta (id="item_1", arguments='{"location": "Tokyo"}')
tool_call.arguments.done  (id="item_1", call_id="call_abc", name="get_weather", arguments='{"location": "Tokyo"}')
tool_call.ready           (id="item_1", call_id="call_abc", name="get_weather", arguments='{"location": "Tokyo"}')
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
        messages: list[CanonicalMessage],
        tools: list[CanonicalToolSpec] | None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> CanonicalResponse | AsyncIterator[CanonicalEvent] | AsyncIterator[tuple[CanonicalEvent | None, RawSseEvent | None]]:
        """Send a chat completion request using the provider configuration
        that was bound during client construction (via
        `ProviderRegistry.create_client`). Model, API keys, base URLs, and
        other provider settings are resolved once at construction time.

        Args:
            messages: List of canonical messages (system, user, assistant,
                      tool_result). Provider clients translate these into the
                      provider SDK's native message format internally.
            tools: Optional list of canonical tool specifications.
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
            AsyncIterator[tuple[CanonicalEvent | None, RawSseEvent | None]] when
            stream=True, raw_events=True.

        Raises:
            ProviderAuthError: If credentials are missing or invalid.
            ProviderApiError: For provider SDK-level errors.
        """

    @abstractmethod
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

## Planning Scope

This design document, together with the companion spec, defines the contract for the **immediate next implementation plan**. The sections below clarify what is in scope and what is deferred.

### In Scope (Next Implementation Plan)

| Area | Details |
|------|---------|
| Canonical SSE event schema | All concrete event TypedDicts with `CanonicalEvent` discriminated union type alias, `CanonicalResponse`, `RawSseEvent`, `CanonicalUsage` |
| Canonical input types | `CanonicalMessage` (discriminated union of `SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolResultMessage`), `CanonicalToolSpec` |
| Tool result continuation contract | Documentation of the append-to-messages pattern for tool-result submission; provider clients own SDK-specific continuation state (e.g., `previous_response_id`) |
| `LLMClient` ABC | Refactored abstract base with `chat()` and `close()` contracts; updated return types and canonical input types |
| `ProviderRegistry` | Singleton registry with `register()`, `create_client()`, `list_providers()`, `is_supported()`, `reset()` |
| Error classes | `ProviderNotSupportedError`, `ProviderAuthError`, `ProviderApiError` |
| Core exception module | `tinycua_sdk/core/exceptions.py` |
| Unit tests | Schema validation, registry behavior, error cases (unit-level, no SDK mocking) |
| Integration tests | Provider switching via `LanguageModel.provider` (compile-time contract tests) |

**Key constraint**: Phase 1 is **provider-agnostic**. No provider SDK integration (no `openai` PyPI dependency, no `OpenAIResponsesClient`, no per-provider normalizer). The registry, schema, and ABC must compile and pass tests without any provider SDK installed.

### Out of Scope (Deferred to Future Phases)

| Area | Phase | Details |
|------|-------|---------|
| `OpenAIResponsesClient` | Phase 2 | OpenAI Responses API provider client and normalizer wrapping `openai` PyPI SDK |
| Agent Loop migration | Phase 2 | Update `tinycua_sdk/agent/loop.py` to consume new canonical event schema |
| Raw pass-through implementation | Phase 2 | Per-provider `raw_events` behavior (type contract is defined in Phase 1; runtime behavior comes with provider implementations) |
| `OpenAIChatClient` | Phase 3 | OpenAI Chat Completions API provider client |

The PR body references Phase 2 items (OpenAI Responses provider, loop migration) as future milestones, consistent with this scope. The success criteria in the spec that mention provider tests are aspirational for the full roadmap; the immediate Phase 1 success criteria are limited to schema, registry, contract, and compile-time tests.

---

## Implementation Phases

> **Note**: Each phase below is an independent implementation stage with its own spec and design document. This design document covers planning for Phase 1 (Foundation) as defined in **Planning Scope** above. Subsequent phases will have separate specs and designs.

### Phase 1 — Foundation: Interface, Schema, Registry (This Milestone)

This phase establishes the core abstractions and is **provider-agnostic** — no provider SDK integrations.

- [ ] **1.1**: Formalize the canonical SSE event schema in `events.py` — define all canonical event TypedDicts, `CanonicalResponse`, and `RawSseEvent`; replace existing TypedDicts with new canonical schema; define canonical input types (`CanonicalMessage`, `CanonicalToolSpec`, `ToolResultMessage`)
- [ ] **1.2**: Refactor `LLMClient` ABC — update `chat()` parameter types to `list[CanonicalMessage]` and `list[CanonicalToolSpec] | None`, update return type to `CanonicalResponse` (non-streaming), and document canonical event contract in docstring; add `raw_events` parameter
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
| Raw pass-through performance overhead (double serialization) | Low | Medium | Raw provider SDK event objects are passed by reference inside `RawSseEvent.raw_event`; they are not converted or re-serialized; only pay the cost when `raw_events=True` |
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
