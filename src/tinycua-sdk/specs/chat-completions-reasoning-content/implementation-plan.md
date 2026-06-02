# Implementation: Chat Completions Reasoning Content Normalization

Add reasoning token normalization to the Chat Completions provider for both streaming and non-streaming responses, so consumers can differentiate between chain-of-thought reasoning and visible response content from Qwen-compatible servers.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: S

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv

---

## Success Criteria — Integration Tests (TDD First)

### Key Test Scenarios

- [x] **Scenario 1**: Streaming chunk with `reasoning_content` emits `ReasoningDeltaEvent`
- [x] **Scenario 2**: Streaming chunk with both `reasoning_content` and `content` emits both event types
- [x] **Scenario 3**: Stream finish with reasoning parts emits `ReasoningDoneEvent` before `ContentDoneEvent`
- [x] **Scenario 4**: Non-streaming response with `reasoning_content` includes it in `LLMResponse`
- [x] **Scenario 5**: Non-streaming response without `reasoning_content` sets field to `None`
- [x] **Edge case**: Empty `reasoning_content` string produces no event / `None`
- [x] **Backward compatibility**: Existing tests pass without modification

## Verification Plan

### Automated Tests

- [ ] Unit tests for streaming reasoning content normalization
- [ ] Unit tests for non-streaming reasoning content normalization
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua-sdk && uv run pytest`

---

## Proposed Changes

### Events Module

#### [MODIFY] `tinycua_sdk/agent/events.py`

- **Add `reasoning_content` field**: Add optional `reasoning_content: str | None` field to `LLMResponse` TypedDict

### Chat Completions Provider

#### [MODIFY] `tinycua_sdk/providers/open_ai_chat_completions.py`

- **Add imports**: `ReasoningDeltaEvent`, `ReasoningDoneEvent` from `tinycua_sdk.agent.events`
- **Extend `ChoiceAccumulator`**: Add `reasoning_parts: list[str]` and `reasoning_done_emitted: bool` fields
- **Extend `_normalize_chunk_content`**: Inspect `delta.get("reasoning_content")`, emit `ReasoningDeltaEvent`
- **Extend `_normalize_chunk_finalize`**: Emit `ReasoningDoneEvent` before `ContentDoneEvent` when reasoning parts exist
- **Extend `_normalize_non_streaming_response`**: Extract `reasoning_content` from message and include in `LLMResponse`

---

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `LLMResponse` | Modify | Add optional `reasoning_content: str | None` field |
| `ChoiceAccumulator` | Modify | Add `reasoning_parts` and `reasoning_done_emitted` fields |
| `_normalize_chunk_content` | Modify | Add reasoning_content inspection and ReasoningDeltaEvent emission |
| `_normalize_chunk_finalize` | Modify | Add ReasoningDoneEvent emission before ContentDoneEvent |
| `_normalize_non_streaming_response` | Modify | Add reasoning_content extraction from message |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Existing tests break | High | All changes are additive; existing code paths unchanged when reasoning_content is absent |
| LLMResponse backward incompatibility | Medium | Field is optional via `total=False`, defaults to `None` |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-02*
