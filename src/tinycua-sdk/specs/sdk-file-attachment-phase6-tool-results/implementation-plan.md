# Implementation: Phase 6 — Tool Result File Support

Enable SDK tools to return canonical file attachments to the LLM on the next turn. This closes the last gap in SDK-wide file attachment support by preserving `ToolResultMessage.content: list[ContentPart]` and `ToolResultMessage.attachments` through the agent loop and provider translators.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: Medium (3-5 days)

## Environment Pre-requisites

### Configuration

- [x] **None** — unit tests and mocked integration tests require no external API keys.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| None | No | N/A | N/A |

### Data / Fixtures

- [x] **None** — tests should construct small in-memory/base64 attachments with `FileAttachment.from_bytes()`.

### Access / Permissions

- [x] **None** — no special access required for automated tests.

### Developer Tooling

- [x] **Runtime**: Python 3.11 via uv
- [x] **Package manager**: uv

---

## Success Criteria — Integration Tests (TDD First)

Write these tests before implementation. They should fail on the current branch because tool results are stringified and provider translators do not translate tool-result attachments.

```python
# Test file: tests/integration/test_tool_result_attachments.py
"""Integration tests for tool-result file attachment handoff."""

import pytest

from tinycua_sdk.agent.loop import BaseLoop
from tinycua_sdk.models import ContentPart, FileAttachment


class RecordingAgent:
    """Minimal agent double that records second-turn messages."""

    instructions = "Use tools when needed."
    skills = []

    def __init__(self, first_response, second_response):
        from types import SimpleNamespace

        self.policy = SimpleNamespace(max_tool_calls=5)
        self.is_cancelled = False
        self._cancel_event = None
        self.calls = []
        self._responses = [first_response, second_response]
        self.tool_permissions = {}

    async def _call_llm(self, messages, tools, stream=False):
        self.calls.append(messages)
        response = self._responses.pop(0)
        if stream:
            async def _gen():
                for tc in response.get("tool_calls", []):
                    yield {
                        "type": "tool_call.ready",
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "arguments": tc.get("arguments", "{}"),
                    }
                if response.get("content"):
                    yield {
                        "type": "response.output_text.delta",
                        "delta": response["content"],
                    }
                yield {
                    "type": "response.completed",
                    "finish_reason": "tool_calls" if response.get("tool_calls") else "stop",
                    "response": {"usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
                }
            return _gen()
        return response

# NOTE: RecordingAgent does not implement tool-execution methods (_execute_tool, get_tools, etc.)
# because BaseLoop.run() dispatches tool execution via ToolExecutor.execute() which calls tool.invoke()
# on tools from the provided tools list. The agent double only needs to supply LLM responses to drive the loop.


class Tool:
    name = "make_image"
    description = "Generate an image."
    parameters = {"type": "object", "properties": {}}

    def invoke(self, **kwargs):
        attachment = FileAttachment.from_bytes(
            b"fake-png-bytes",  # intentionally invalid — no image validation in mocked test paths
            mime_type="image/png",
            filename="generated.png",
        )
        return {
            "content": [
                ContentPart(type="text", text="Generated image."),
                ContentPart(type="file", file=attachment),
            ]
        }


@pytest.mark.asyncio
async def test_non_streaming_tool_result_file_reaches_second_llm_turn():
    agent = RecordingAgent(
        first_response={
            "content": "",
            "tool_calls": [{"id": "call_1", "name": "make_image", "arguments": "{}"}],
        },
        second_response={"content": "The image is visible."},
    )

    result = await BaseLoop(max_iterations=2).run(agent, [], [Tool()])

    assert result == "The image is visible."
    second_turn = agent.calls[1]
    tool_result = next(msg for msg in second_turn if msg["role"] == "tool_result")
    assert tool_result["call_id"] == "call_1"
    assert isinstance(tool_result["content"], list)
    assert tool_result["content"][1].type == "file"


@pytest.mark.asyncio
async def test_non_streaming_tool_result_attachments_shape_reaches_second_llm_turn():
    attachment = FileAttachment.from_bytes(
        b"fake-png-bytes",  # intentionally invalid — no image validation in mocked test paths
        mime_type="image/png",
        filename="generated.png",
    )

    class AttachmentTool(Tool):
        def invoke(self, **kwargs):
            return {"content": "Generated image.", "attachments": [attachment]}

    agent = RecordingAgent(
        first_response={
            "content": "",
            "tool_calls": [{"id": "call_1", "name": "make_image", "arguments": "{}"}],
        },
        second_response={"content": "The image is visible."},
    )

    await BaseLoop(max_iterations=2).run(agent, [], [AttachmentTool()])

    second_turn = agent.calls[1]
    tool_result = next(msg for msg in second_turn if msg["role"] == "tool_result")
    assert tool_result["content"] == "Generated image."
    assert tool_result["attachments"] == [attachment]


@pytest.mark.asyncio
async def test_streaming_tool_result_file_reaches_second_llm_turn():
    agent = RecordingAgent(
        first_response={
            "content": "",
            "tool_calls": [{"id": "call_1", "name": "make_image", "arguments": "{}"}],
        },
        second_response={"content": "The image is visible."},
    )

    stream_result = BaseLoop(max_iterations=2).run(agent, [], [Tool()], stream=True)
    async for _ in stream_result:
        pass  # consume stream — assertions target agent.calls below

    second_turn = agent.calls[1]
    tool_result = next(msg for msg in second_turn if msg["role"] == "tool_result")
    assert tool_result["call_id"] == "call_1"
    assert isinstance(tool_result["content"], list)
    assert tool_result["content"][1].type == "file"
```

```python
# Test file: tests/unit/test_openai_chat_client.py
# Note: These tests call the private _translate_chat_messages() method directly.
# If its signature changes during implementation, update the tests accordingly.

from tinycua_sdk.agent.llm_model import LanguageModel


@pytest.mark.asyncio
async def test_chat_completions_translates_tool_result_attachments_to_tool_content_parts():
    attachment = FileAttachment.from_bytes(b"img", mime_type="image/png", filename="img.png")
    client = OpenAIChatCompletionsClient(LanguageModel(model_name="gpt-test"))
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "make_image", "arguments": "{}"}}],
        },
        {
            "role": "tool_result",
            "call_id": "call_1",
            "content": "Generated image.",
            "attachments": [attachment],
        },
    ]

    translated = await client._translate_chat_messages(messages)

    tool_msgs = [m for m in translated if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    tool_msg = tool_msgs[0]
    assert tool_msg["tool_call_id"] == "call_1"
    assert tool_msg["content"][0] == {"type": "text", "text": "Generated image."}
    assert tool_msg["content"][1]["type"] == "image_url"
```

```python
# Test file: tests/unit/test_llm_client.py
# Note: These tests call the private _translate_responses_input() method directly.
# If its signature changes during implementation, update the tests accordingly.

from tinycua_sdk.agent.llm_model import LanguageModel


@pytest.mark.asyncio
async def test_responses_translates_tool_result_content_parts_to_function_call_output():
    attachment = FileAttachment.from_bytes(b"img", mime_type="image/png", filename="img.png")
    client = OpenAIResponsesClient(LanguageModel(model_name="gpt-test"))
    messages = [
        {
            "role": "tool_result",
            "call_id": "call_1",
            "content": [
                ContentPart(type="text", text="Generated image."),
                ContentPart(type="file", file=attachment),
            ],
        }
    ]

    translated = await client._translate_responses_input(messages)

    output = translated[0]
    assert output["type"] == "function_call_output"
    assert output["call_id"] == "call_1"
    assert output["output"][0] == {"type": "input_text", "text": "Generated image."}
    assert output["output"][1]["type"] == "input_image"
```

```python
# Test file: tests/unit/test_loop.py — normalization edge cases

# normalize_tool_result is exported from tinycua_sdk.agent.loop for direct testing:
# from tinycua_sdk.agent.loop import normalize_tool_result

# ---- Detection rule 1: non-empty list[ContentPart] → structured multipart ----

def test_normalize_structured_multipart_content():
    """Rule 1: Non-empty list of ContentParts is treated as structured multipart."""
    tool_result = {"content": [ContentPart(type="text", text="hello")]}
    result = normalize_tool_result("call_1", tool_result)
    assert result["role"] == "tool_result"
    assert result["call_id"] == "call_1"
    assert result["content"] == tool_result["content"]


# ---- Detection rule 2: string content + attachments → structured with message-level attachments ----

def test_normalize_string_with_attachments():
    """Rule 2: String content plus attachments list yields structured message."""
    attachment = FileAttachment.from_bytes(b"data", mime_type="text/plain", filename="f.txt")
    tool_result = {"content": "Generated file.", "attachments": [attachment]}
    result = normalize_tool_result("call_1", tool_result)
    assert result["content"] == "Generated file."
    assert result["attachments"] == [attachment]


# ---- Detection rule 3: pre-formed canonical tool_result message ----

def test_normalize_pre_formed_canonical_message():
    """Rule 3: Tool result with role='tool_result' is treated as canonical."""
    tool_result = {
        "role": "tool_result",
        "call_id": "call_abc",
        "content": "Canonical content.",
    }
    result = normalize_tool_result("call_1", tool_result)
    assert result["role"] == "tool_result"
    assert result["call_id"] == "call_1"
    assert result["content"] == "Canonical content."


# ---- Detection rule 4: unrecognized shape → legacy str(tool_result) fallback ----

@pytest.mark.parametrize("legacy_value", [
    "plain string",
    42,
    {"arbitrary": "dict", "nested": {"key": "val"}},
    None,
])
def test_normalize_legacy_falls_back_to_string(legacy_value):
    """Rule 4: Unrecognized tool result shapes fall back to str(tool_result)."""
    result = normalize_tool_result("call_1", legacy_value)
    assert result["content"] == str(legacy_value)
    assert "attachments" not in result


# ---- Detection rule 5: empty content list → ValueError ----

@pytest.mark.parametrize("empty_content", [[], list()])
def test_normalize_rejects_empty_content_part_list(empty_content):
    tool_result = {"content": empty_content}
    with pytest.raises(ValueError, match="empty"):
        normalize_tool_result("call_1", tool_result)
```

```python
# Test file: tests/unit/test_openai_chat_client.py — cache reuse

from tinycua_sdk.agent.llm_model import LanguageModel


@pytest.mark.asyncio
async def test_chat_completions_tool_result_cache_reuse():
    """Repeated tool-returned non-image files reuse existing upload cache."""
    attachment = FileAttachment.from_bytes(b"file-content", filename="report.pdf")
    upload_calls = []

    async def _upload_fn(att):
        upload_calls.append(att.filename)
        return "file-abc123"

    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "make_file", "arguments": "{}"}}],
        },
        {
            "role": "tool_result",
            "call_id": "call_1",
            "content": "Here is the file.",
            "attachments": [attachment],
        },
    ]

    client = OpenAIChatCompletionsClient(LanguageModel(model_name="gpt-test"))
    from unittest.mock import AsyncMock

    mock_upload_fn = AsyncMock(side_effect=_upload_fn)
    assert not attachment.file_id

    await client._translate_chat_messages(messages, _upload_fn=mock_upload_fn)
    assert mock_upload_fn.await_count == 1
    assert attachment.file_id == "file-abc123"

    await client._translate_chat_messages(messages, _upload_fn=mock_upload_fn)
    assert mock_upload_fn.await_count == 1  # cache hit — no additional upload
```

### Key Test Scenarios

- [ ] **Non-streaming tool-generated file handoff**: proves the primary user flow works through the default agent loop.
- [ ] **Streaming tool-generated file handoff**: proves streaming mode preserves the same structured tool result.
- [ ] **Provider translation**: proves Chat Completions and Responses receive provider-native content parts rather than stringified attachments.
- [ ] **Backward compatibility**: proves legacy string/dict/exception tool results still behave as before.
- [ ] **Empty ContentPart rejection**: proves empty `list[ContentPart]` tool results raise a clear `ValueError`, matching user message behavior.
- [ ] **Cache reuse for tool-result files**: proves repeated tool-returned non-image files hit the existing upload cache.

## Verification Plan

### Automated Tests

- [ ] Integration tests: `cd src/tinycua-sdk && uv run pytest tests/integration/test_tool_result_attachments.py`
- [ ] Loop unit tests: `cd src/tinycua-sdk && uv run pytest tests/unit/test_loop.py tests/unit/test_loop_custom.py`
- [ ] Provider unit tests: `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py tests/unit/test_llm_client.py`
- [ ] Full suite: `cd src/tinycua-sdk && uv run pytest`

### Manual Verification

- [ ] Optional real-provider smoke test with a vision-capable model where a tool generates a small PNG and the LLM describes it.

### Performance Considerations

- [ ] No new large-file handling path should be introduced; streaming and upload behavior must reuse Phase 5 attachment translation.
- [ ] Verify repeated tool-returned non-image files hit the existing upload cache in provider tests where upload is required.

## Proposed Changes

### Agent Loop

#### [MODIFY] `tinycua_sdk/agent/loop.py` → Tasks 7, 7a-7e, 8, 9

- **Add tool result normalizer** (Task 7, 7a-7e): Introduce an internal helper that converts supported structured tool return values into canonical `tool_result` messages and falls back to stringification otherwise.
- **Update non-streaming path** (Task 8): Replace direct `"content": str(tool_result)` construction in `process_tool_calls()` with the shared normalizer.
- **Update streaming path** (Task 9): Replace the corresponding direct string construction in `process_stream_tool_calls()` with the same normalizer.
- **Rationale**: Ensures sync and streaming paths preserve file attachments identically.

#### [MODIFY] `tinycua_sdk/agent/events.py` → Task 12

- **Clarify message contract**: Ensure `ToolResultMessage` documentation and exports accurately describe `attachments` and `list[ContentPart]` support.
- **Rationale**: Keeps canonical type docs aligned with behavior.

### Provider Translation

#### [MODIFY] `tinycua_sdk/providers/open_ai_chat_completions.py` → Task 10

- **Add structured tool-result translator**: Mirror `_translate_chat_user_message()` for `role: tool_result`, outputting `role: tool` and `tool_call_id`.
- **Wire into batch handling**: When `_translate_chat_messages()` processes tool-result batches, translate each tool result through the new helper instead of copying raw `content`.
- **Rationale**: Preserves existing assistant `tool_calls` ordering while enabling multimodal tool output.

#### [MODIFY] `tinycua_sdk/providers/open_ai_responses.py` → Task 11

- **Add async structured tool-result translator**: Translate plain output, content-part lists, and message-level attachments to `function_call_output`.
- **Wire into `_translate_responses_input()`**: Route tool-result messages through the async helper so uploads/downloads can be awaited.
- **Keep `_translate_messages()` backward compatible**: `_translate_messages()` remains synchronous for plain content-only tool results; callers that require attachment translation must use the async `_translate_responses_input()` path.
- **Rationale**: Responses attachment translation may require async upload/download behavior.

### Tests

#### [NEW] `tests/integration/test_tool_result_attachments.py`

- **Description**: Add mocked end-to-end tests for tool-generated image handoff in non-streaming and streaming loops.
- **Dependencies**: `BaseLoop`, `FileAttachment`, `ContentPart`, tool doubles, agent doubles.

#### [MODIFY] `tests/unit/test_loop.py`

- **Description**: Add tests for normalization of explicit multipart content, basic attachments shape, canonical tool-result dicts, and legacy fallback.
- **Rationale**: Locks down the most important backward-compatibility boundary.

#### [MODIFY] `tests/unit/test_loop_custom.py`

- **Description**: Add or update tests to ensure public loop helper methods preserve structured tool results for custom loops.
- **Rationale**: Prevents regressions for custom loop subclasses.

#### [MODIFY] `tests/unit/test_openai_chat_client.py`

- **Description**: Add Chat Completions tool-result translation tests for `ContentPart` and `attachments` forms, plus legacy string output.
- **Rationale**: Verifies exact provider payload shape.

#### [MODIFY] `tests/unit/test_llm_client.py`

- **Description**: Add Responses tool-result translation tests for `ContentPart` and `attachments` forms, plus legacy string output.
- **Rationale**: Verifies async Responses translation and provider-native output shape.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| Agent loop | Modify | Shared normalization for structured tool return values |
| Chat Completions provider | Modify | Multimodal tool-result content translation |
| Responses provider | Modify | Async multimodal function-call output translation |
| Tests | New/Modify | TDD coverage for loop, provider, and mocked integration flows |

## Data Model Changes

No new public data models. Existing `ToolResultMessage` structured fields become fully honored at runtime.

```python
ToolResultMessage:
    role: "tool_result"
    call_id: str
    content: str | list[ContentPart]
    attachments?: list[FileAttachment]
```

## API Changes

No HTTP endpoints are involved.

### Modified Interfaces

| Interface | Change |
|-----------|--------|
| Tool return values | Tools may now return supported canonical dict shapes with `content` and optional `attachments` to preserve files. |
| Provider translators | Tool-result messages may contain structured content requiring async translation. |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| None | N/A | No new external dependencies |

### Internal Dependencies

- Depends on: Phase 1–5 attachment models, provider translation, upload cache, and streaming upload support (already merged).
- Blocks: final closure of issue #46 Phase 6 acceptance criteria.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Provider rejects multimodal tool output payloads | High | Write provider payload tests first; surface provider errors clearly; keep legacy plain string path unchanged. |
| Existing dict-returning tools change behavior | Medium | Only treat explicit supported shapes as structured; all other dicts fall back to `str(...)`. |
| Sync and streaming paths diverge | High | Use one shared normalization helper and test both paths. |
| Responses translation needs async behavior from currently sync helper | Medium | Route tool results through `_translate_responses_input()` async path; keep sync `_translate_messages()` for plain fallback where needed. |
| Upload/cache behavior regresses | Medium | Reuse existing attachment translation helpers and run Phase 5 upload/cache tests. |

---

*Generated from spec.md and design.md. Paired with task.md.*
*Last updated: 2026-05-26*
