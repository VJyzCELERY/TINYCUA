# Design Document: Agent Convenience API for File Attachments

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-05-22

---

## Overview

This design adds file attachment convenience to `Agent.run()` by extending the `query` parameter to accept `str | list[ContentPart]` and adding an optional `file_attachments: list[FileAttachment] | None = None` parameter. The agent loop constructs the canonical user message dict internally, so callers never need to build `content: list[ContentPart]` message structures by hand. The change is purely additive — existing `agent.run("query")` calls are fully backward compatible.

---

## Architecture

### Component Overview

The change is confined to `Agent.run()` in `agent/agent.py`. No changes to `BaseLoop`, `AgentExecutor`, or provider clients are required because the provider translation layers already support both canonical message shapes (`content: list[ContentPart]` and `content: str` + `attachments`).

```
Caller
  │
  ▼
Agent.run(query, file_attachments, messages, instructions, stream)
  │
  │  ← Constructs user message dict from query + file_attachments
  │
  ▼
BaseLoop.run(agent, messages, tools, override_instructions, stream)
  │
  ▼
Provider Translation (_translate_chat_user_message / _translate_responses_user_message)
  │
  ▼
LLM API
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `Agent.run()` | Modified | Extended `query` type, added `file_attachments` param, message construction logic |
| `Agent.__init__` | None | No changes — `file_attachments` is per-call, not per-agent |
| `BaseLoop` | None | Already accepts `list[dict]` messages with arbitrary shapes |
| `AgentExecutor` | None | No changes to `_call_llm` interface |
| Provider clients | None | Already handle `content: list[ContentPart]` and `attachments` |
| `tinycua_sdk/__init__.py` | Modified | Add `FileAttachment` and `ContentPart` to public exports |
| Test suite | New | `test_agent_file_attachments.py` for unit tests |

---

## Data Model

### New Entities

None. This design reuses the existing `FileAttachment` and `ContentPart` models from `tinycua_sdk.models.attachment` (Phase 1).

### Schema Changes

The user message dict gains an optional `attachments` key when `file_attachments` is provided:

```python
# Before (backward compatible)
{"role": "user", "content": "Hello"}

# After — str query + file_attachments
{"role": "user", "content": "Hello", "attachments": [FileAttachment(...)]}

# After — list[ContentPart] query
{"role": "user", "content": [ContentPart(type="text", text="Hello"), ContentPart(type="file", file=...)]}

# After — list[ContentPart] + file_attachments (merged)
{"role": "user", "content": [ContentPart(type="text", text="Hello"), ContentPart(type="file", file=img1), ContentPart(type="file", file=img2)]}
```

No database or persistent schema changes are involved.

---

## API / Interface Contracts

### Modified: `Agent.run()`

```python
async def run(
    self,
    query: str | list[ContentPart],
    messages: list[dict] | None = None,
    instructions: str | None = None,
    stream: bool = False,
    file_attachments: list[FileAttachment] | None = None,
) -> str | AsyncIterator[dict]:
    """
    Run the agent with a query, optionally including file attachments.

    Args:
        query: The user query — either a plain string or a list of ContentPart
               objects for multimodal input.
        messages: Optional message history to prepend.
        instructions: Optional instructions override.
        stream: If True, returns an async iterator of SDK-normalized stream events.
        file_attachments: Optional list of FileAttachment objects to include
                         with the user message.

    Returns:
        Final response string when stream=False, or an async iterator
        of event dicts when streaming.

    Raises:
        TypeError: If file_attachments contains non-FileAttachment items.
    """
```

### Message Construction Logic

```
if query is str:
    if file_attachments is None or empty:
        user_msg = {"role": "user", "content": query}
    else:
        user_msg = {
            "role": "user",
            "content": query,
            "attachments": file_attachments,
        }
elif query is list[ContentPart]:
    if file_attachments is None or empty:
        user_msg = {"role": "user", "content": query}
    else:
        merged = list(query) + [ContentPart(type="file", file=a) for a in file_attachments]
        user_msg = {"role": "user", "content": merged}
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `file_attachments` contains non-`FileAttachment` item | `TypeError` | Raised at call time before message construction |
| `query` is neither `str` nor `list[ContentPart]` | `TypeError` | Rejects unsupported types (e.g., `int`, `dict`, `None`) |
| `query` is `list[ContentPart]` containing non-`ContentPart` items | `TypeError` | Validates each item is a `ContentPart` instance before message construction |
| Empty `query=[]` (empty `list[ContentPart]`) | `TypeError` | Rejected at call time — an empty ContentPart list is semantically ambiguous and passes provider validation vacuously. Rejecting at the agent boundary produces a clear, consistent error for all callers. |
| Empty `file_attachments=[]` | No-op | Treated same as `None` |
| Empty `query=""` with `file_attachments` | Valid | Agent-level message: `content: ""` + `attachments` key. Providers may omit the empty text part in API-specific payloads. |
| `stream` is not `bool` | `TypeError` | Existing behavior preserved |

---

## Implementation Phases

### Phase 1 — MVP

- [x] Extend `Agent.run()` signature with `file_attachments` parameter and `query: str | list[ContentPart]`
- [x] Implement message construction logic in `Agent.run()`
- [x] Add `FileAttachment` and `ContentPart` to `tinycua_sdk/__init__.py` public exports
- [x] Write unit tests for all message construction paths
- [x] Write unit tests for validation errors (invalid types in `file_attachments`)
- [x] Write unit tests for backward compatibility (existing `str` query, no attachments)
- [x] Verify streaming mode works with `file_attachments` via unit test

### Phase 2 — Integration (post-MVP)

- [ ] Add integration test with mock LLM: end-to-end agent run with file attachment
- [ ] Add integration test with mock LLM: end-to-end streaming with file attachment

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use `file_attachments: list[FileAttachment] | None = None` rather than `*attachments: FileAttachment` (variadic positional).
   - **Reason**: Variadic positional arguments would make it easy to accidentally pass a single `FileAttachment` where a `str` kwarg is expected after `query`. A list parameter is explicit, type-safe, and matches the `attachments` key in message dicts from Phases 2–3.
   - **Alternatives Considered**: `*attachments: FileAttachment` — rejected because it conflicts with `**kwargs` style and makes the call signature harder to read.

2. **Decision**: When `query: list[ContentPart]` and `file_attachments` are both provided, merge them into a single `list[ContentPart]` rather than using the `attachments` key.
   - **Reason**: The `attachments` key is a convenience shorthand for `str + files`. When the caller already uses `list[ContentPart]`, they are using the explicit multimodal form. Merging `file_attachments` into the content list gives the caller predictable ordering. Using the `attachments` key would append files after the explicit parts anyway, so we pre-merge and skip the redundant key.
   - **Alternatives Considered**: Use `attachments` key always regardless of `query` type — rejected because `list[ContentPart]` content + `attachments` key is redundant (the file parts are already in the list, and also duplicated in `attachments`).

3. **Decision**: Validate `file_attachments` items at `Agent.run()` call time, raising `TypeError` for non-`FileAttachment` items.
   - **Reason**: Early validation prevents confusing errors deep in provider translation. The provider code validates `ContentPart` structure, but catching unsupported types at the agent boundary gives clearer error messages.
   - **Alternatives Considered**: Defer validation to provider layer — rejected because errors would be harder to trace back to the caller.

4. **Decision**: When `query` is `str` and `file_attachments` is provided, use the `content: str` + `attachments` key shape rather than constructing `list[ContentPart]` inside `Agent.run()`.
   - **Reason**: Provider translation layers already handle the `content: str` + `attachments` shape natively (both Chat Completions `_translate_chat_user_message` and Responses `_translate_responses_user_message`). Reconstructing `list[ContentPart]` from `str` + `attachments` would add unnecessary intermediate objects. The `attachments` key is the canonical "basic message + attachments" shape from the issue spec.
   - **Alternatives Considered**: Always convert to `list[ContentPart]` — rejected because it adds unnecessary object construction and loses the simpler `str` + `attachments` shape that provider layers already optimize for.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Breaking backward compatibility in `Agent.run()` | Low | High | Extensive backward-compatibility tests; `query: str` without `file_attachments` must produce identical message dicts |
| Provider translation bug when both `content: list[ContentPart]` and `attachments` key present | Low | Medium | Never produce both — use either `content: str` + `attachments` OR `content: list[ContentPart]` (no `attachments` key) |
| `FileAttachment` not importable from top-level `tinycua_sdk` | Low | Low | Add to `__init__.py` exports in Phase 1 |
| Streaming breaks with attachments due to async upload in Responses API | Medium | High | The Responses API's `_translate_responses_user_message` is already async and handles uploads; Agent.run() stream path delegates to `BaseLoop.run()` which calls `_call_llm` — the same async upload path works in streaming |

---

## References

- Spec: `./spec.md`
- Parent issue: [Issue #46 — Implementation: SDK-wide File Attachment Support](https://github.com/VJyzCELERY/TINYCUA/issues/46)
- Feature request: [Issue #45 — Feature Request: SDK-wide File Attachment Support](https://github.com/VJyzCELERY/TINYCUA/issues/45)
- Phase 1 implementation: `tinycua_sdk/models/attachment.py` (`FileAttachment`, `ContentPart`)
- Phase 2 implementation: `tinycua_sdk/providers/open_ai_chat_completions.py` (`_translate_chat_user_message`)
- Phase 3 implementation: `tinycua_sdk/providers/open_ai_responses.py` (`_translate_responses_user_message`)