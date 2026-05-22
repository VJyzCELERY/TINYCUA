# Feature Specification: Agent Convenience API for File Attachments

**Status**: Draft
**Created**: 2026-05-22
**Last Updated**: 2026-05-22
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

- **Goals**: Provide a convenient, high-level API on `Agent.run()` so callers can attach files to agent queries without manually constructing `list[ContentPart]` message dicts. Users should be able to call `agent.run("Describe this", file_attachments=[attachment])` and have the SDK wire the attachments through the agent loop and into the correct provider translation layer.
- **Gaps**: Today, `Agent.run()` only accepts `query: str`. To send a file attachment, a caller must manually build a message dict with `content: list[ContentPart]` or `content: str` + `attachments: list[FileAttachment]`, then pass it via the `messages` parameter. This is verbose, error-prone, and forces users to understand internal message structure before they can use file attachments.
- **Non-Goals**: This spec does NOT cover provider-side file upload caching (Phase 5), tool-result file support (Phase 6), or any changes to provider translation layers beyond what is already in place. Provider translation for both canonical message shapes (Phases 2–3) is assumed to be complete.
- **Constraints**:
  - Must maintain full backward compatibility: existing `Agent.run("query")` calls must work unchanged.
  - Must work with both streaming and non-streaming modes.
  - Must support both OpenAI Chat Completions and Responses API providers.
  - The `query` parameter is extended to accept `str | list[ContentPart]`, matching the dual canonical form from Phase 1.
  - The new `file_attachments` parameter is additive and optional.

---

## User Scenarios & Testing

### Primary Scenario

A user wants to send an image to a vision model through the agent:

```python
from tinycua_sdk import Agent, FileAttachment

agent = Agent(llm_model=LanguageModel(model_name="gpt-4o"))
attachment = FileAttachment.from_path("photo.png")
result = await agent.run("Describe this image", file_attachments=[attachment])
```

The agent constructs the appropriate user message behind the scenes and routes it through the provider translation layer.

### Acceptance Scenarios

1. **Given** an agent with no prior messages, **When** `agent.run("Hello", file_attachments=[img])` is called, **Then** the resulting user message contains both the text part and the file attachment.
2. **Given** an agent, **When** `agent.run(query=[ContentPart(type="text", text="Hello"), ContentPart(type="file", file=img)])` is called, **Then** the resulting user message uses the `list[ContentPart]` content shape directly — no double-wrapping or merging.
3. **Given** an agent, **When** `agent.run("Hello", file_attachments=[img1, img2])` is called, **Then** the resulting user message contains one text part and two file parts in order.
4. **Given** an agent, **When** `agent.run("Hello", file_attachments=[img])` is called with `stream=True`, **Then** streaming works correctly and file attachments are included in the request.
5. **Given** an agent, **When** `agent.run("Hello")` is called with no `file_attachments`, **Then** behavior is identical to the current implementation (backward compatible).
6. **Given** an agent, **When** `agent.run("")` is called with only `file_attachments` and an empty string query, **Then** the message includes file attachments with an empty text part (`content: ""`).
7. **Given** an agent and an existing message history, **When** `agent.run("Describe this", file_attachments=[img], messages=history)` is called, **Then** the history messages are preserved and the new user message with attachments is appended.

### Edge Cases

- What happens when `file_attachments` is an empty list? → Treated the same as `None` (no attachments).
- What happens when both `query: list[ContentPart]` and `file_attachments` are provided? → `file_attachments` are appended after the explicit content parts, preserving the order guarantee.
- What happens when `query` is an empty string and `file_attachments` has items? → The agent-level message contains `content: ""` with the `attachments` key (empty text part). Providers may omit the empty text part when constructing API-specific payloads.
- What happens with `None` in the `file_attachments` list? → Raised as `ValueError` or `TypeError` at validation time.

---

## Requirements

### Functional Requirements

- **FR-001**: `Agent.run()` MUST accept `query: str | list[ContentPart]` — the existing `str` type is extended to a union.
- **FR-002**: `Agent.run()` MUST accept an optional `file_attachments: list[FileAttachment] | None = None` parameter.
- **FR-003**: When `query` is `str` and `file_attachments` is provided, `Agent.run()` MUST construct a user message dict with `content: str` containing the query text and an `attachments` key containing the `file_attachments` list.
- **FR-004**: When `query` is `str` and `file_attachments` is `None` or `[]`, `Agent.run()` MUST produce the same `{"role": "user", "content": query}` message as before (backward compatible).
- **FR-005**: When `query` is `list[ContentPart]`, `Agent.run()` MUST use the content parts directly as the message `content`. If `file_attachments` is also provided, the attachments MUST be appended as additional `ContentPart(type="file", ...)` items after the explicit content parts.
- **FR-006**: `Agent.run()` with `file_attachments` MUST work correctly in streaming mode (`stream=True`).
- **FR-007**: `Agent.run()` MUST validate that items in `file_attachments` are `FileAttachment` instances, raising `TypeError` for invalid items.
- **FR-008**: The constructed user message MUST follow the canonical message shape `[{"role": "user", "content": <str | list[ContentPart]>, "attachments": <list[FileAttachment]>}]` where the `attachments` key is present only when `file_attachments` is provided and non-empty.

### Key Entities

- **UserMessage dict**: The internal message format: `{"role": "user", "content": str | list[ContentPart], "attachments": list[FileAttachment] | none}`. Provider translation layers already handle both `content: list[ContentPart]` and `content: str` + `attachments` shapes.
- **FileAttachment**: The canonical model from `tinycua_sdk.models.attachment` (already exists from Phase 1).
- **ContentPart**: The canonical multimodal content part model from `tinycua_sdk.models.attachment` (already exists from Phase 1).

---

## Success Criteria

- [ ] **Agent.run() accepts file_attachments**: Callers can pass `file_attachments=[FileAttachment(...)]` and the request reaches the LLM provider correctly.
- [ ] **Agent.run() accepts query as list[ContentPart]**: Callers can pass `query=[ContentPart(type="text", text="..."), ContentPart(type="file", file=...)]` directly.
- [ ] **Backward compatible**: Existing `agent.run("str")` calls produce identical results.
- [ ] **Streaming works**: `agent.run("str", file_attachments=[...], stream=True)` streams correctly.
- [ ] **Both providers supported**: File attachments flow correctly through both OpenAI Chat Completions and Responses API providers.
- [ ] **Empty file_attachments is no-op**: `agent.run("str", file_attachments=[])` behaves identically to `agent.run("str")`.

---

## Testing Plan

### Unit Tests

- `Agent.run()` with `str` query and `file_attachments`: verify message dict has correct shape.
- `Agent.run()` with `list[ContentPart]` query: verify message dict uses content parts directly.
- `Agent.run()` with `list[ContentPart]` query and `file_attachments`: verify attachments appended after content parts.
- `Agent.run()` with `str` query and no `file_attachments`: verify backward-compatible message dict.
- `Agent.run()` with empty `file_attachments=[]`: verify no-op behavior.
- `Agent.run()` with `stream=True` and `file_attachments`: verify streaming starts and completes.
- `Agent.run()` with invalid `file_attachments` types: verify `TypeError` is raised.
- `Agent.run()` with `None` items in `file_attachments`: verify `TypeError`/`ValueError` is raised.

### Integration Tests

- End-to-end agent run with a `FileAttachment.from_path()` image, verifying the request reaches a mock LLM and returns a response.
- End-to-end agent stream with `file_attachments`, verifying stream events are received.

### Manual Tests

- Run an agent with a real OpenAI API key and a local image file, verify the response describes the image.