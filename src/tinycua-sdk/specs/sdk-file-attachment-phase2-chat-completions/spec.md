# Feature Specification: OpenAI Chat Completions File Attachment Translation

**Status**: Complete
**Created**: 2026-05-20
**Last Updated**: 2026-05-20
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Enable SDK callers to send image file attachments through the OpenAI Chat Completions provider using the canonical file attachment shapes introduced in Phase 1:

- Explicit multipart content: `content: list[ContentPart]`
- Basic message attachments: `content: str` with `attachments: list[FileAttachment]`

The provider must translate both canonical forms into Chat Completions-native multimodal message content so callers can use `provider="openai-chat-completions"` with vision-capable models without constructing provider-specific payloads themselves.

### Gaps

- Phase 1 added canonical file attachment models, but Chat Completions translation still assumes plain string message content.
- Callers cannot currently send images through the Chat Completions provider using `FileAttachment` or `ContentPart`.
- Canonical attachment data from `FileAttachment.from_bytes()`, `FileAttachment.from_path()`, and `FileAttachment.from_url()` has no Chat Completions mapping.
- Existing tests verify text and tool-call translation, but not multimodal Chat Completions payloads.

### Non-Goals

- No OpenAI Responses API attachment translation in this phase; that is tracked by Phase 3.
- No provider file upload endpoint or `file_id` cache in this phase; Chat Completions image inputs use URLs or inline data URLs.
- No generic non-image file support for Chat Completions unless the provider natively accepts it through the same message format. PDF, audio, video, and arbitrary file handling remain provider-permitting work for later phases.
- No changes to `Agent.run()` convenience parameters; that is tracked by Phase 4.
- No tool-result file attachment support in this phase; that is tracked by Phase 6.
- No new canonical message models; this phase consumes the Phase 1 models as-is.

### Constraints

- Plain `content: str` user messages must remain byte-for-byte equivalent in the translated Chat Completions payload when no attachments are present.
- Both canonical attachment forms must be accepted for user messages.
- `ContentPart` ordering must be preserved for explicit multipart content.
- For basic message attachments, the text content must appear before appended attachment parts.
- `FileAttachment` values backed by inline base64 data must be sent as data URLs with their declared MIME type.
- `FileAttachment` values backed by URLs must be sent as provider-visible URLs.
- `FileAttachment.file_id` alone is out of scope for Chat Completions Phase 2 and must fail clearly rather than silently dropping the attachment.

---

## User Scenarios & Testing

### Primary Scenario

A developer builds an agent using `provider="openai-chat-completions"` and a vision-capable model. They create an image attachment with `FileAttachment.from_path("photo.png")`, pass it in a user message together with a text prompt, and receive a model response describing the image. The developer uses SDK canonical types only and does not manually build `image_url` payloads.

### Acceptance Scenarios

1. **Given** a user message whose `content` is `list[ContentPart]` with text followed by an image file attachment, **When** it is sent through the Chat Completions provider, **Then** the provider request contains Chat Completions multimodal content parts in the same order.
2. **Given** a user message whose `content` is a string and whose `attachments` contains one image attachment, **When** it is sent through the Chat Completions provider, **Then** the provider request contains one text part followed by one image part.
3. **Given** a base64-backed image attachment, **When** it is translated for Chat Completions, **Then** the image part uses a data URL containing the declared MIME type and encoded data.
4. **Given** a URL-backed image attachment, **When** it is translated for Chat Completions, **Then** the image part uses that URL without requiring a download or upload.
5. **Given** an existing string-only user message, **When** it is translated for Chat Completions, **Then** the translated payload remains the same as before this phase.
6. **Given** an unsupported attachment source such as `file_id` without URL or inline data, **When** it is translated for Chat Completions, **Then** the provider fails clearly before making the request.
7. **Given** a user message whose `content` is `list[ContentPart]` and whose `attachments` is non-empty, **When** it is translated for Chat Completions, **Then** the provider request contains the explicit content parts in order followed by message-level attachment parts in the order supplied.

### Edge Cases

- Empty `content: list[ContentPart]` MUST be rejected with a `ValueError` before translation, consistent with the principle that at least one content part is required for a meaningful user message.
- Empty `attachments` should behave the same as omitted `attachments`.
- Multiple attachments should appear in the same order supplied by the caller.
- Mixed text and file `ContentPart` values should preserve caller-defined order.
- Non-image MIME types should fail clearly for Chat Completions unless explicitly supported by the provider message format.
- String-only system, assistant, and tool-result messages must retain their existing translation behavior.

---

## Requirements

### Functional Requirements

- **FR-001**: Chat Completions translation MUST support `UserMessage.content` as `list[ContentPart]`.
- **FR-002**: Chat Completions translation MUST support `UserMessage.content` as `str` with `attachments: list[FileAttachment]`.
- **FR-003**: Text `ContentPart` values MUST translate to Chat Completions text content parts.
- **FR-004**: File `ContentPart` values backed by image data or image URLs MUST translate to Chat Completions image content parts.
- **FR-005**: Message-level attachments MUST be normalized as file content parts appended after the message text.
- **FR-006**: When both `content: list[ContentPart]` and non-empty `attachments` are present, message-level attachments MUST append after the explicit content parts, preserving caller order within each group.
- **FR-007**: Base64-backed image attachments MUST translate to provider-visible data URLs that include the attachment MIME type.
- **FR-008**: URL-backed image attachments MUST translate to provider-visible image URLs without SDK-side upload.
- **FR-009**: The existing plain string message path MUST remain backward-compatible when no attachments are present.
- **FR-010**: Unsupported attachment sources or MIME types MUST produce a clear error before the provider API request is made.
- **FR-011**: Unit tests MUST cover both canonical attachment forms, inline data, URLs, multiple attachments, ordering, backward-compatible string messages, and the combined `content: list[ContentPart]` plus `attachments` case.
- **FR-012**: Integration coverage MUST verify that a Chat Completions request can carry an image attachment to a vision-capable model, with network-dependent execution guarded by environment configuration.

### Key Entities

- **FileAttachment**: Canonical file descriptor introduced in Phase 1. In this phase, Chat Completions consumes image attachments backed by `data` or `url`.
- **ContentPart**: Canonical typed content part introduced in Phase 1. In this phase, text parts and image file parts are mapped to provider-native message content.
- **UserMessage**: Canonical user message that may contain either plain text or structured content parts, plus optional message-level attachments.
- **Chat Completions message content**: Provider-native multimodal content list containing text and image entries.

---

## Success Criteria

- [ ] **Explicit multipart content works**: A user message with `list[ContentPart]` containing text and an image attachment translates to provider-native text and image content parts.
- [ ] **Basic attachments shape works**: A user message with `content: str` and `attachments` translates to provider-native text followed by image content parts.
- [ ] **Inline image data works**: Base64-backed image attachments become valid data URLs in Chat Completions payloads.
- [ ] **Image URLs work**: URL-backed image attachments remain URLs in Chat Completions payloads.
- [ ] **Ordering is preserved**: Explicit multipart content and multiple attachments retain caller-specified order.
- [ ] **Mixed input ordering is preserved**: When both `list[ContentPart]` and `attachments` are present, explicit content parts appear first followed by message-level attachment parts, with caller order preserved within each group.
- [ ] **Backward compatibility holds**: Existing string-only Chat Completions payload tests continue to pass unchanged.
- [ ] **Unsupported inputs fail clearly**: `file_id`-only or unsupported non-image attachments are rejected before the request is sent.
- [ ] **Integration path is covered**: A guarded integration test documents and verifies image attachment use with a vision-capable Chat Completions model.

---

## Testing Plan

### Unit Tests

- Test `_translate_chat_messages()` with `content: list[ContentPart]` containing text and inline image data.
- Test `_translate_chat_messages()` with `content: str` and `attachments: list[FileAttachment]`.
- Test URL-backed image attachment translation.
- Test multiple attachments and explicit multipart ordering.
- Test combined `content: list[ContentPart]` with non-empty `attachments` appends message-level attachments after explicit content parts in caller order.
- Test string-only user messages remain translated as plain strings.
- Test unsupported MIME types and `file_id`-only attachments fail clearly.
- Test tool-result translation remains unchanged for string content.

### Integration Tests

- Add a guarded Chat Completions integration test that sends an image attachment to a vision-capable model using `FileAttachment.from_bytes()` or `FileAttachment.from_path()` and asserts a non-empty assistant response.
- Ensure the integration test is skipped unless the required API key and model configuration are present.

### Manual Tests

- Run the Chat Completions provider against a real OpenAI vision-capable model with both canonical attachment forms.
- Confirm existing Chat Completions text and tool-call workflows still pass.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec & Design | Complete | Ready for implementation |
| Chat Completions attachment translation | TODO | Phase 2 implementation |
| Unit tests | TODO | Must be written before source changes |
| Integration test | TODO | Guarded by environment configuration |
| Text-file attachment support | Deferred | Non-image files out of scope for Phase 2; scheduled for a future Responses/arbitrary-file phase |

---

## Open Questions

*(No open questions — Phase 2 is intentionally scoped to Chat Completions image attachment translation using existing canonical models.)*

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
