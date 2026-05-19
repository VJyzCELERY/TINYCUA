# Implementation: OpenAI Chat Completions Provider

Implement a first-class OpenAI Chat Completions provider for `tinycua-sdk` so `provider="openai"` uses `client.chat.completions.create()` while `provider="openai-responses"` continues to use the Responses API client. The implementation normalizes Chat Completions streaming chunks into the existing canonical event schema, preserves raw event pass-through, and removes the Stage 1 alias that routed `openai` to `openai-responses`.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [ ] **None** - mocked unit and integration tests require no `.env` file.
- [ ] **Optional manual verification** - `OPENAI_API_KEY` is required only for the real OpenAI API smoke test.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| None | No | N/A | N/A |

### Data / Fixtures

- [ ] **None** - tests should use mocked OpenAI SDK response and stream objects.

### Access / Permissions

- [ ] **None** - automated tests must not require network access or external credentials.
- [ ] **Optional OpenAI API access** - only for manual verification against `provider="openai"` and `model="gpt-4o"`.

### Developer Tooling

- [ ] **Runtime**: Python 3.12 through `uv`.
- [ ] **Package manager**: `uv`.
- [ ] **Test command**: `cd src/tinycua-sdk && uv run pytest`.

---

## Success Criteria — Integration Tests (TDD First)

Write these tests before implementation. They should fail first because `OpenAIChatClient` is not registered or implemented yet, then pass after the implementation is complete.

```python
# Test file: tests/integration/test_openai_chat_completions_provider.py
"""Integration tests for the OpenAI Chat Completions provider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua_sdk.agent.events import UserMessage
from tinycua_sdk.agent.llm_client import OpenAIChatClient, OpenAIResponsesClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.providers import get_provider_registry


@pytest.mark.asyncio
async def test_openai_provider_resolves_to_chat_completions_client():
    """provider='openai' creates OpenAIChatClient, not OpenAIResponsesClient."""
    registry = get_provider_registry()
    assert registry.is_supported("openai")
    assert registry.is_supported("openai-responses")

    openai_client = registry.create_client(
        LanguageModel(provider="openai", model_name="gpt-4o")
    )
    responses_client = registry.create_client(
        LanguageModel(provider="openai-responses", model_name="gpt-4o")
    )

    assert isinstance(openai_client, OpenAIChatClient)
    assert not isinstance(openai_client, OpenAIResponsesClient)
    assert isinstance(responses_client, OpenAIResponsesClient)


@pytest.mark.asyncio
async def test_openai_chat_non_streaming_normalizes_response():
    """Non-streaming Chat Completions responses normalize to LLMResponse."""
    client = OpenAIChatClient(LanguageModel(provider="openai", model_name="gpt-4o"))
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(return_value=MagicMock(model_dump=lambda: {
        "model": "gpt-4o",
        "choices": [{
            "message": {"role": "assistant", "content": "Hello!", "tool_calls": None},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }))
    client._client = sdk

    response = await client.chat([UserMessage(role="user", content="Hello")])

    assert response["content"] == "Hello!"
    assert response["finish_reason"] == "stop"
    assert response["usage"]["input_tokens"] == 3
    assert response["usage"]["output_tokens"] == 2
    sdk.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_chat_streaming_tool_calls_emit_ready_once():
    """Streaming tool deltas accumulate into exactly one ready event."""
    client = OpenAIChatClient(LanguageModel(provider="openai", model_name="gpt-4o"))
    stream = _mock_chat_stream([
        _chunk({"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "lookup", "arguments": "{\"q"}}]}),
        _chunk({"tool_calls": [{"index": 0, "function": {"arguments": "\":\"time\"}"}}]}),
        _chunk({}, finish_reason="tool_calls"),
    ])
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(return_value=stream)
    client._client = sdk

    result = await client.chat(
        [UserMessage(role="user", content="What time is it?")],
        tools=[{"name": "lookup", "description": "Lookup", "parameters": {"type": "object"}}],
        stream=True,
    )
    events = [event async for event in result]

    assert [event["type"] for event in events].count("tool_call.ready") == 1
    ready = next(event for event in events if event["type"] == "tool_call.ready")
    assert ready["call_id"] == "call_1"
    assert ready["name"] == "lookup"
    assert ready["arguments"] == "{\"q\":\"time\"}"


@pytest.mark.asyncio
async def test_openai_chat_raw_events_pair_canonical_with_sdk_chunks():
    """raw_events=True preserves the original ChatCompletionChunk object."""
    client = OpenAIChatClient(LanguageModel(provider="openai", model_name="gpt-4o"))
    raw_chunk = _chunk({"content": "Hi"})
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(return_value=_mock_chat_stream([raw_chunk]))
    client._client = sdk

    result = await client.chat(
        [UserMessage(role="user", content="Hello")],
        stream=True,
        raw_events=True,
    )
    pairs = [pair async for pair in result]

    canonical, raw = pairs[0]
    assert canonical["type"] == "response.output_text.delta"
    assert raw["provider"] == "openai"
    assert raw["raw_event"] is raw_chunk


async def _mock_chat_stream(chunks):
    for chunk in chunks:
        yield chunk


def _chunk(delta, finish_reason=None, usage=None):
    data = {
        "id": "chatcmpl_1",
        "model": "gpt-4o",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    if usage is not None:
        data["usage"] = usage
    return MagicMock(model_dump=lambda: data)
```

### Key Test Scenarios

- [ ] **Provider resolution**: `provider="openai"` resolves to `OpenAIChatClient`, while `provider="openai-responses"` still resolves to `OpenAIResponsesClient`.
- [ ] **Non-streaming response normalization**: Chat Completions SDK responses produce `LLMResponse` with `content`, `tool_calls`, `usage`, `finish_reason`, and `model`.
- [ ] **Streaming content normalization**: `choices[0].delta.content` yields `ContentDeltaEvent`, finalizes with `ContentDoneEvent`, and emits `ResponseCompletedEvent`.
- [ ] **Streaming tool-call accumulation**: partial `delta.tool_calls[]` chunks are accumulated by index and emit exactly one `ToolCallReadyEvent` per call.
- [ ] **Raw event pass-through**: `raw_events=True` yields `(canonical_event, RawSseEvent)` tuples containing the original SDK chunk object.
- [ ] **Alias removal**: `resolve_provider("openai")` remains `"openai"` and no longer warns or maps to `"openai-responses"`.
- [ ] **Responses API coexistence**: existing `OpenAIResponsesClient` tests continue to pass without behavior changes.

## Verification Plan

### Automated Tests

- [ ] Integration tests defined above: `cd src/tinycua-sdk && uv run pytest tests/integration/test_openai_chat_completions_provider.py`.
- [ ] Unit tests for Chat Completions payload translation, non-streaming normalization, streaming normalization, raw tuples, tool-result continuation, and error translation.
- [ ] Provider registry tests: `cd src/tinycua-sdk && uv run pytest tests/unit/test_provider_registry.py tests/unit/test_provider_switching.py tests/integration/test_provider_switching.py`.
- [ ] Existing SDK suite: `cd src/tinycua-sdk && uv run pytest`.

### Manual Verification

- [ ] With `OPENAI_API_KEY` set, run a local smoke script using `LanguageModel(provider="openai", model_name="gpt-4o")` and confirm a non-streaming response returns content.
- [ ] Run a streaming request against the real API and confirm canonical events are yielded in the expected state-machine order.
- [ ] Run `LanguageModel(provider="openai-responses", model_name="gpt-4o")` and confirm the Responses API client remains selectable.

### Performance Considerations

- [ ] Confirm the streaming normalizer processes chunks incrementally and does not buffer full content or tool-call streams except accumulated text/arguments required for done/ready events.
- [ ] Confirm `n=1` is the only supported normalization path and additional choices are ignored without unbounded accumulator growth.

## Proposed Changes

### Chat Completions Client

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **Description of change**: Add `OpenAIChatClient` next to `OpenAIResponsesClient`, wrapping `AsyncOpenAI.chat.completions.create()` for non-streaming and streaming modes.
- **Rationale**: The provider needs a concrete `LLMClient` implementation under the existing SDK-backed client module to reuse shared error handling and canonical event contracts.

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **Description of change**: Add Chat Completions-specific translation helpers for request payloads where needed, including Chat Completions message shape, tool specs, `max_tokens`, and `ToolResultMessage` mapping to `{role: "tool", tool_call_id, content}`. The client MUST also preserve prior assistant `tool_calls` from the Chat Completions response and inject a preceding assistant message with `tool_calls=[{id, type: "function", function: {name, arguments}}]` before tool-result messages in follow-up requests, so the Chat Completions API can validate each `tool_call_id`.
- **Rationale**: Existing helpers are Responses API-shaped (`input`, `function_call_output`, `max_output_tokens`) and must not be reused blindly for Chat Completions request payloads. Without the assistant `tool_calls` context, the Chat Completions API rejects tool-result messages as invalid.

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **Description of change**: Add `ChoiceAccumulator` and `ToolCallAccumulator` dataclasses plus `_normalize_chat_chunk()` and small helper functions to normalize content, usage, lifecycle, and tool-call delta chunks.
- **Rationale**: Chat Completions streams per-choice delta chunks, so it needs a separate normalizer from `_normalize_responses_event()`.

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **Description of change**: Translate OpenAI SDK exceptions in the Chat Completions client into `ProviderAuthError` or `ProviderApiError`, matching the existing provider error contract.
- **Rationale**: Consumer code should receive SDK-neutral provider exceptions from all provider clients.

### Provider Registry

#### [MODIFY] `tinycua_sdk/core/providers.py`

- **Description of change**: Remove `_PROVIDER_ALIASES["openai"] = OPENAI_RESPONSES`, add an `OPENAI_CHAT` constant if useful, and make `resolve_provider("openai")` return `"openai"`.
- **Rationale**: `openai` becomes a real Chat Completions provider, not a deprecated alias.

#### [MODIFY] `tinycua_sdk/core/providers.py`

- **Description of change**: Register `"openai"` to create `OpenAIChatClient` and continue registering `"openai-responses"` to create `OpenAIResponsesClient`.
- **Rationale**: Both OpenAI provider variants must coexist with stable identifiers.

### Public Exports

#### [MODIFY] `tinycua_sdk/agent/__init__.py`

- **Description of change**: Export `OpenAIChatClient` from the agent package if provider-specific clients are exported there.
- **Rationale**: Keeps import behavior consistent with `OpenAIResponsesClient`.

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **Description of change**: Add `OpenAIChatClient` to `__all__`.
- **Rationale**: Makes the new provider client an explicit module export.

### Tests

#### [NEW] `tests/unit/test_openai_chat_client.py`

- **Description**: Unit tests for payload construction, non-streaming normalization, streaming content normalization, streaming tool-call accumulation, raw pass-through, error translation, and tool-result continuation.
- **Dependencies**: Mocked `AsyncOpenAI` client and mocked SDK response/chunk objects.

#### [NEW] `tests/integration/test_openai_chat_completions_provider.py`

- **Description**: Integration tests for default registry provider coexistence, alias removal, and end-to-end mocked client behavior through `LanguageModel(provider="openai")`.
- **Dependencies**: `ProviderRegistry`, `LanguageModel`, `OpenAIChatClient`, and `OpenAIResponsesClient`.

#### [MODIFY] `tests/unit/test_llm_client.py`

- **Description of change**: Keep existing Responses API assertions intact; move Chat Completions-specific assertions to the new unit test file unless small import/export checks fit here.
- **Rationale**: Prevent the already large `test_llm_client.py` from becoming a mixed-provider test sink.

#### [MODIFY] `tests/unit/test_provider_registry.py`, `tests/unit/test_provider_switching.py`, `tests/integration/test_provider_switching.py`

- **Description of change**: Update expectations that currently treat `"openai"` as an alias to `"openai-responses"`; assert `"openai"` is directly supported and returns `OpenAIChatClient`.
- **Rationale**: The core behavioral change is provider identifier ownership.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `OpenAIChatClient` | New | SDK-backed Chat Completions provider implementing `LLMClient` |
| Chat Completions normalizer | New | Converts `ChatCompletionChunk` deltas into canonical `LLMEvent` types |
| `ChoiceAccumulator` | New | Tracks content, tool calls, finish reason, and usage for choice index 0 |
| `ToolCallAccumulator` | New | Tracks streamed tool-call `id`, `name`, and argument fragments by tool-call index |
| `ProviderRegistry` defaults | Modify | Registers both `openai` and `openai-responses` as distinct providers |
| Provider alias map | Modify | Removes `openai` to `openai-responses` alias |
| Agent package exports | Modify | Exposes `OpenAIChatClient` where provider clients are exported |

## Data Model Changes

```python
@dataclass
class ChoiceAccumulator:
    index: int
    content_parts: list[str] = field(default_factory=list)
    tool_calls: dict[int, ToolCallAccumulator] = field(default_factory=dict)
    finish_reason: str | None = None
    content_done_emitted: bool = False


@dataclass
class ToolCallAccumulator:
    index: int
    id: str | None = None
    name: str | None = None
    arguments_parts: list[str] = field(default_factory=list)
    started_emitted: bool = False
    done_emitted: bool = False
    ready_emitted: bool = False
```

## API Changes

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| N/A | N/A | No HTTP endpoints are added. |

### Modified Endpoints

| Method | Path | Change |
|--------|------|--------|
| N/A | N/A | SDK provider behavior changes only. |

### Public Python Interfaces

| Interface | Change |
|-----------|--------|
| `tinycua_sdk.agent.llm_client.OpenAIChatClient` | New provider client class |
| `ProviderRegistry.create_client(LanguageModel(provider="openai"))` | Returns `OpenAIChatClient` |
| `ProviderRegistry.create_client(LanguageModel(provider="openai-responses"))` | Continues returning `OpenAIResponsesClient` |
| `resolve_provider("openai")` | Returns `"openai"` instead of `"openai-responses"` |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `openai` | `>=2.34,<3` | Existing SDK dependency used for `AsyncOpenAI.chat.completions.create()` |

### Internal Dependencies

- [ ] Depends on Stage 1 `LLMClient`, canonical event schema, `OpenAIResponsesClient`, and `ProviderRegistry` work already present.
- [ ] Does not block other features except provider-specific work that assumes `provider="openai"` should resolve to Chat Completions.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reusing Responses payload helpers sends wrong Chat Completions request fields | High | Add Chat-specific payload tests for `messages`, `tools`, `max_tokens`, and tool-result mapping |
| Tool-call deltas produce duplicate `tool_call.ready` events | High | Track emitted state in `ToolCallAccumulator` and assert exactly one ready event per call |
| Alias removal breaks tests or users relying on Stage 1 `provider="openai"` Responses behavior | High | Update tests and document that Responses users must use `provider="openai-responses"` |
| Raw pass-through loses the original SDK object | Medium | Pair canonical events with `RawSseEvent(provider="openai", raw_event=chunk)` through `_yield_events()` following standard one-to-many pairing rules (first canonical gets raw, follow-on canonicals get `raw=None`) |
| Streaming terminal chunks without content omit completion events | Medium | Unit test empty/tool-only terminal chunks and always emit `ResponseCompletedEvent` when `finish_reason` is present |
| OpenAI SDK chunk model variations differ from mocked dictionaries | Medium | Normalize through `model_dump()` when available and write mocks that match SDK field names |
| Multiple choices are ignored for MVP | Low | Explicitly normalize only `choices[0]`, document `n=1` scope, and avoid accumulating other choices |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-19*
