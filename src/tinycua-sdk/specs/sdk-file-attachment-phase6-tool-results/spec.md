# Feature Specification: Phase 6 — Tool Result File Support

**Status**: Complete
**Created**: 2026-05-26
**Last Updated**: 2026-05-26
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Enable tools executed by the SDK agent loop to return files back to the language model on the next turn. Phase 1–5 made user-supplied file attachments work through canonical `FileAttachment`, `ContentPart`, and provider translation layers. Phase 6 completes the loop by preserving those same attachment shapes when they originate from tool results rather than initial user messages.

The caller outcome is that a tool can generate or retrieve an image, PDF, text artifact, or provider file reference and the LLM can immediately reason over that file in the next model call.

### Gaps

| Gap | Impact |
|-----|--------|
| The agent loop coerces every tool result to `str(tool_result)` | Structured tool results containing `ContentPart` or `attachments` lose their file semantics before provider translation. |
| Provider translation only applies attachment helpers to user messages | Tool result messages are converted using raw `content`/`output` fields, so tool-returned files are not translated into provider-native content. |
| Streaming and non-streaming tool-call paths share string-only result handling | File support could work in one loop mode and silently fail in the other unless both paths share a canonical conversion contract. |
| There is no end-to-end test for a tool-generated file followed by LLM reasoning | Regressions in the agent loop, provider translation, and upload/cache integration could go unnoticed. |

### Non-Goals

- No new attachment model types; Phase 6 reuses `FileAttachment` and `ContentPart` from earlier phases.
- No changes to user message file support, upload cache policy, streaming upload behavior, or URL download policy from Phase 1–5.
- No new public provider APIs beyond accepting the already-documented `ToolResultMessage.content: str | list[ContentPart]` and optional `ToolResultMessage.attachments` shapes.
- No automatic conversion of arbitrary binary bytes returned by tools into attachments unless the tool returns an explicit supported attachment shape.
- No provider-specific capability emulation when a provider cannot accept files in tool results; provider errors should remain clear and actionable.

### Constraints

- Existing string-only tool results must remain backward compatible.
- Tool-call sequencing contracts must remain valid for both OpenAI Chat Completions and OpenAI Responses.
- File uploads, file ID cache reuse, streaming attachments, and text MIME inline decoding must reuse the Phase 5 provider translation paths.
- Tool result attachment support must work in both non-streaming and streaming agent loops.
- The implementation must be test-first, with failing integration tests written before source changes.

---

## User Scenarios & Testing

### Primary Scenario

A developer registers a tool that creates an image file and returns a tool-result message containing a text summary plus a `FileAttachment`. The agent executes the tool, appends the structured tool result to its working messages, and calls the LLM again. The provider translates the tool-result attachment into its native file/image content shape. The LLM then answers a follow-up question about the generated image.

### Acceptance Scenarios

1. **Given** a tool returns `content: list[ContentPart]` containing text and a file, **When** the non-streaming agent loop executes the tool, **Then** the next LLM request receives a structured tool result that preserves the file attachment.
2. **Given** a tool returns string content plus `attachments: list[FileAttachment]`, **When** the non-streaming agent loop executes the tool, **Then** the next LLM request receives the text plus translated file parts.
3. **Given** a tool returns a file result while `Agent.run(stream=True)` is active, **When** the streaming loop processes the tool call, **Then** the same structured tool result is preserved for the next LLM stream iteration.
4. **Given** the provider is OpenAI Chat Completions, **When** a tool result contains an image attachment, **Then** it is translated to provider-native multimodal content without breaking tool-call message ordering.
5. **Given** the provider is OpenAI Responses, **When** a tool result contains an image or file attachment, **Then** it is translated to provider-native input content for the corresponding function-call output turn.
6. **Given** a legacy tool returns any non-structured value, **When** the agent loop processes it, **Then** the tool result remains a string exactly as before.

### Edge Cases

- Tool returns `ContentPart(type="file")` without a file object: the provider translation should raise `ValueError` (from the existing `ContentPart` validation) rather than silently dropping the part.
- Tool returns empty `list[ContentPart]`: the implementation should reject with a `ValueError` containing a message that identifies the empty content part list as invalid.
- Tool result includes both explicit content parts and message-level attachments: explicit parts should be translated first, then attachments appended, matching user message semantics.
- Tool execution fails before producing a structured result: existing error-result behavior must remain string-only and backward compatible.
- A tool returns a `StreamingFileAttachment`: provider translation should reuse the existing streaming upload path.

---

## Requirements

### Functional Requirements

- **FR-001**: The agent loop MUST preserve tool results that are already shaped as canonical `ToolResultMessage` data, including `content: list[ContentPart]` and optional `attachments`.
- **FR-002**: The agent loop MUST support tool return values that provide string content plus `attachments: list[FileAttachment]` without coercing the attachments into a string.
- **FR-003**: The agent loop MUST support tool return values that provide `content: list[ContentPart]` without coercing those content parts into a string.
- **FR-004**: Non-streaming and streaming tool-call processing MUST use the same canonical tool-result normalization behavior.
- **FR-005**: OpenAI Chat Completions translation MUST translate tool-result `list[ContentPart]` and `attachments` into provider-native tool message content while preserving the assistant `tool_calls` message required by the API.
- **FR-006**: OpenAI Responses translation MUST translate tool-result `list[ContentPart]` and `attachments` into provider-native function-call output content for the next turn.
- **FR-007**: Provider translation MUST reuse existing attachment behavior for image, text, non-image, URL, streaming, and pre-existing `file_id` attachments.
- **FR-008**: Legacy tool results that are plain strings, numbers, dicts without attachment fields, or exceptions MUST continue to produce string tool-result content.
- **FR-009**: Unit tests MUST cover agent-loop normalization, provider translation for both canonical tool-result attachment forms, and backward compatibility.
- **FR-010**: Integration tests MUST verify that a tool-generated file reaches the next LLM call in both streaming and non-streaming flows.

### Key Entities

- **ToolResultMessage**: Canonical message from a tool execution back to the LLM. It may contain plain string content, explicit multimodal content parts, or string content with message-level attachments.
- **FileAttachment**: Canonical file reference/data object reused from earlier phases.
- **ContentPart**: Canonical multimodal message part used to mix text and file content.
- **Tool result normalization**: The agent-loop behavior that converts arbitrary tool return values into a canonical tool-result message before appending it to the working message list.

---

## Success Criteria

- [ ] **Tool-generated image reaches the LLM**: A tool can return an image attachment and the next model request includes it in provider-native form.
- [ ] **Explicit content parts work**: A tool result using `content: list[ContentPart]` is preserved and translated correctly.
- [ ] **Basic attachments shape works**: A tool result using `content: str` plus `attachments: list[FileAttachment]` is preserved and translated correctly.
- [ ] **Streaming loop works**: Tool-result file support behaves the same under `Agent.run(stream=True)` as under non-streaming execution.
- [ ] **Chat Completions works**: Chat Completions provider translates tool-result attachments without breaking tool-call ordering.
- [ ] **Responses works**: Responses provider translates tool-result attachments into valid function-call output/input content.
- [ ] **Backward compatibility holds**: Existing string-only tool result tests continue to pass.
- [ ] **Cache and upload behavior reused**: Repeated tool-returned files reuse existing file ID cache behavior where provider translation requires upload.

---

## Testing Plan

### Unit Tests

- Agent loop: structured tool return with `content: list[ContentPart]` is appended without string coercion.
- Agent loop: structured tool return with `content: str` and `attachments` is appended without string coercion.
- Agent loop: legacy string, dict, number, and exception results remain string-compatible.
- Streaming loop: structured tool returns are preserved through the streaming tool-call processing path.
- Chat Completions provider: tool-result attachments translate to provider-native tool message content and preserve `tool_call_id`.
- Responses provider: tool-result attachments translate to function-call output shape with multimodal content preserved.

### Integration Tests

- End-to-end non-streaming agent run where a tool generates an image and the second LLM call receives the file attachment.
- End-to-end streaming agent run where a tool generates an image and the second LLM stream receives the file attachment.
- Provider-level integration using mocked OpenAI clients to assert the exact next-turn payload contains the translated attachment.

### Manual Tests

- Optional real-provider smoke test with a vision-capable model: tool generates a small PNG and asks the LLM to describe it.

---

## Status Tracker

This table tracks implementation progress. Spec and design planning is Complete; all other items reflect code-level implementation status (TODO = not yet implemented).

| Item | Status | Notes |
|------|--------|-------|
| Spec & Design | Complete | Phase 6 planning initialized from issue #46 |
| Agent loop normalization | TODO | Preserve structured tool results |
| Chat Completions translation | TODO | Tool result multimodal content |
| Responses translation | TODO | Function-call output with attachments |
| Integration tests | TODO | Tool-generated image scenario |

---

## Review Checklist

- [x] No implementation details outside the required behavioral contracts
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
