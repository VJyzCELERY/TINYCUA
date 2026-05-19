# Feature Specification: OpenAI Chat Completions Provider

**Status**: Complete
**Created**: 2026-05-19
**Last Updated**: 2026-05-19
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Extend the TINYCUA SDK with an **OpenAI Chat Completions API** provider client so that:
- Users can interact with OpenAI's `/chat/completions` endpoint through the same `LLMClient` interface established in Stage 1
- Chat Completions streaming events (delta-based content, tool calls) are normalized into the canonical Responses-shaped event schema
- Raw SSE events from the Chat Completions API are exposed as a pass-through stream
- The provider is registered as `"openai"` (the identifier reserved in Stage 1) in the `ProviderRegistry`
- The Stage 1 `"openai"` → `"openai-responses"` deprecation alias is removed so `"openai"` resolves to the Chat Completions client

### Gaps

- The SDK currently supports only the OpenAI Responses API (`openai-responses` provider)
- The `"openai"` provider identifier is occupied by a Stage 1 deprecation alias pointing to `openai-responses`
- No Chat Completions SSE normalizer exists — the canonical event normalizer in `llm_client.py` is Responses-specific (`_normalize_responses_event`)
- Chat Completions uses a different streaming format (per-choice delta chunks with `tool_calls` arrays) that does not map 1:1 to Responses API events

### Non-Goals

- Rebuilding the `openai` PyPI SDK (we delegate to the existing SDK)
- Adding new provider types beyond OpenAI Chat Completions (Anthropic, Google, etc. are future work)
- Modifying the `LLMClient` ABC or canonical event schema (Stage 2 fits into the existing contracts)
- Changing the Agent Loop (`loop.py`) — the Chat Completions normalizer produces the same canonical events the loop already consumes
- Streaming-only features — non-streaming `chat()` is fully supported and returns the same `LLMResponse` shape
- Supporting Azure OpenAI or other OpenAI-compatible endpoints — the Chat Completions client uses the `openai` SDK's existing `base_url` parameter which already supports custom endpoints; this is inherited, not a new feature

### Constraints

- Must use the official `openai` PyPI SDK (`client.chat.completions.create()`) — no HTTP-level client
- Must normalize Chat Completions SSE events into the existing canonical event schema (Responses-shaped TypedDicts)
- Must support raw event pass-through via the same `(canonical, raw)` paired tuple mechanism
- Must remove the Stage 1 `"openai"` deprecation alias from `ProviderRegistry` and register the Chat Completions client under `"openai"` instead
- The `"openai-responses"` provider must continue to work unchanged
- Existing tool-call state machine rules (one `tool_call.ready` per executable call) apply unchanged
- Must handle Chat Completions-specific edge cases: `content` can be `null` when only tool calls are returned, multiple choices are requested but only `n=1` is in scope for MVP

---

## User Scenarios & Testing

### Primary Scenario

A developer building an agent application wants to use OpenAI's Chat Completions API instead of the Responses API. They configure a `LanguageModel` with `provider="openai"` and `model="gpt-4o"`. The SDK resolves the Chat Completions provider client from the registry. The Agent Loop consumes canonical events exactly as it does with the Responses API — the provider difference is invisible to the loop.

### Acceptance Scenarios

1. **Given** a `LanguageModel` with `provider="openai"` (Chat Completions), **When** `ProviderRegistry.create_client(model_config)` is called, **Then** an `OpenAIChatClient` instance is returned, not the `OpenAIResponsesClient`.

2. **Given** an `OpenAIChatClient` instance, **When** `client.chat(messages=[UserMessage(role="user", content="Hello"])` is called with `stream=False`, **Then** the returned `LLMResponse` contains the assistant's text content, normalized usage data, and a finish reason.

3. **Given** an `OpenAIChatClient` instance, **When** `client.chat(messages, tools, stream=True)` is called and the model responds with tool calls, **Then** the stream yields `ToolCallStartedEvent`, `ToolCallArgumentsDeltaEvent`, `ToolCallArgumentsDoneEvent`, and exactly one `ToolCallReadyEvent` per tool call — matching the canonical tool-call state machine.

4. **Given** a streaming request with `stream=True` and `raw_events=True`, **When** the async iterator is consumed, **Then** each yielded item follows the standard pairing contract from Stage 1: first canonical event from a chunk is paired with the raw SDK object, while synthetic or follow-on canonical events (from one-to-many chunk expansion) are paired with `raw=None`. Consumers MUST handle `raw=None` for synthetic or follow-on canonical events.

5. **Given** the `ProviderRegistry` singleton, **When** `ProviderRegistry.is_supported("openai")` is called, **Then** it returns `True`, and `ProviderRegistry.is_supported("openai-responses")` also returns `True` (both providers coexist).

6. **Given** the Stage 1 `"openai"` → `"openai-responses"` deprecation alias, **When** Stage 2 is deployed, **Then** the alias is removed and `"openai"` resolves to the Chat Completions client — existing code using `provider="openai-responses"` is unaffected.

### Edge Cases

- What happens when the model returns only tool calls (no content)? The `ContentDeltaEvent` and `ContentDoneEvent` events are omitted from the stream; `LLMResponse.content` is `None` in non-streaming mode.
- How does the client handle multiple `choices`? MVP scope uses `n=1` (single choice) — only `choices[0]` is normalized into canonical events.
- What happens when the stream ends with `finish_reason="stop"` vs `"tool_calls"`? Both are handled: `"stop"` produces `response.completed` with `finish_reason="stop"`; `"tool_calls"` produces tool events followed by `response.completed`.
- How are Chat Completions streaming `tool_calls` chunks aggregated? The `delta.tool_calls` array in each chunk contains index-based partial tool call data — the normalizer accumulates by index across chunks until all arguments are complete.
- What about `finish_reason="length"`? Treated the same as `"stop"` — produces `response.completed` with the actual finish reason.
- How does the client handle empty/invalid API keys? Delegated to the `openai` SDK which raises `openai.AuthenticationError` — the client translates this to `ProviderAuthError`.

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide an `OpenAIChatClient` class implementing the `LLMClient` ABC, wrapping `openai.chat.completions.create()`.
- **FR-002**: Non-streaming `chat()` MUST normalize the Chat Completions response to `LLMResponse` with `content`, `tool_calls`, `usage`, `finish_reason`, and `model`.
- **FR-003**: Streaming `chat()` MUST normalize Chat Completions delta chunks into canonical `LLMEvent` types: `ContentDeltaEvent`, `ContentDoneEvent`, `ToolCallStartedEvent`, `ToolCallArgumentsDeltaEvent`, `ToolCallArgumentsDoneEvent`, `ToolCallReadyEvent`, `ResponseUsageEvent`, `ResponseCompletedEvent`, `ResponseFailedEvent`.
- **FR-004**: The Chat Completions normalizer MUST aggregate `delta.tool_calls` array chunks across stream chunks by tool call index, producing one `ToolCallReadyEvent` per complete tool call.
- **FR-005**: The Chat Completions normalizer MUST emit exactly one `ToolCallReadyEvent` per executable tool call (matching the Stage 1 state machine contract).
- **FR-006**: Raw pass-through (`raw_events=True`) MUST follow the standard pairing contract from Stage 1's `_yield_events()`: when one chunk produces multiple canonical events, the first canonical event is paired with the original `ChatCompletionChunk` SDK object (lossless), and subsequent canonical events from the same chunk are paired with `raw=None`. For chunks that produce a single canonical event, the pair is `(canonical_event, raw_event)` where `raw_event.raw_event` is the SDK's `ChatCompletionChunk` object.
- **FR-007**: The provider MUST be registered under the `"openai"` identifier in `ProviderRegistry`.
- **FR-008**: The Stage 1 `"openai"` deprecation alias (pointing to `"openai-responses"`) MUST be removed upon registration of the Chat Completions client.
- **FR-009**: The `OpenAIChatClient` MUST accept `LanguageModel` configuration (API key, base URL, model name, temperature, max_tokens, etc.) and pass them to the SDK constructor.
- **FR-010**: Errors from the `openai` SDK (authentication, rate limits, invalid requests) MUST be translated to `ProviderAuthError` or `ProviderApiError` as appropriate.
- **FR-011**: The client MUST support tool-result continuation by appending `ToolResultMessage` to the messages list, mapping `call_id` and `content` to the Chat Completions tool message format internally. The client MUST also preserve the prior assistant response's `tool_calls` payload and inject a preceding assistant message with `tool_calls=[{id, type: "function", function: {name, arguments}}]` before each batch of `role="tool"` messages so the Chat Completions API can validate tool results against the original tool calls.
- **FR-012**: The `openai` SDK dependency (`openai>=2.34,<3`) already declared in `pyproject.toml` covers Chat Completions — no new dependencies are required.

### Key Entities

- **OpenAIChatClient**: Concrete `LLMClient` subclass wrapping `openai.chat.completions.create()`.
- **ChatCompletionsNormalizer**: Per-provider SSE normalizer that maps Chat Completions delta chunks to canonical `LLMEvent` types. Handles tool call accumulation across chunks.
- **ChoiceAccumulator**: Internal state tracker that accumulates `delta.content` and `delta.tool_calls` across stream chunks for a single choice index.

---

## Success Criteria

- [ ] **Non-streaming chat**: `OpenAIChatClient.chat(stream=False)` returns a valid `LLMResponse` with content, usage, and finish reason.
- [ ] **Streaming content**: Streaming chat yields `ContentDeltaEvent` and `ContentDoneEvent` events with correct delta text.
- [ ] **Streaming tool calls**: Streaming chat with tool-using models yields correctly accumulated `ToolCallReadyEvent` events.
- [ ] **Raw pass-through**: `raw_events=True` yields paired tuples with lossless SDK chunk objects.
- [ ] **Provider coexistence**: Both `"openai"` and `"openai-responses"` are registered and resolvable.
- [ ] **Alias removal**: The deprecated `"openai"` → `"openai-responses"` alias is removed; `"openai"` resolves to Chat Completions.
- [ ] **Error translation**: OpenAI SDK errors are wrapped in `ProviderAuthError` / `ProviderApiError`.
- [ ] **Tool-result continuation**: Tool results submitted as `ToolResultMessage` are correctly mapped to Chat Completions tool messages in the subsequent request.
- [ ] **Unit tests pass**: All Chat Completions provider tests pass with mocked SDK responses.
- [ ] **Integration tests pass**: End-to-end provider switching tests confirm both providers work.

---

## Testing Plan

### Unit Tests

- Test `OpenAIChatClient._chat_impl(non-streaming)` returns correct `LLMResponse` shape
- Test streaming normalization maps all Chat Completions chunk types to canonical events
- Test tool call accumulation across chunks (partial `tool_calls` arrays, index-based merging)
- Test raw pass-through yields correct `(canonical, raw)` pairs
- Test error translation: `openai.AuthenticationError` → `ProviderAuthError`, `openai.APIError` → `ProviderApiError`
- Test `ProviderRegistry` registration and resolution for `"openai"`
- Test that `"openai"` → `"openai-responses"` alias is gone
- Test tool-result continuation: `ToolResultMessage` → Chat Completions tool message format

### Integration Tests

- Test end-to-end streaming with mocked Chat Completions responses
- Test provider switching: `LanguageModel(provider="openai")` resolves to `OpenAIChatClient`, `LanguageModel(provider="openai-responses")` resolves to `OpenAIResponsesClient`
- Test that existing `OpenAIResponsesClient` integration tests still pass

### Manual Tests

- Run against real OpenAI API with `provider="openai"` and `model="gpt-4o"` to verify end-to-end streaming and normalization

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec & Design | Complete | Ready for planning |
| OpenAIChatClient implementation | TODO | |
| ChatCompletionsNormalizer | TODO | |
| Provider registration + alias removal | TODO | |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
