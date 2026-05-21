# Feature Specification: OpenAI Responses File Attachment Translation

**Status**: Complete
**Created**: 2026-05-21
**Last Updated**: 2026-05-21
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Enable SDK callers to send canonical file attachments through the OpenAI Responses provider using the Phase 1 attachment shapes:

- Explicit multipart content: `content: list[ContentPart]`
- Basic message attachments: `content: str` with `attachments: list[FileAttachment]`

The provider must translate both canonical forms into Responses-native multimodal input so callers can use `provider="openai-responses"` with vision-capable and file-capable models without constructing provider-specific payloads themselves.

### Gaps

- Phase 1 added canonical `FileAttachment` and `ContentPart` models, but the OpenAI Responses provider still passes user messages through as plain text-oriented input.
- Phase 2 added Chat Completions attachment translation, but the default `openai-responses` provider cannot yet consume canonical attachments.
- Base64-backed, URL-backed, and `file_id`-backed attachments have no Responses-specific mapping.
- The SDK has no Responses provider upload/cache path to avoid re-uploading the same file attachment in a session.
- Existing Responses tests verify text and tool-call payloads, but not multimodal input payloads.

### Non-Goals

- No changes to the canonical attachment models introduced in Phase 1.
- No changes to the Chat Completions provider; Phase 2 already owns that path.
- No `Agent.run()` convenience parameter changes; Phase 4 owns user-facing run API expansion.
- No tool-result attachment support beyond preserving current tool-result string output behavior; Phase 6 owns tool-result file flow.
- No persistent file cache across process restarts or agent lifetimes; this phase only requires a per-session/provider-client cache.
- No fully lazy large-file streaming API; broader streaming upload behavior remains Phase 5 unless needed by the provider upload endpoint.

### Constraints

- Plain `content: str` user messages must remain translated exactly as they are today when no attachments are present.
- Both canonical attachment forms must be accepted for user messages.
- `ContentPart` ordering must be preserved for explicit multipart content.
- For basic message attachments, the text content must appear before appended attachment parts.
- Message-level attachments must be appended after explicit `content: list[ContentPart]` parts when both forms are supplied.
- Existing tool-call, tool-result, `previous_response_id`, streaming, and raw event behavior must not regress.
- Provider-specific unsupported attachment forms or MIME types must fail clearly before a provider request is made, unless the provider can safely accept them.

---

## User Scenarios & Testing

### Primary Scenario

A developer builds an agent using the default `openai-responses` provider and a vision-capable model. They create an image attachment with `FileAttachment.from_path("photo.png")`, pass it in a user message with a text prompt, and receive a model response describing the image. The developer uses SDK canonical types only and does not manually build OpenAI Responses content parts.

### Acceptance Scenarios

1. **Given** a user message whose `content` is `list[ContentPart]` with text followed by an image attachment, **When** it is sent through the OpenAI Responses provider, **Then** the provider request contains Responses-native multimodal input parts in the same order.
2. **Given** a user message whose `content` is a string and whose `attachments` contains one image attachment, **When** it is sent through the OpenAI Responses provider, **Then** the provider request contains one text part followed by one image/file part.
3. **Given** a base64-backed image attachment, **When** it is translated for OpenAI Responses, **Then** it becomes a Responses-compatible inline image input.
4. **Given** a URL-backed image attachment, **When** it is translated for OpenAI Responses, **Then** it becomes a Responses-compatible image input referencing that URL.
5. **Given** a non-image file attachment that the Responses API supports through file input, **When** it is translated, **Then** it becomes a Responses-compatible file input.
6. **Given** a file attachment that requires upload, **When** the same attachment is used multiple times in one provider-client session, **Then** the provider reuses the cached `file_id` rather than uploading it again.
7. **Given** an existing string-only user message, **When** it is translated for OpenAI Responses, **Then** the translated payload remains the same as before this phase.
8. **Given** an unsupported or malformed attachment source, **When** it is translated for OpenAI Responses, **Then** the provider fails clearly before making an invalid request.

### Edge Cases

- Empty `content: list[ContentPart]` MUST be rejected with a `ValueError` before translation.
- Empty `attachments` should behave the same as omitted `attachments`.
- Multiple attachments should appear in the same order supplied by the caller.
- Mixed text and file `ContentPart` values should preserve caller-defined order.
- When both `content: list[ContentPart]` and `attachments` are present, explicit content parts should appear first, followed by message-level attachments.
- Pre-existing `FileAttachment.file_id` values should be used directly when valid for OpenAI Responses.
- Cache lookup misses should upload once and cache the resulting file ID for later use in the same session.
- String-only system, assistant, and tool-result messages must retain their existing translation behavior.

---

## Requirements

### Functional Requirements

- **FR-001**: OpenAI Responses translation MUST support `UserMessage.content` as `list[ContentPart]`.
- **FR-002**: OpenAI Responses translation MUST support `UserMessage.content` as `str` with `attachments: list[FileAttachment]`.
- **FR-003**: Text `ContentPart` values MUST translate to Responses-native text input parts.
- **FR-004**: Image `FileAttachment` values backed by inline data or URLs MUST translate to Responses-native image input parts.
- **FR-005**: Non-image `FileAttachment` values supported by the Responses API MUST translate to Responses-native file input parts.
- **FR-006**: `FileAttachment.file_id` values MUST translate to Responses-native file references without re-uploading.
- **FR-007**: Message-level attachments MUST be normalized as file content parts appended after message text.
- **FR-008**: When both `content: list[ContentPart]` and non-empty `attachments` are present, message-level attachments MUST append after explicit content parts while preserving caller order within each group.
- **FR-009**: The provider MUST maintain a per-session cache mapping stable file content/source hashes to provider `file_id` values for uploaded attachments.
- **FR-010**: Reusing the same upload-required attachment within one provider-client session MUST reuse the cached `file_id` instead of uploading again.
- **FR-011**: The existing plain string message path MUST remain backward-compatible when no attachments are present.
- **FR-012**: Unsupported attachment sources, invalid content parts, and unsupported provider MIME/source combinations MUST produce clear errors before an invalid provider request is made.
- **FR-013**: Unit tests MUST cover both canonical attachment forms, inline data, URLs, `file_id`, cache reuse, multiple attachments, ordering, backward-compatible string messages, and the combined `content: list[ContentPart]` plus `attachments` case.
- **FR-014**: Integration coverage MUST verify that a Responses request can carry an image attachment to a vision-capable model, with network-dependent execution guarded by environment configuration.

### Key Entities

- **FileAttachment**: Canonical file descriptor introduced in Phase 1. In this phase, the Responses provider consumes attachments backed by inline data, URL, or provider file ID.
- **ContentPart**: Canonical typed content part introduced in Phase 1. In this phase, text parts and file parts are mapped to Responses-native message content.
- **UserMessage**: Canonical user message that may contain either plain text or structured content parts, plus optional message-level attachments.
- **OpenAI Responses input content**: Provider-native multimodal input containing text, image, and file entries.
- **Per-session file cache**: Provider-client scoped cache that maps repeat attachment inputs to uploaded OpenAI file IDs.

---

## Success Criteria

- [ ] **Explicit multipart content works**: A user message with `list[ContentPart]` containing text and file attachments translates to provider-native Responses content parts.
- [ ] **Basic attachments shape works**: A user message with `content: str` and `attachments` translates to provider-native text followed by attachment content parts.
- [ ] **Inline image data works**: Base64-backed image attachments become valid Responses image inputs.
- [ ] **Image URLs work**: URL-backed image attachments remain URL references in Responses payloads.
- [ ] **File IDs work**: Pre-existing or cached `file_id` values are reused without re-upload.
- [ ] **Upload cache works**: Reusing the same upload-required attachment in one session uploads once and reuses the cached `file_id` later.
- [ ] **Ordering is preserved**: Explicit multipart content and multiple attachments retain caller-specified order.
- [ ] **Mixed input ordering is preserved**: When both `list[ContentPart]` and `attachments` are present, explicit content parts appear first followed by message-level attachment parts.
- [ ] **Backward compatibility holds**: Existing string-only Responses payload tests continue to pass unchanged.
- [ ] **Unsupported inputs fail clearly**: Invalid or unsupported attachment shapes are rejected before the request is sent.
- [ ] **Integration path is covered**: A guarded integration test documents and verifies image attachment use with a vision-capable OpenAI Responses model.

---

## Testing Plan

### Unit Tests

- Test `_translate_messages()` with `content: list[ContentPart]` containing text and inline image data.
- Test `_translate_messages()` with `content: str` and `attachments: list[FileAttachment]`.
- Test URL-backed image attachment translation.
- Test non-image file attachment translation for provider-supported file input.
- Test `file_id`-backed attachment translation without upload.
- Test upload-required attachment cache reuse in one `OpenAIResponsesClient` session.
- Test multiple attachments and explicit multipart ordering.
- Test combined `content: list[ContentPart]` with non-empty `attachments` appends message-level attachments after explicit content parts in caller order.
- Test string-only user messages remain translated as the current plain string payload shape.
- Test unsupported MIME/source combinations and malformed content parts fail clearly.
- Test tool-result translation and `previous_response_id` behavior remain unchanged.

### Integration Tests

- Add a guarded OpenAI Responses integration test that sends an image attachment to a vision-capable model using `FileAttachment.from_bytes()` or `FileAttachment.from_path()` and asserts a non-empty assistant response.
- Ensure the integration test is skipped unless the required API key and model configuration are present.

### Manual Tests

- Run the OpenAI Responses provider against a real vision-capable model with both canonical attachment forms.
- Attach the same file twice in one session and confirm upload reuse through logs or mocked upload call counts.
- Confirm existing Responses text, streaming, and tool-call workflows still pass.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec & Design | Done | Ready for implementation |
| Responses attachment translation | TODO | Phase 3 implementation |
| File upload integration | TODO | Provider-specific upload path |
| Per-session file ID cache | TODO | Cache scope limited to provider-client session |
| Unit tests | TODO | Must be written before implementation |
| Integration test | TODO | Guarded by environment configuration |
| Persistent cache / large-file streaming | Deferred | Broader Phase 5 scope |

---

## Open Questions

*(No open questions — Phase 3 scope follows issue #46 and the Phase 1 attachment decisions.)*

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
