# Implementation: OpenAI Chat Completions Provider

Implement a first-class OpenAI Chat Completions provider for `tinycua-sdk` so `provider="openai-chat-completions"` uses `client.chat.completions.create()` while `provider="openai"` and `provider="openai-responses"` continue to use the Responses API client (via the Stage 1 deprecation alias). The implementation normalizes Chat Completions streaming chunks into the existing canonical event schema, preserves raw event pass-through, and registers the new provider without removing the existing alias.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [ ] **`.env` setup** - copy `.env.example` to `.env` and configure `TINYCUA_BASE_URL` pointing to the local LLM server (default: `http://localhost:1234/v1`). This is required for local smoke tests.
- [ ] **Optional real OpenAI API key** - set `OPENAI_API_KEY` only for real OpenAI API smoke tests.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| LLM Server (OpenAI-compatible) | Yes (for manual smoke tests) | Start any OpenAI-compatible server on `localhost:1234/v1` (e.g., LM Studio, llama.cpp, vLLM) | `curl http://localhost:1234/v1/models` returns 200 |

### Data / Fixtures

- [ ] **None** - tests should use mocked OpenAI SDK response and stream objects.

### Access / Permissions

- [ ] **None** - automated tests must not require network access or external credentials.
- [ ] **Local LLM Server** - required for manual smoke tests. Default endpoint is `http://localhost:1234/v1`.
- [ ] **Optional OpenAI API access** - only for manual verification against real OpenAI with `provider="openai-chat-completions"` and `model="gpt-4o"`.

### Developer Tooling

- [ ] **Runtime**: Python 3.12 through `uv`.
- [ ] **Package manager**: `uv`.
- [ ] **Test command**: `cd src/tinycua-sdk && uv run pytest`.

---

## Success Criteria — Integration Tests (TDD First)

Write these tests before implementation. They should fail first because `OpenAIChatCompletionsClient` is not registered or implemented yet, then pass after the implementation is complete.

```python
# Test file: tests/integration/test_openai_chat_completions_provider.py
"""Integration tests for the OpenAI Chat Completions provider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua_sdk.agent.events import UserMessage
from tinycua_sdk.agent.llm_client import OpenAIChatCompletionsClient, OpenAIResponsesClient
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.core.providers import get_provider_registry


@pytest.mark.asyncio
async def test_openai_chat_completions_provider_resolves():
    """provider='openai-chat-completions' creates OpenAIChatCompletionsClient."""
    registry = get_provider_registry()
    assert registry.is_supported("openai-chat-completions")
    assert registry.is_supported("openai")
    assert registry.is_supported("openai-responses")

    chat_client = registry.create_client(
        LanguageModel(provider="openai-chat-completions", model_name="gpt-4o")
    )
    responses_client = registry.create_client(
        LanguageModel(provider="openai-responses", model_name="gpt-4o")
    )

    assert isinstance(chat_client, OpenAIChatCompletionsClient)
    assert not isinstance(chat_client, OpenAIResponsesClient)
    assert isinstance(responses_client, OpenAIResponsesClient)


@pytest.mark.asyncio
async def test_openai_chat_non_streaming_normalizes_response():
    """Non-streaming Chat Completions responses normalize to LLMResponse."""
    client = OpenAIChatCompletionsClient(LanguageModel(provider="openai-chat-completions", model_name="gpt-4o"))
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
    client = OpenAIChatCompletionsClient(LanguageModel(provider="openai-chat-completions", model_name="gpt-4o"))
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
    client = OpenAIChatCompletionsClient(LanguageModel(provider="openai-chat-completions", model_name="gpt-4o"))
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
    assert raw["provider"] == "openai-chat-completions"
    assert raw["raw_event"] is raw_chunk


@pytest.mark.asyncio
async def test_openai_chat_raw_events_one_to_many_pairing():
    """One chunk producing >=2 canonical events: first gets raw, follow-on gets raw=None."""
    client = OpenAIChatCompletionsClient(LanguageModel(provider="openai-chat-completions", model_name="gpt-4o"))
    terminal_chunk = _chunk({"content": "Bye"}, finish_reason="stop", usage={"prompt_tokens": 5, "completion_tokens": 8})
    sdk = MagicMock()
    sdk.chat.completions.create = AsyncMock(return_value=_mock_chat_stream([terminal_chunk]))
    client._client = sdk

    result = await client.chat(
        [UserMessage(role="user", content="Hello")],
        stream=True,
        raw_events=True,
    )
    pairs = [pair async for pair in result]

    # First event (ContentDelta) should carry the raw chunk
    assert pairs[0].raw is not None
    assert pairs[0].raw["raw_event"] is terminal_chunk
    # A later synthetic event (e.g. ContentDone or ResponseCompleted) gets raw=None
    assert any(p.raw is None for p in pairs[1:]), "Expected at least one follow-on event with raw=None"


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

- [ ] **Provider resolution**: `provider="openai-chat-completions"` resolves to `OpenAIChatCompletionsClient`, while `provider="openai"` still resolves to `OpenAIResponsesClient` via alias, and `provider="openai-responses"` still resolves to `OpenAIResponsesClient`.
- [ ] **Non-streaming response normalization**: Chat Completions SDK responses produce `LLMResponse` with `content`, `tool_calls`, `usage`, `finish_reason`, and `model`.
- [ ] **Streaming content normalization**: `choices[0].delta.content` yields `ContentDeltaEvent`, finalizes with `ContentDoneEvent`, and emits `ResponseCompletedEvent`.
- [ ] **Streaming tool-call accumulation**: partial `delta.tool_calls[]` chunks are accumulated by index and emit exactly one `ToolCallReadyEvent` per call.
- [ ] **Raw event pass-through**: `raw_events=True` yields `(canonical_event, RawSseEvent)` tuples containing the original SDK chunk object.
- [ ] **Alias preserved**: `resolve_provider("openai")` continues to resolve to `"openai-responses"` (alias remains in place).
- [ ] **Responses API coexistence**: existing `OpenAIResponsesClient` tests continue to pass without behavior changes.

## Verification Plan

### Automated Tests

- [ ] Integration tests defined above: `cd src/tinycua-sdk && uv run pytest tests/integration/test_openai_chat_completions_provider.py`.
- [ ] Unit tests for Chat Completions payload translation, non-streaming normalization, streaming normalization, raw tuples, tool-result continuation, and error translation.
- [ ] Provider registry tests: `cd src/tinycua-sdk && uv run pytest tests/unit/test_provider_registry.py tests/unit/test_provider_switching.py tests/integration/test_provider_switching.py`.
- [ ] Existing SDK suite: `cd src/tinycua-sdk && uv run pytest`.

### Manual Verification

- [ ] **Local LLM Server smoke test**: With the local server running at `http://localhost:1234/v1`, run a smoke script using `LanguageModel(provider="openai-chat-completions", model_name=<model>, base_url="http://localhost:1234/v1")` and confirm non-streaming response returns content. Use `.env.example` as the configuration reference.
- [ ] **Real OpenAI API smoke test**: With `OPENAI_API_KEY` set, run a smoke script using `LanguageModel(provider="openai-chat-completions", model_name="gpt-4o")` and confirm a non-streaming response returns content.
- [ ] Run a streaming request against the local LLM server and confirm canonical events are yielded in the expected state-machine order.
- [ ] Run `LanguageModel(provider="openai-responses", model_name="gpt-4o")` and confirm the Responses API client remains selectable.

### Performance Considerations

- [ ] Confirm the streaming normalizer processes chunks incrementally and does not buffer full content or tool-call streams except accumulated text/arguments required for done/ready events.
- [ ] Confirm `n=1` is the only supported normalization path and additional choices are ignored without unbounded accumulator growth.

## Proposed Changes

### Chat Completions Client

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **Description of change**: Add `OpenAIChatCompletionsClient` next to `OpenAIResponsesClient`, wrapping `AsyncOpenAI.chat.completions.create()` for non-streaming and streaming modes.
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

- **Description of change**: Register `"openai-chat-completions"` to create `OpenAIChatCompletionsClient` and continue registering `"openai-responses"` to create `OpenAIResponsesClient`. The `"openai"` → `"openai-responses"` alias remains in place.
- **Rationale**: Chat Completions gets its own stable identifier; existing `"openai"` users are unaffected.

### Public Exports

#### [MODIFY] `tinycua_sdk/agent/__init__.py`

- **Description of change**: Export `OpenAIChatCompletionsClient` from the agent package if provider-specific clients are exported there.
- **Rationale**: Keeps import behavior consistent with `OpenAIResponsesClient`.

#### [MODIFY] `tinycua_sdk/agent/llm_client.py`

- **Description of change**: Add `OpenAIChatCompletionsClient` to `__all__`.
- **Rationale**: Makes the new provider client an explicit module export.

### Tests

#### [NEW] `tests/unit/test_openai_chat_client.py`

- **Description**: Unit tests for payload construction, non-streaming normalization, streaming content normalization, streaming tool-call accumulation, raw pass-through, error translation, and tool-result continuation.
- **Dependencies**: Mocked `AsyncOpenAI` client and mocked SDK response/chunk objects.

#### [NEW] `tests/integration/test_openai_chat_completions_provider.py`

- **Description**: Integration tests for default registry provider coexistence, alias preservation, and end-to-end mocked client behavior through `LanguageModel(provider="openai-chat-completions")`.
- **Dependencies**: `ProviderRegistry`, `LanguageModel`, `OpenAIChatCompletionsClient`, and `OpenAIResponsesClient`.

#### [MODIFY] `tests/unit/test_llm_client.py`

- **Description of change**: Keep existing Responses API assertions intact; move Chat Completions-specific assertions to the new unit test file unless small import/export checks fit here.
- **Rationale**: Prevent the already large `test_llm_client.py` from becoming a mixed-provider test sink.

#### [MODIFY] `tests/unit/test_provider_registry.py`, `tests/unit/test_provider_switching.py`, `tests/integration/test_provider_switching.py`

- **Description of change**: Update expectations: assert `"openai-chat-completions"` is directly supported and returns `OpenAIChatCompletionsClient`; `"openai"` still resolves to `OpenAIResponsesClient` via alias.
- **Rationale**: The new provider uses a distinct identifier; the existing alias is preserved.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `OpenAIChatCompletionsClient` | New | SDK-backed Chat Completions provider implementing `LLMClient` |
| Chat Completions normalizer | New | Converts `ChatCompletionChunk` deltas into canonical `LLMEvent` types |
| `ChoiceAccumulator` | New | Tracks content, tool calls, finish reason, and usage for choice index 0 |
| `ToolCallAccumulator` | New | Tracks streamed tool-call `id`, `name`, and argument fragments by tool-call index |
| `ProviderRegistry` defaults | Modify | Registers `openai-chat-completions`, `openai`, and `openai-responses` as distinct entries |
| Provider alias map | No change | `openai` → `openai-responses` alias remains in place |
| Agent package exports | Modify | Exposes `OpenAIChatCompletionsClient` where provider clients are exported |

## Data Model Changes

```python
@dataclass
class ChoiceAccumulator:
    index: int
    content_parts: list[str] = field(default_factory=list)
    tool_calls: dict[int, ToolCallAccumulator] = field(default_factory=dict)
    finish_reason: str | None = None
    usage: dict | None = None
    content_done_emitted: bool = False
    started_emitted: bool = False
    done_emitted: bool = False
    ready_emitted: bool = False


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
| `tinycua_sdk.agent.llm_client.OpenAIChatCompletionsClient` | New provider client class |
| `ProviderRegistry.create_client(LanguageModel(provider="openai-chat-completions"))` | Returns `OpenAIChatCompletionsClient` |
| `ProviderRegistry.create_client(LanguageModel(provider="openai"))` | Continues returning `OpenAIResponsesClient` (via alias) |
| `ProviderRegistry.create_client(LanguageModel(provider="openai-responses"))` | Continues returning `OpenAIResponsesClient` |
| `resolve_provider("openai-chat-completions")` | Returns `"openai-chat-completions"` |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `openai` | `>=2.34,<3` | Existing SDK dependency used for `AsyncOpenAI.chat.completions.create()` |

### Internal Dependencies

- [ ] Depends on Stage 1 `LLMClient`, canonical event schema, `OpenAIResponsesClient`, and `ProviderRegistry` work already present.
- [ ] Does not block other features except provider-specific work that assumes `provider="openai-chat-completions"` should resolve to Chat Completions.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reusing Responses payload helpers sends wrong Chat Completions request fields | High | Add Chat-specific payload tests for `messages`, `tools`, `max_tokens`, and tool-result mapping |
| Tool-call deltas produce duplicate `tool_call.ready` events | High | Track emitted state in `ToolCallAccumulator` and assert exactly one ready event per call |
| Alias remains in place — no breaking change for `provider="openai"` users | Low | The `"openai"` → `"openai-responses"` alias is preserved |
| Raw pass-through loses the original SDK object | Medium | Pair canonical events with `RawSseEvent(provider="openai-chat-completions", raw_event=chunk)` through `_yield_events()` following standard one-to-many pairing rules (first canonical gets raw, follow-on canonicals get `raw=None`) |
| Streaming terminal chunks without content omit completion events | Medium | Unit test empty/tool-only terminal chunks and always emit `ResponseCompletedEvent` when `finish_reason` is present |
| OpenAI SDK chunk model variations differ from mocked dictionaries | Medium | Normalize through `model_dump()` when available and write mocks that match SDK field names |
| Multiple choices are ignored for MVP | Low | Explicitly normalize only `choices[0]`, document `n=1` scope, and avoid accumulating other choices |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-19*
