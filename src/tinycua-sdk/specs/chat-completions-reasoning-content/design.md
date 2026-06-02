# Design Document: Chat Completions Reasoning Content Normalization

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-02

---

## Overview

This change extends the Chat Completions provider to handle `reasoning_content` from Qwen-compatible servers, for both streaming and non-streaming responses. The implementation adds reasoning tracking to the `ChoiceAccumulator` dataclass, extends `_normalize_chunk_content` to emit `ReasoningDeltaEvent`, extends `_normalize_chunk_finalize` to emit `ReasoningDoneEvent`, and extends `_normalize_non_streaming_response` to include `reasoning_content` in `LLMResponse`. The change is minimal, localized to a single file, and fully backward compatible.

---

## Architecture

### Component Overview

```
[Streaming Chunk] --> [_normalize_chat_chunk]
                          |
                    [_normalize_chunk_content]  <-- Extended: inspect reasoning_content
                          |                           emit ReasoningDeltaEvent
                    [_normalize_chunk_tool_calls]
                          |
                    [_normalize_chunk_finalize]  <-- Extended: emit ReasoningDoneEvent
                          |                           before ContentDoneEvent
                    [Events Output] --> [Consumer]

[Non-Streaming Response] --> [_normalize_non_streaming_response]
                                    |
                              Extended: inspect message.reasoning_content
                                    |     include in LLMResponse
                              [LLMResponse Output] --> [Consumer]
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `ChoiceAccumulator` | Modified | Add `reasoning_parts` and `reasoning_done_emitted` fields |
| `LLMResponse` | Modified | Add optional `reasoning_content: str | None` field |
| `_normalize_chunk_content` | Modified | Add reasoning_content inspection and ReasoningDeltaEvent emission |
| `_normalize_chunk_finalize` | Modified | Add ReasoningDoneEvent emission before ContentDoneEvent |
| `_normalize_non_streaming_response` | Modified | Add reasoning_content extraction from message |
| `open_ai_chat_completions.py` imports | Modified | Add ReasoningDeltaEvent, ReasoningDoneEvent imports |

---

## Data Model

### Schema Changes

**ChoiceAccumulator** — two new fields:

```python
@dataclass
class ChoiceAccumulator:
    index: int
    content_parts: list[str] = dataclass_field(default_factory=list)
    reasoning_parts: list[str] = dataclass_field(default_factory=list)  # NEW
    tool_calls: dict[int, ToolCallAccumulator] = dataclass_field(default_factory=dict)
    finish_reason: str | None = None
    content_done_emitted: bool = False
    reasoning_done_emitted: bool = False  # NEW
    started_emitted: bool = False
    done_emitted: bool = False
    completion_deferred: bool = False
```

**LLMResponse** — one new field (in `events.py`):

```python
class LLMResponse(TypedDict, total=False):
    content: str | None
    tool_calls: list[ToolCallDict] | None
    usage: TokenUsage | None
    finish_reason: str | None
    model: str | None
    reasoning_content: str | None  # NEW
```

Note: `LLMResponse` uses `total=False` so the new field is optional for backward compatibility.

---

## API / Interface Contracts

### Modified Functions

**Streaming — `_normalize_chunk_content`:**

```python
@staticmethod
def _normalize_chunk_content(
    delta: dict[str, Any],
    acc: ChoiceAccumulator,
    events: list[LLMEvent],
) -> None:
    """Normalize content and reasoning deltas within a streaming chunk.

    Handles both delta.content (visible text) and delta.reasoning_content
    (chain-of-thought tokens from Qwen-compatible servers).
    """
    # Reasoning content (must come before content for correct event ordering)
    reasoning = delta.get("reasoning_content")
    if reasoning:
        acc.reasoning_parts.append(reasoning)
        events.append(
            ReasoningDeltaEvent(
                type="response.reasoning.delta",
                delta=reasoning,
            ),
        )

    # Visible content (unchanged behavior)
    content = delta.get("content")
    if not content:
        return
    acc.content_parts.append(content)
    events.append(
        ContentDeltaEvent(
            type="response.output_text.delta",
            delta=content,
            index=acc.index,
        ),
    )
```

**Streaming — `_normalize_chunk_finalize`:**

```python
@staticmethod
def _normalize_chunk_finalize(
    finish_reason: str | None,
    chunk_data: dict[str, Any],
    acc: ChoiceAccumulator,
    events: list[LLMEvent],
) -> None:
    """Finalize chunk: tool call completion, reasoning done, content done, usage, lifecycle."""
    # ... existing tool call finalization ...

    # Reasoning done (must come BEFORE content done for correct event ordering)
    if finish_reason and acc.reasoning_parts and not acc.reasoning_done_emitted:
        acc.reasoning_done_emitted = True
        events.append(
            ReasoningDoneEvent(type="response.reasoning.done"),
        )

    # Content done (unchanged, but now comes after reasoning done)
    if finish_reason and acc.content_parts and not acc.content_done_emitted:
        acc.content_done_emitted = True
        events.append(
            ContentDoneEvent(type="response.output_text.done", index=acc.index),
        )

    # ... rest unchanged ...
```

**Non-streaming — `_normalize_non_streaming_response`:**

```python
@staticmethod
def _normalize_non_streaming_response(data: dict[str, Any]) -> LLMResponse:
    """Normalize a Chat Completions non-streaming response to ``LLMResponse``."""
    content = None
    reasoning_content = None  # NEW
    tool_calls: list[ToolCallDict] | None = None

    choices = data.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        content = message.get("content") or None
        reasoning_content = message.get("reasoning_content") or None  # NEW

        raw_tool_calls = message.get("tool_calls")
        # ... rest unchanged ...

    # ... build LLMResponse with reasoning_content=reasoning_content ...
```

### Error Handling

No new error cases. The implementation is purely additive — if `reasoning_content` is absent, behavior is identical to before.

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Add `ReasoningDeltaEvent` and `ReasoningDoneEvent` to imports in `open_ai_chat_completions.py`
- [ ] Add `reasoning_parts` and `reasoning_done_emitted` fields to `ChoiceAccumulator`
- [ ] Add `reasoning_content: str | None` field to `LLMResponse` in `events.py`
- [ ] Extend `_normalize_chunk_content` to inspect `delta.get("reasoning_content")` and emit `ReasoningDeltaEvent`
- [ ] Extend `_normalize_chunk_finalize` to emit `ReasoningDoneEvent` before `ContentDoneEvent`
- [ ] Extend `_normalize_non_streaming_response` to extract `reasoning_content` from message
- [ ] Write unit tests for streaming reasoning content normalization
- [ ] Write unit tests for non-streaming reasoning content normalization
- [ ] Verify existing tests pass (backward compatibility)

---

## Technical Decisions

1. **Decision**: Emit reasoning events in `_normalize_chunk_content` rather than a separate `_normalize_chunk_reasoning` method.
   - **Reason**: Keeps the code simple and follows the existing pattern where content-related deltas are handled in `_normalize_chunk_content`. A separate method would add unnecessary indirection for a small addition.
   - **Alternatives Considered**: Separate `_normalize_chunk_reasoning` method — rejected because it would require changes to `_normalize_chat_chunk` to call it, adding complexity without benefit.

2. **Decision**: Emit `ReasoningDoneEvent` before `ContentDoneEvent` in `_normalize_chunk_finalize`.
   - **Reason**: Reasoning tokens precede visible content in the model's output. The done event should follow the same ordering — reasoning finishes first, then content finishes.
   - **Alternatives Considered**: Emit after ContentDoneEvent — rejected because it would confuse consumers that expect reasoning to be complete before content is marked done.

3. **Decision**: Add `reasoning_parts` to `ChoiceAccumulator` even though we don't currently use the accumulated text.
   - **Reason**: Follows the existing pattern for `content_parts` and provides a hook for future use (e.g., consumers that need the full reasoning text).
   - **Alternatives Considered**: Skip accumulation — rejected because it would break the accumulator pattern and make future extensions harder.

4. **Decision**: Use `total=False` for the new `reasoning_content` field in `LLMResponse`.
   - **Reason**: `LLMResponse` is a `TypedDict` and existing code may construct it without the new field. Making it optional via `total=False` ensures backward compatibility.
   - **Alternatives Considered**: Use `NotRequired` — rejected because `LLMResponse` already uses `total=False` pattern.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing tests break | Low | High | All changes are additive; existing code paths unchanged when reasoning_content is absent |
| Event ordering confusion | Low | Medium | ReasoningDoneEvent emitted before ContentDoneEvent, matching model output order |
| Performance impact from additional dict lookup | Negligible | Negligible | Single `delta.get("reasoning_content")` call per chunk |
| LLMResponse backward incompatibility | Low | Medium | Field is optional via `total=False`, defaults to `None` |

---

## Open Questions _(optional)_

None — all design decisions are resolved.

---

## References

- Spec: `./spec.md`
- Events definition: `tinycua_sdk/agent/events.py`
- Responses API reasoning normalizer: `tinycua_sdk/providers/open_ai_responses.py` (`_normalize_reasoning_event`)
- Chat Completions provider: `tinycua_sdk/providers/open_ai_chat_completions.py`
