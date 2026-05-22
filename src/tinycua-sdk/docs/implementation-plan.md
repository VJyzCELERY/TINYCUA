# Implementation: Agent Convenience API for File Attachments

Extends `Agent.run()` to accept `str | list[ContentPart]` for the `query` parameter and an optional `file_attachments: list[FileAttachment] | None = None` parameter, so callers can attach files without manually constructing message dicts. Provider translation layers already support both canonical message shapes, so this change is confined to the `Agent.run()` entry point and public exports.

## Context

- **Spec Reference**: `./spec.md` — Agent Convenience API for File Attachments
- **Design Reference**: `./design.md` — Phase 4 message construction and API contracts
- **Priority**: P1 — unblocks ergonomic file attachment use in the SDK
- **Estimated Effort**: S — single module change + tests, no architectural changes

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
- [x] **Additional CLI tools**: pytest
- [x] **None** — no special tooling beyond the SDK's existing setup

---

## Success Criteria — Unit Tests (TDD First)

```python
# Test file: tests/unit/test_agent_file_attachments.py
"""Unit tests for Agent.run() file attachment convenience API."""


import pytest
from tinycua_sdk import Agent, BaseLoop, LanguageModel, FileAttachment, ContentPart


class TestAgentRunFileAttachments:
    """Test Agent.run() with file_attachments parameter."""

    @pytest.mark.asyncio
    async def test_run_str_query_with_file_attachments(self):
        """Verify str query + file_attachments produces content: str + attachments key."""
        agent = Agent(llm_model=LanguageModel())
        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")

        await agent.run("Describe this", file_attachments=[img])
        user_msg = captured["messages"][-1]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "Describe this"
        assert user_msg["attachments"] == [img]

    @pytest.mark.asyncio
    async def test_run_empty_query_with_file_attachments(self):
        """Verify empty str query + file_attachments produces content: '' + attachments key."""
        agent = Agent(llm_model=LanguageModel())
        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")

        await agent.run("", file_attachments=[img])
        user_msg = captured["messages"][-1]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == ""
        assert user_msg["attachments"] == [img]

    @pytest.mark.asyncio
    async def test_run_str_query_without_file_attachments(self):
        """Verify backward compatibility: str query with no attachments unchanged."""
        agent = Agent(llm_model=LanguageModel())
        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        await agent.run("Hello")
        assert captured["messages"][-1] == {"role": "user", "content": "Hello"}

    @pytest.mark.asyncio
    async def test_run_content_parts_query_without_attachments(self):
        """Verify list[ContentPart] query uses content parts directly."""
        agent = Agent(llm_model=LanguageModel())
        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")
        parts = [ContentPart(type="text", text="Look at this"), ContentPart(type="file", file=img)]

        await agent.run(parts)
        user_msg = captured["messages"][-1]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == parts
        assert "attachments" not in user_msg

    @pytest.mark.asyncio
    async def test_run_content_parts_query_with_attachments_merges(self):
        """Verify list[ContentPart] query + file_attachments merges into single list."""
        agent = Agent(llm_model=LanguageModel())
        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img1 = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")
        img2 = FileAttachment(data="AQIDBA==", mime_type="image/jpeg")
        parts = [ContentPart(type="text", text="Compare these")]

        await agent.run(parts, file_attachments=[img1, img2])
        user_msg = captured["messages"][-1]
        assert user_msg["role"] == "user"
        assert len(user_msg["content"]) == 3
        assert user_msg["content"][0] == ContentPart(type="text", text="Compare these")
        assert user_msg["content"][1] == ContentPart(type="file", file=img1)
        assert user_msg["content"][2] == ContentPart(type="file", file=img2)
        assert "attachments" not in user_msg

    @pytest.mark.asyncio
    async def test_run_empty_file_attachments_is_noop(self):
        """Verify file_attachments=[] behaves same as None."""
        agent = Agent(llm_model=LanguageModel())
        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        await agent.run("Hello", file_attachments=[])
        assert captured["messages"][-1] == {"role": "user", "content": "Hello"}

    @pytest.mark.asyncio
    async def test_run_invalid_file_attachments_raises_type_error(self):
        """Verify TypeError for non-FileAttachment items in file_attachments."""
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(TypeError, match="file_attachments"):
            await agent.run("Hello", file_attachments=["not_a_file_attachment"])

    @pytest.mark.asyncio
    async def test_run_none_in_file_attachments_raises_type_error(self):
        """Verify TypeError for None items in file_attachments."""
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(TypeError, match="file_attachments"):
            await agent.run("Hello", file_attachments=[None])

    @pytest.mark.asyncio
    async def test_run_invalid_query_type_raises_type_error(self):
        """Verify TypeError when query is neither str nor list[ContentPart]."""
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(TypeError, match="query"):
            await agent.run(42)

    @pytest.mark.asyncio
    async def test_run_content_parts_query_rejects_non_content_part_items(self):
        """Verify TypeError when list[ContentPart] query contains non-ContentPart items."""
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(TypeError, match="ContentPart"):
            await agent.run(["not_a_content_part", "also_invalid"])

    @pytest.mark.asyncio
    async def test_run_stream_with_file_attachments(self):
        """Verify streaming works with file_attachments and attachments reach the request."""
        agent = Agent(llm_model=LanguageModel())
        captured = {}

        async def fake_stream(messages, tools, stream=False):
            captured["messages"] = messages
            captured["stream"] = stream
            async def _gen():
                yield {"type": "response.output_text.delta", "delta": "Hi", "index": 0}

            return _gen()

        agent._call_llm = fake_stream
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")

        stream_iter = await agent.run("Describe", file_attachments=[img], stream=True)
        events = [e async for e in stream_iter]
        assert any(e["type"] == "response.output_text.delta" for e in events)
        assert captured["stream"] is True
        assert captured["messages"][-1]["content"] == "Describe"
        assert captured["messages"][-1]["attachments"] == [img]

    @pytest.mark.asyncio
    async def test_run_preserves_message_history_with_attachments(self):
        """Verify message history is preserved when using file_attachments."""
        agent = Agent(llm_model=LanguageModel())
        captured = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")
        history = [
            {"role": "user", "content": "Previous"},
            {"role": "assistant", "content": "Previous reply"},
        ]

        await agent.run("New query", messages=history, file_attachments=[img])
        assert captured["messages"][0] == history[0]
        assert captured["messages"][1] == history[1]
        assert captured["messages"][2]["role"] == "user"
        assert captured["messages"][2]["content"] == "New query"
```

### Key Test Scenarios

- [x] **Scenario 1**: `str` query + `file_attachments` produces `content: str` + `attachments` key shape
- [x] **Scenario 2**: Empty `str` query (`""`) + `file_attachments` produces `content: ""` + `attachments` key shape
- [x] **Scenario 3**: `str` query without `file_attachments` is backward compatible (identical message dict)
- [x] **Scenario 4**: `list[ContentPart]` query uses parts directly, no `attachments` key
- [x] **Scenario 5**: `list[ContentPart]` query + `file_attachments` merges into single list
- [x] **Scenario 6**: Empty `file_attachments=[]` is treated same as `None` (no-op)
- [x] **Scenario 7**: Invalid items in `file_attachments` (non-FileAttachment, None) raise `TypeError`
- [x] **Scenario 8**: Streaming mode works with `file_attachments`, attachments reach the request path
- [x] **Scenario 9**: Message history is preserved when using `file_attachments`
- [x] **Scenario 10**: Invalid `query` type (neither `str` nor `list[ContentPart]`) raises `TypeError`
- [x] **Scenario 11**: `list[ContentPart]` query containing non-`ContentPart` items raises `TypeError`

> **Phase 4 scope**: The tests above verify that `Agent.run` constructs canonical SDK messages correctly. Provider end-to-end verification (Chat Completions + Responses integration) is covered by prior phase tests in `tests/integration/`. The Phase 4 implementation is complete when these unit tests pass.

## Verification Plan

### Automated Tests

- [ ] Unit tests for `Agent.run()` message construction (all paths) — tests above
- [ ] Unit tests for validation errors (`TypeError` for invalid `file_attachments` items and invalid `query` types)
- [ ] Unit tests for backward compatibility (existing `str` query calls unchanged)
- [ ] Unit tests for streaming mode with `file_attachments`
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua-sdk && uv run pytest tests/unit/`

### Manual Verification

- [ ] Run an agent with a real OpenAI API key and a local image file, verify response describes the image

### Performance Considerations

- [ ] No performance concerns — message construction is a single dict creation with no I/O

## Proposed Changes

### Agent Module

#### MODIFY `tinycua_sdk/agent/agent.py`

- **Extend `Agent.run()` signature**: Add `query: str | list[ContentPart]` union type and `file_attachments: list[FileAttachment] | None = None` parameter
- **Add message construction logic**: Build user message dict based on query type and file_attachments presence, following the design document's decision tree:
  - `str` query without attachments → `{"role": "user", "content": query}` (backward compatible)
  - `str` query with attachments → `{"role": "user", "content": query, "attachments": file_attachments}`
  - `list[ContentPart]` query without attachments → `{"role": "user", "content": query}`
  - `list[ContentPart]` query with attachments → merged `{"role": "user", "content": merged_parts}`
- **Add validation**: Raise `TypeError` for non-`FileAttachment` items or `None` in `file_attachments`, and for invalid `query` types (non-str, non-list, or list items not `ContentPart`)
- **Add import**: Import `ContentPart` and `FileAttachment` from `tinycua_sdk.models.attachment`
- **Rationale**: This is the only entry point callers use; all message shaping happens here before passing to `BaseLoop.run()`

### Public API

#### MODIFY `tinycua_sdk/__init__.py`

- **Add `FileAttachment` and `ContentPart` to public exports**: Add import and `__all__` entry so callers can do `from tinycua_sdk import FileAttachment, ContentPart`
- **Rationale**: The spec's primary scenario shows `from tinycua_sdk import Agent, FileAttachment`; both must be importable from top-level

### Test Suite

#### NEW `tests/unit/test_agent_file_attachments.py`

- **All test scenarios from Success Criteria above**: Unit tests for every message construction path, validation, backward compatibility, and streaming
- **Rationale**: This is a new feature touchpoint on `Agent.run()`, so dedicated test file keeps concerns separate

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `Agent.run()` | Modify | Extended signature and message construction logic |
| `tinycua_sdk/__init__.py` | Modify | Add `FileAttachment` and `ContentPart` to exports |
| `test_agent_file_attachments.py` | New | Unit tests for file attachment convenience API |

No changes to `BaseLoop`, `AgentExecutor`, or provider clients — they already support both message shapes.

## Data Model Changes

No new entities. Reuses existing `FileAttachment` and `ContentPart` from `tinycua_sdk.models.attachment` (Phase 1).

## API Changes

### Modified Interface

| Method | Change | Description |
|--------|--------|-------------|
| `Agent.run()` | Extended signature | `query: str` → `query: str \| list[ContentPart]`, added `file_attachments: list[FileAttachment] \| None = None` |
| `Agent.run()` | New behavior | Constructs user message dict from `query` + `file_attachments` before passing to `BaseLoop` |
| `tinycua_sdk.__init__` | New exports | `FileAttachment` and `ContentPart` added to `__all__` |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | existing | `FileAttachment` and `ContentPart` already use Pydantic BaseModel |

### Internal Dependencies

- [x] Depends on Phase 1 (`FileAttachment`, `ContentPart` models) — already complete
- [x] Depends on Phase 2 (Chat Completions `_translate_chat_user_message`) — already complete
- [x] Depends on Phase 3 (Responses `_translate_responses_user_message`) — already complete
- [ ] Blocks Phase 5 (file upload caching) and Phase 6 (tool-result file support) — planned future work

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking backward compatibility in `Agent.run()` | High | Extensive backward-compatibility tests; `query: str` without `file_attachments` must produce identical message dicts |
| `content: list[ContentPart]` + `attachments` key both present | Medium | Never produce both — use either `content: str` + `attachments` OR `content: list[ContentPart]` (no `attachments` key) |
| `FileAttachment` not importable from top-level | Low | Add to `__init__.py` exports in Phase 1 of this plan |
| Streaming breaks with attachments due to async upload in Responses API | Medium | Responses API `_translate_responses_user_message` is already async; `Agent.run()` stream path delegates to `BaseLoop.run()` which calls `_call_llm` — the same async path works |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-22*