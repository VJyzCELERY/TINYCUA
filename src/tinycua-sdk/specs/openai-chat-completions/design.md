# Design Document: OpenAI Chat Completions Provider

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-05-19

---

## Overview

This design introduces an **OpenAIChatClient** — a new `LLMClient` subclass wrapping the OpenAI Chat Completions API via the official `openai` PyPI SDK (`client.chat.completions.create()`). The client includes a Chat Completions-specific SSE normalizer that converts delta-chunk streaming events into the canonical Responses-shaped event schema established in Stage 1, and registers as `"openai"` in the `ProviderRegistry`. The Stage 1 `"openai"` → `"openai-responses"` deprecation alias is removed. Only `tinycua-sdk` is affected; no new dependencies are required since `openai>=2.34,<3` is already declared.

---

## Architecture

### Component Overview

```
┌──────────────────────────────────────────────────────────┐
│                    Consumer Code                           │
│           (Agent Loop / Custom Loop / End User)            │
└──────────┬───────────────────────────────────────┬────────┘
           │ create_client(model_config)           │
           ▼                                       │
┌──────────────────────────┐                      │
│   ProviderRegistry       │                      │
│   create_client(...)     │                      │
│   (now has both          │                      │
│    "openai" and          │                      │
│    "openai-responses")   │                      │
└──────────┬───────────────┘                      │
           │ returns OpenAIChatClient(            │
           │   configured for Chat Completions)   │
           ▼                                      │
┌────────────────────────────────┐               │
│   OpenAIChatClient             │               │
│   (implements LLMClient ABC)   │               │
│   ┌────────────────────────┐   │               │
│   │   openai SDK            │   │  raw events   │
│   │   chat.completions      │──┼───────────────┼──▶ Raw SSE Stream
│   │   .create()             │   │               │
│   └───────────┬────────────┘   │               │
│               │ SDK chunks     │               │
│               ▼                │               │
│   ┌────────────────────────┐   │               │
│   │   ChatCompletions       │   │  canonical    │
│   │   Normalizer            │──┼───────────────┼──▶ Canonical Event Stream
│   │   (delta→accumulate→    │   │               │
│   │    canonical event)     │   │               │
│   └────────────────────────┘   │               │
└────────────────────────────────┘               │
                                                  ▼
                                         ┌────────────────┐
                                         │  Agent Loop     │
                                         │  (unchanged —   │
                                         │   consumes same │
                                         │   canonical     │
                                         │   events)       │
                                         └────────────────┘
```

### Key Difference from Responses API

The Chat Completions API streams **per-choice delta chunks** rather than named event types:

| Aspect | Responses API | Chat Completions API |
|--------|---------------|---------------------|
| Stream unit | Named events (`response.output_text.delta`, `response.function_call_arguments.delta`, etc.) | Per-choice delta chunks with nested `delta.content` and `delta.tool_calls[]` |
| Tool calls | Separate named events per phase | `delta.tool_calls` array — partial per chunk, accumulated by index |
| Content | Dedicated `response.output_text.delta` event | `choices[0].delta.content` (nullable string) |
| Lifecycle | `response.created`, `response.in_progress`, `response.completed`, etc. | Only `finish_reason` in terminal chunk; no intermediate lifecycle events |
| Reasoning | `response.reasoning.delta` events | No native reasoning events (handled via content prefix for o-series) |
| Usage | `response.usage` event | Only available in final chunk's `usage` field (or not at all in streaming) |

The normalizer must bridge this gap by:
- Accumulating `delta.content` fragments into `ContentDeltaEvent` / `ContentDoneEvent`
- Accumulating `delta.tool_calls` array entries by index into tool call events
- Synthesizing lifecycle events (`ResponseCreatedEvent`, `ResponseCompletedEvent`) from chunk metadata
- Extracting usage from the terminal chunk if present

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/agent/llm_client.py` | Extended — New class | `OpenAIChatClient` added; shared normalizer utilities reused |
| `tinycua_sdk/core/providers.py` | Modified | Register `"openai"` → `OpenAIChatClient`; remove deprecation alias |
| `tinycua_sdk/agent/__init__.py` | Modified | Export `OpenAIChatClient` |
| `tinycua_sdk/__init__.py` | No change | `LLMClient` already exported; consumers import provider-specific clients from subpackages |

---

## Data Model

### New Entities

```python
# ChoiceAccumulator: internal state for aggregating one stream choice
@dataclass
class ChoiceAccumulator:
    """Accumulates delta chunks for a single choice across stream iterations."""
    index: int
    content_parts: list[str] = field(default_factory=list)
    tool_calls: dict[int, ToolCallAccumulator] = field(default_factory=dict)
    finish_reason: str | None = None
    usage: dict | None = None


@dataclass
class ToolCallAccumulator:
    """Accumulates partial tool call data across stream chunks by index."""
    index: int
    id: str | None = None
    name: str | None = None
    arguments_parts: list[str] = field(default_factory=list)
```

### Schema Changes

- **`ProviderRegistry`**: No schema changes. Only runtime registration changes.
- **`LanguageModel`**: No changes — all Chat Completions parameters (model, temperature, max_tokens, etc.) are already supported.
- **Canonical Event Schema** (in `events.py`): No changes — the Chat Completions normalizer outputs the same event types.
- **`LLMResponse`**: No changes — Chat Completions non-streaming maps to the same fields.

---

## API / Interface Contracts

### OpenAIChatClient

```python
class OpenAIChatClient(LLMClient):
    """OpenAI Chat Completions API provider client.

    Wraps the official openai SDK's chat.completions.create() for both
    streaming and non-streaming modes. Normalizes Chat Completions delta
    chunks into the canonical Responses-shaped event schema.

    Registered as provider "openai" in the ProviderRegistry.
    """

    def __init__(self, model_config: LanguageModel) -> None:
        """Initialize the OpenAI Chat Completions client.

        Args:
            model_config: LanguageModel configuration with provider="openai".
                          Extracts api_key, base_url, model, temperature,
                          max_tokens, and other SDK parameters.
        """

    async def _chat_impl(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec] | None = None,
        stream: bool = False,
        raw_events: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMEvent] | AsyncIterator[tuple[LLMEvent | None, RawSseEvent | None]]:
        """Provider-specific implementation using client.chat.completions.create().

        Non-streaming: calls create() with stream=False, normalizes response to LLMResponse.
        Streaming: calls create(stream=True), wraps the chunk iterator in the normalizer.
        """

    async def close(self) -> None:
        """Close the underlying openai SDK client (HTTP session)."""
```

### ChatCompletionsNormalizer (module-level functions in `llm_client.py`)

```python
async def _normalize_chat_chunk(
    chunk: ChatCompletionChunk,
    accumulator: dict[int, ChoiceAccumulator],
) -> AsyncIterator[LLMEvent]:
    """Process one Chat Completions delta chunk and yield canonical events.

    Mutates the accumulator in-place across chunks. Yields zero or more
    canonical events per chunk:
    - ContentDeltaEvent for each content delta
    - ContentDoneEvent when a choice reaches a terminal state
    - ToolCallStartedEvent for each new tool call index
    - ToolCallArgumentsDeltaEvent for each argument delta
    - ToolCallArgumentsDoneEvent when arguments are complete
    - ToolCallReadyEvent when a tool call is fully accumulated
    - ResponseUsageEvent when usage data is available (terminal chunk)
    - ResponseCompletedEvent when finish_reason is present
    """
```

### Provider Registry Changes

```python
# In core/providers.py, _register_defaults():

def _register_defaults() -> None:
    """Register built-in providers."""
    from tinycua_sdk.agent.llm_client import OpenAIResponsesClient, OpenAIChatClient

    _provider_registry.register(
        "openai-responses",
        lambda cfg: OpenAIResponsesClient(cfg),
        ProviderInfo(...),
    )
    _provider_registry.register(
        "openai",
        lambda cfg: OpenAIChatClient(cfg),  # was: deprecated alias to openai-responses
        ProviderInfo(...),
    )
    # The old: _provider_registry.register("openai", _openai_deprecation_alias)
    # is REMOVED.
```

### Error Handling

| Error Case | Exception | Notes |
|------------|-----------|-------|
| Authentication failure | `ProviderAuthError` | Wrap `openai.AuthenticationError` |
| Rate limit / server error | `ProviderApiError(status_code, message)` | Wrap `openai.RateLimitError`, `openai.APIError`, etc. |
| Invalid request (bad model, etc.) | `ProviderApiError(400, message)` | Wrap `openai.BadRequestError` |
| SDK not installed | `ProviderApiError("openai SDK not available")` | Should not happen since it's a core dep |
| Empty stream | `ResponseCompletedEvent(finish_reason="stop")` | No content events emitted |
| `raw_events=True` with `stream=False` | `ValueError` | Inherited from `LLMClient.chat()` validation |

### Raw SSE Pass-Through

Same contract as Stage 1: when `raw_events=True`, the stream yields `(canonical, raw)` tuples. The raw slot contains the original `ChatCompletionChunk` SDK object (lossless). The canonical slot may be `None` for chunks that have no canonical equivalent (should not occur for Chat Completions since every delta chunk has a canonical mapping, but the contract supports it).

```python
stream = await client.chat(..., stream=True, raw_events=True)
async for canonical, raw in stream:
    # canonical: LLMEvent (e.g., ContentDeltaEvent)
    # raw: RawSseEvent(provider="openai", raw_event=ChatCompletionChunk(...))
```

---

## Implementation Phases

### Phase 2 — OpenAI Chat Completions Provider (This Milestone)

- [ ] **2.1**: Implement `ChoiceAccumulator` and `ToolCallAccumulator` dataclasses for per-choice chunk accumulation
- [ ] **2.2**: Implement `_normalize_chat_chunk()` — process a single Chat Completions delta chunk and yield canonical events
- [ ] **2.3**: Implement `OpenAIChatClient` class — `_chat_impl()` for non-streaming and streaming modes
- [ ] **2.4**: Register `"openai"` → `OpenAIChatClient` in `ProviderRegistry._register_defaults()`; remove the Stage 1 deprecation alias
- [ ] **2.5**: Update `tinycua_sdk/agent/__init__.py` to export `OpenAIChatClient`
- [ ] **2.6**: Write unit tests for:
      - Non-streaming normalization (mock `openai.resources.chat.completions.create`)
      - Streaming normalization (mock chunk iterator)
      - Tool call accumulation across chunks
      - Error translation
      - Raw pass-through paired tuples
- [ ] **2.7**: Write integration tests for:
      - Provider registry coexistence (`"openai"` + `"openai-responses"`)
      - Alias removal: `"openai"` no longer resolves to `"openai-responses"`
      - Existing `OpenAIResponsesClient` tests still pass
- [ ] **2.8**: Manual test against real OpenAI API with `provider="openai"` and `model="gpt-4o"`

---

## Technical Decisions

1. **Decision**: Implement `OpenAIChatClient` in the same file (`llm_client.py`) as `OpenAIResponsesClient`.
   - **Reason**: Both share the same module-level helpers (`_translate_tools`, `_translate_messages`, `_build_payload`). Keeping them in one file avoids circular imports and allows code reuse.
   - **Alternatives Considered**: Separate `providers/openai_chat/` package — rejected because it would duplicate shared translation logic and introduce import complexity.

2. **Decision**: Single-choice (`n=1`) support for MVP, no multi-choice normalization.
   - **Reason**: The canonical event schema assumes a single response stream. Multi-choice would require a different normalization strategy (interleaved content deltas from multiple choices). No current consumer needs multi-choice.
   - **Future**: If multi-choice support is needed, the normalizer would track multiple `ChoiceAccumulator` instances and tag events with a `choice_index` field.

3. **Decision**: Accumulate tool call chunks by index using `ToolCallAccumulator`, emit events incrementally.
   - **Reason**: Chat Completions streams tool calls as `delta.tool_calls[]` arrays with partial data per chunk (e.g., first chunk has `id` and `name`, subsequent chunks have `function.arguments` deltas). Accumulating by index allows emitting progress events (`ToolCallArgumentsDeltaEvent`) while still producing a complete `ToolCallReadyEvent`.
   - **Alternatives Considered**: Buffer all tool calls until stream end — rejected because it defeats the purpose of streaming (users can't show progressive tool call UI).

4. **Decision**: Synthesize `ResponseCreatedEvent` from first chunk metadata, `ResponseCompletedEvent` from terminal `finish_reason`.
   - **Reason**: Chat Completions does not emit lifecycle events like the Responses API. The normalizer synthesizes these from available chunk data to maintain canonical event contract compatibility.
   - **Note**: `ResponseInProgressEvent` and `ResponseCancelledEvent` are not emitted by Chat Completions (no equivalent concept). The normalizer will not synthesize them — consumers that need them must use the Responses API.

5. **Decision**: Remove the `"openai"` deprecation alias entirely, not just override it.
   - **Reason**: The Stage 1 alias registered `"openai"` as a compatibility shim to `"openai-responses"`. Now that Chat Completions has a real provider, the alias must be removed — not just overridden — to avoid any residual behavior (e.g., warning messages, backward-compat logic).
   - **Migration**: Users who were using `provider="openai"` during Stage 1 to get Responses API behavior must switch to `provider="openai-responses"` explicitly, or switch to `provider="openai"` for Chat Completions behavior.

6. **Decision**: Extend the existing `_normalize_responses_event`-style pattern with a new `_normalize_chat_chunk` rather than modifying the Responses normalizer.
   - **Reason**: The two APIs have fundamentally different streaming models (named events vs. delta chunks). A single normalizer that tries to handle both would be complex and hard to test. Separate normalizers with a shared interface (both yield `AsyncIterator[LLMEvent]`) is cleaner.
   - **Shared Code**: Both normalizers use the same `_yield_events()`, `_translate_tools()`, `_translate_messages()`, and `_build_payload()` helpers already in `llm_client.py`.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Chat Completions streaming chunks may change format with SDK upgrades | Low | Medium | Pin `openai` major version; add integration tests with known chunk shapes |
| Tool call accumulation across chunks may miss edge cases (e.g., empty `tool_calls` array in some chunks) | Medium | Medium | Add defensive checks; emit partial tool call events even if not all fields are populated; unit test all chunk patterns |
| Existing code using `provider="openai"` silently switches from Responses API to Chat Completions | Medium | High | Document the breaking change in release notes; the Stage 1 spec already warned this would happen; users should have migrated to `"openai-responses"` |
| Chat Completions has no native reasoning events — o-series reasoning appears as content prefix | Medium | Low | The existing `strip_thinking` logic in `LanguageModel` already handles this at the model config level |
| Multiple choices (`n>1`) not supported — may surprise users who set `n=2` | Low | Low | Document single-choice limitation; the normalizer ignores `choices[1+]` |

---

## Open Questions

1. **Should we support `response_format` for structured outputs?**
   - **Status**: Decided
   - **Decision**: Yes — the `LanguageModel.response_format` field is already passed through to the SDK via `_build_payload`. No additional work needed.

2. **Should we emit `ResponseInProgressEvent` for Chat Completions?**
   - **Status**: Decided
   - **Decision**: No — Chat Completions has no in-progress lifecycle event. The normalizer emits `ResponseCreatedEvent` on first chunk and `ResponseCompletedEvent` on terminal chunk. `ResponseInProgressEvent` is Responses API-specific.

---

## References

- Spec: `./spec.md`
- Issue #39: SDK Feature Roadmap (https://github.com/VJyzCELERY/TINYCUA/issues/39)
- Stage 1 Design: `../llm-client-interface/design.md`
- Stage 1 Spec: `../llm-client-interface/spec.md`
- `OpenAIResponsesClient`: `tinycua_sdk/agent/llm_client.py` (line 599)
- Canonical Event Schema: `tinycua_sdk/agent/events.py`
- Provider Registry: `tinycua_sdk/core/providers.py`
- `LLMClient` ABC: `tinycua_sdk/agent/llm_client.py` (line 507)
