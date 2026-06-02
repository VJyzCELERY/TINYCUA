# Feature Specification: Chat Completions Reasoning Content Normalization

**Status**: Draft
**Created**: 2026-06-02
**Last Updated**: 2026-06-02
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement _(mandatory)_

- **Goals**: Provide reasoning token normalization in the Chat Completions provider so consumers can differentiate between chain-of-thought reasoning and visible response content, for both streaming and non-streaming responses.
- **Gaps**: The Chat Completions provider has two gaps:
  1. **Streaming**: `_normalize_chunk_content()` only reads `delta.get("content")` and emits it as `response.output_text.delta`. It does not inspect `delta.get("reasoning_content")`, even though the SDK already defines canonical `response.reasoning.delta` / `response.reasoning.done` events. Qwen-compatible Chat Completions servers emit reasoning tokens via `reasoning_content` in the delta, but these are silently dropped before reaching consumers.
  2. **Non-streaming**: `_normalize_non_streaming_response()` only reads `message.get("content")`. It does not inspect `message.get("reasoning_content")`, so reasoning tokens in non-streaming responses are also dropped.
- **Non-Goals**: This spec does NOT cover:
  - Changes to the Responses API provider (already handles reasoning correctly)
  - New event type definitions (already exist in `events.py`)
- **Constraints**: Must maintain backward compatibility with existing consumers. Must not break existing streaming or non-streaming behavior for non-reasoning models.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer uses the tinycua-sdk to interact with a Qwen-compatible Chat Completions server (e.g., Qwen with reasoning enabled, or any OpenAI-compatible proxy that emits `reasoning_content`). The SDK normalizes reasoning tokens into canonical reasoning events for streaming, and preserves reasoning content in the response object for non-streaming, allowing the consumer to display or process reasoning separately from the visible response content.

### Acceptance Scenarios

1. **Given** a streaming chunk with `delta.reasoning_content` set, **When** the chunk is normalized, **Then** a `ReasoningDeltaEvent` with type `response.reasoning.delta` is emitted with the reasoning text.
2. **Given** a streaming chunk with both `delta.reasoning_content` and `delta.content` set, **When** the chunk is normalized, **Then** both a `ReasoningDeltaEvent` and a `ContentDeltaEvent` are emitted.
3. **Given** a streaming chunk with `delta.reasoning_content` set and `finish_reason` present, **When** the chunk is finalized, **Then** a `ReasoningDoneEvent` with type `response.reasoning.done` is emitted before the `ContentDoneEvent`.
4. **Given** a streaming chunk with only `delta.content` set (no reasoning), **When** the chunk is normalized, **Then** only a `ContentDeltaEvent` is emitted (backward compatible).
5. **Given** a non-streaming response with `message.reasoning_content` set, **When** the response is normalized, **Then** the reasoning content is preserved in the `LLMResponse`.
6. **Given** a non-streaming response with both `message.reasoning_content` and `message.content` set, **When** the response is normalized, **Then** both `content` and `reasoning_content` are present in the `LLMResponse`.
7. **Given** a non-streaming response with only `message.content` set (no reasoning), **When** the response is normalized, **Then** `reasoning_content` is `None` in the `LLMResponse` (backward compatible).

### Edge Cases

- What happens when `reasoning_content` is an empty string? → Should be treated as falsy, no event emitted / field set to `None`.
- What happens when `reasoning_content` is present but `content` is also present in the same delta? → Both events should be emitted.
- What happens when the stream ends with reasoning still in progress (no finish_reason)? → `ReasoningDoneEvent` should NOT be emitted until finish_reason is received.
- What happens with models that don't emit reasoning_content? → No change in behavior, backward compatible.

---

## Requirements _(mandatory)_

### Functional Requirements

**Streaming:**
- **FR-001**: The Chat Completions streaming normalizer MUST inspect `delta.get("reasoning_content")` in addition to `delta.get("content")`.
- **FR-002**: When `reasoning_content` is present and truthy, the normalizer MUST emit a `ReasoningDeltaEvent` with type `response.reasoning.delta` and the reasoning text as `delta`.
- **FR-003**: The `ChoiceAccumulator` MUST track reasoning content parts in a new `reasoning_parts: list[str]` field.
- **FR-004**: When `finish_reason` is received and reasoning parts have been accumulated, the normalizer MUST emit a `ReasoningDoneEvent` with type `response.reasoning.done`.
- **FR-005**: The normalizer MUST emit `ReasoningDoneEvent` before `ContentDoneEvent` when both reasoning and content are present.

**Non-streaming:**
- **FR-006**: The Chat Completions non-streaming normalizer MUST inspect `message.get("reasoning_content")` in addition to `message.get("content")`.
- **FR-007**: When `reasoning_content` is present and truthy in a non-streaming response, the normalizer MUST include it in the `LLMResponse` as `reasoning_content`.
- **FR-008**: When `reasoning_content` is absent or falsy in a non-streaming response, `reasoning_content` in `LLMResponse` MUST be `None`.

**General:**
- **FR-009**: The implementation MUST be backward compatible — existing consumers that don't handle reasoning must not break.

### Key Entities _(include if feature involves data)_

- **ChoiceAccumulator**: Extended with `reasoning_parts: list[str]` and `reasoning_done_emitted: bool` fields.
- **LLMResponse**: Extended with optional `reasoning_content: str | None` field.
- **ReasoningDeltaEvent**: Already defined in `events.py` — type `response.reasoning.delta`, delta `str`.
- **ReasoningDoneEvent**: Already defined in `events.py` — type `response.reasoning.done`.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Streaming reasoning tokens are surfaced**: Streaming chunks with `reasoning_content` produce `response.reasoning.delta` events.
- [ ] **Streaming reasoning done is emitted**: When the stream finishes, `response.reasoning.done` is emitted if reasoning was present.
- [ ] **Streaming both reasoning and content**: Chunks with both `reasoning_content` and `content` emit both event types.
- [ ] **Non-streaming reasoning preserved**: Non-streaming responses with `reasoning_content` include it in `LLMResponse`.
- [ ] **Backward compatible**: Existing tests pass without modification.
- [ ] **Non-reasoning models unaffected**: Models that don't emit `reasoning_content` produce no reasoning events.

---

## Testing Plan _(mandatory)_

### Unit Tests

**Streaming:**
- Test `_normalize_chunk_content` emits `ReasoningDeltaEvent` when `reasoning_content` is present.
- Test `_normalize_chunk_content` emits both events when both `reasoning_content` and `content` are present.
- Test `_normalize_chunk_finalize` emits `ReasoningDoneEvent` when reasoning parts exist and finish_reason is received.
- Test `_normalize_chunk_finalize` emits `ReasoningDoneEvent` before `ContentDoneEvent`.
- Test empty `reasoning_content` string produces no event.
- Test `ChoiceAccumulator` tracks reasoning parts correctly.

**Non-streaming:**
- Test `_normalize_non_streaming_response` includes `reasoning_content` in `LLMResponse` when present.
- Test `_normalize_non_streaming_response` sets `reasoning_content` to `None` when absent.
- Test `_normalize_non_streaming_response` handles both `reasoning_content` and `content` present.

### Integration Tests

- Test full streaming flow with reasoning-enabled model (mock server).
- Test full non-streaming flow with reasoning-enabled model (mock server).
- Test that existing streaming and non-streaming tests continue to pass.

### Manual Tests _(if applicable)_

- Test against a Qwen-compatible server with reasoning enabled (if available).

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Spec | Done | |
| Design | TODO | |
| Implementation | TODO | |
| Tests | TODO | |
| PR | TODO | |

---

## Open Questions _(optional)_

None — all questions resolved.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
