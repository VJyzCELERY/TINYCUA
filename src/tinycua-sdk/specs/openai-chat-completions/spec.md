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
- The provider is registered as `"openai-chat-completions"` in the provider registry
- The Stage 1 `"openai"` → `"openai-responses"` deprecation alias remains in place since `"openai-chat-completions"` does not conflict

### Gaps

- The SDK currently supports only the OpenAI Responses API (`openai-responses` provider)
- The `"openai"` provider identifier remains occupied by the Stage 1 deprecation alias pointing to `openai-responses`; the Chat Completions provider is registered under `"openai-chat-completions"` instead
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

- Must use the official `openai` PyPI SDK for Chat Completions access — no HTTP-level client
- Must normalize Chat Completions SSE events into the existing canonical event schema (Responses-shaped TypedDicts)
- Must support raw event pass-through via the same `(canonical, raw)` paired tuple mechanism
- Must register the Chat Completions provider under `"openai-chat-completions"`; the Stage 1 `"openai"` deprecation alias remains in place
- The `"openai-responses"` provider must continue to work unchanged
- Existing tool-call state machine rules (one `tool_call.ready` per executable call) apply unchanged
- Must handle Chat Completions-specific edge cases: `content` can be `null` when only tool calls are returned, multiple choices are requested but only `n=1` is in scope for MVP

---

## User Scenarios & Testing

### Primary Scenario

A developer building an agent application wants to use OpenAI's Chat Completions API instead of the Responses API. They configure a `LanguageModel` with `provider="openai-chat-completions"` and `model="gpt-4o"`. The SDK resolves the Chat Completions provider client from the registry. The Agent Loop consumes canonical events exactly as it does with the Responses API — the provider difference is invisible to the loop.

### Acceptance Scenarios

1. **Given** a `LanguageModel` with `provider="openai-chat-completions"` (Chat Completions), **When** a provider client is created from the model configuration, **Then** a Chat Completions provider client instance is returned, not a Responses API provider client.

2. **Given** a Chat Completions provider client instance, **When** `client.chat(messages=[UserMessage(role="user", content="Hello")])` is called with `stream=False`, **Then** the returned `LLMResponse` contains the assistant's text content, normalized usage data, and a finish reason.

3. **Given** a Chat Completions provider client instance, **When** `client.chat(messages, tools, stream=True)` is called and the model responds with tool calls, **Then** the stream yields `ToolCallStartedEvent`, `ToolCallArgumentsDeltaEvent`, `ToolCallArgumentsDoneEvent`, and exactly one `ToolCallReadyEvent` per tool call — matching the canonical tool-call state machine.

4. **Given** a streaming request with `stream=True` and `raw_events=True`, **When** the async iterator is consumed, **Then** each yielded item follows the standard pairing contract from Stage 1: first canonical event from a chunk is paired with the raw SDK object, while synthetic or follow-on canonical events (from one-to-many chunk expansion) are paired with `raw=None`. Consumers MUST handle `raw=None` for synthetic or follow-on canonical events.

5. **Given** the provider registry, **When** provider support is checked for `"openai-chat-completions"`, **Then** it returns `True`, and checking `"openai"` and `"openai-responses"` also returns `True` (all three providers coexist).

6. **Given** the Stage 1 `"openai"` → `"openai-responses"` deprecation alias, **When** Stage 2 is deployed, **Then** the alias remains in place and `"openai-chat-completions"` is registered as a separate Chat Completions provider — existing code using `provider="openai"` or `provider="openai-responses"` is unaffected.

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

- **FR-001**: The system MUST provide a first-class provider for OpenAI Chat Completions through the existing `LLMClient` interface.
- **FR-002**: Non-streaming `chat()` MUST normalize the Chat Completions response to `LLMResponse` with `content`, `tool_calls`, `usage`, `finish_reason`, and `model`.
- **FR-003**: Streaming `chat()` MUST normalize Chat Completions delta chunks into canonical `LLMEvent` types: `ResponseCreatedEvent`, `ContentDeltaEvent`, `ContentDoneEvent`, `ToolCallStartedEvent`, `ToolCallArgumentsDeltaEvent`, `ToolCallArgumentsDoneEvent`, `ToolCallReadyEvent`, `ResponseUsageEvent`, `ResponseCompletedEvent`.
- **FR-004**: The Chat Completions normalizer MUST aggregate `delta.tool_calls` array chunks across stream chunks by tool call index, producing one `ToolCallReadyEvent` per complete tool call.
- **FR-005**: The Chat Completions normalizer MUST emit exactly one `ToolCallReadyEvent` per executable tool call (matching the Stage 1 state machine contract).
- **FR-006**: Raw pass-through (`raw_events=True`) MUST follow the standard pairing contract from Stage 1's `_yield_events()`: when one chunk produces multiple canonical events, the first canonical event is paired with the original `ChatCompletionChunk` SDK object (lossless), and subsequent canonical events from the same chunk are paired with `raw=None`. For chunks that produce a single canonical event, the pair is `(canonical_event, raw_event)` where `raw_event.raw_event` is the SDK's `ChatCompletionChunk` object.
- **FR-007**: The provider MUST be registered under the `"openai-chat-completions"` identifier in the provider registry.
- **FR-008**: The Stage 1 `"openai"` deprecation alias (pointing to `"openai-responses"`) MUST remain in place after registration of the Chat Completions client.
- **FR-009**: The OpenAI Chat Completions provider MUST accept `LanguageModel` configuration (API key, base URL, model name, temperature, max_tokens, etc.) and pass them to the SDK constructor.
- **FR-010**: Errors from the `openai` SDK (authentication, rate limits, invalid requests) MUST be translated to `ProviderAuthError` or `ProviderApiError` as appropriate.
- **FR-011**: The client MUST support tool-result continuation by appending `ToolResultMessage` to the messages list, mapping `call_id` and `content` to the Chat Completions tool message format internally. The client MUST also preserve the prior assistant response's `tool_calls` payload and inject a preceding assistant message with `tool_calls=[{id, type: "function", function: {name, arguments}}]` before each batch of `role="tool"` messages so the Chat Completions API can validate tool results against the original tool calls.
- **FR-012**: The `openai` SDK dependency (`openai>=2.34,<3`) already declared in `pyproject.toml` covers Chat Completions — no new dependencies are required.

---

## Success Criteria

- [ ] **Non-streaming chat**: Chat Completions non-streaming chat returns a valid `LLMResponse` with content, usage, and finish reason.
- [ ] **Streaming content**: Streaming chat yields `ContentDeltaEvent` and `ContentDoneEvent` events with correct delta text.
- [ ] **Streaming tool calls**: Streaming chat with tool-using models yields correctly accumulated `ToolCallReadyEvent` events.
- [ ] **Raw pass-through**: `raw_events=True` yields paired tuples with lossless SDK chunk objects.
- [ ] **Provider coexistence**: `"openai-chat-completions"`, `"openai"`, and `"openai-responses"` are all registered and resolvable.
- [ ] **Alias preserved**: The `"openai"` → `"openai-responses"` alias remains in place; `"openai-chat-completions"` resolves to Chat Completions.
- [ ] **Error translation**: OpenAI SDK errors are wrapped in `ProviderAuthError` / `ProviderApiError`.
- [ ] **Tool-result continuation**: Tool results submitted as `ToolResultMessage` are correctly mapped to Chat Completions tool messages in the subsequent request.
- [ ] **Unit tests pass**: All Chat Completions provider tests pass with mocked SDK responses.
- [ ] **Integration tests pass**: End-to-end provider switching tests confirm both providers work.

---

## Testing Plan

### Unit Tests

- Test Chat Completions non-streaming `_chat_impl` returns correct `LLMResponse` shape
- Test streaming normalization maps all Chat Completions chunk types to canonical events
- Test tool call accumulation across chunks (partial `tool_calls` arrays, index-based merging)
- Test raw pass-through yields correct `(canonical, raw)` pairs
- Test error translation: `openai.AuthenticationError` → `ProviderAuthError`, `openai.APIError` → `ProviderApiError`
- Test provider registry registration and resolution for `"openai-chat-completions"`
- Test that the `"openai"` → `"openai-responses"` alias remains in place
- Test tool-result continuation: `ToolResultMessage` → Chat Completions tool message format

### Integration Tests

- Test end-to-end streaming with mocked Chat Completions responses
- Test provider switching: `LanguageModel(provider="openai-chat-completions")` resolves to the Chat Completions provider client, `LanguageModel(provider="openai")` still resolves to `OpenAIResponsesClient` (via alias), and `LanguageModel(provider="openai-responses")` also resolves to `OpenAIResponsesClient`
- Test that existing `OpenAIResponsesClient` integration tests still pass

### Manual Tests

- Run against a local OpenAI-compatible server (default `http://localhost:1234/v1`) with `provider="openai-chat-completions"` to verify end-to-end streaming and normalization against local LLM
- Run against real OpenAI API with `provider="openai-chat-completions"` and `model="gpt-4o"` to verify end-to-end streaming and normalization

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec & Design | Complete | Ready for planning |
| Chat Completions provider client implementation | Complete | |
| Chat Completions SSE normalizer | Complete | |
| Provider registration (openai-chat-completions) | Complete | |
| Unit tests | Complete | |
| Integration tests | Complete | |

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
