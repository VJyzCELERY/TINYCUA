# Feature Specification: SDK-wide File Attachment Support

**Status**: Complete
**Created**: 2026-05-20
**Last Updated**: 2026-05-20
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Provide a canonical `FileAttachment` model and `ContentPart` system so that SDK callers can:

- Attach files (images, PDFs, audio, video, etc.) to user messages sent to LLM providers
- Define multimodal message content as a list of typed parts (text or file)
- Use ergonomic helpers (`from_path`, `from_bytes`, `from_url`) to construct file attachments
- Allow tool results to include file attachments that flow back to the LLM in subsequent turns

### Gaps

Today the SDK supports only plain-text user messages (`content: str`). There is no abstraction for:

1. Representing file data (base64 content, MIME type, filename, URL, or provider file ID)
2. Structuring messages with mixed content (text + file) — every message is a single string
3. Translating file attachments to provider-native formats (OpenAI Responses API `input_file`, Chat Completions `image_url`)
4. Caching uploaded files to avoid re-uploading the same content
5. Streaming large files rather than loading them fully into memory

### Non-Goals

- No custom file storage or persistence layer — files are provided inline (base64) or by URL; `file_id` caching is ephemeral per-session
- No image analysis or processing — the SDK passes file data to the provider and returns the provider response as-is
- No multi-modal output — only the LLM's text response is supported; provider file outputs (e.g. DALL-E image generation) are out of scope
- Provider translation is not modified in this phase — the provider translation layer remains unchanged. Phase 1 is model-only (canonical model construction, serialization, and message type widening).

### Constraints

- Backward compatibility: `content: str` must continue to work unchanged for all existing callers
- The `UserMessage` and `ToolResultMessage` canonical message types must accept both `str` and `list[ContentPart]`
- In Phase 1, provider translation is out of scope — the translation layer only passes through canonical content parts unchanged. Provider-native format mapping is deferred to Phase 2+.
- The `FileAttachment` model must support validation and serialization of its fields
- The `ContentPart` model must enforce that text parts set `text` and file parts set `file`, with mutually exclusive field validation per variant

---

## User Scenarios & Testing

### Primary Scenario

A developer building an AI agent wants to send an image file to a vision-capable model. They:

1. Load an image from disk using `FileAttachment.from_path("photo.jpg")`
2. Construct a message with `ContentPart(type="text", text="What is in this image?")` and `ContentPart(type="file", file=attachment)`
3. Construct a canonical `UserMessage` containing the text and file `ContentPart` list
4. Serialize and deserialize the `ContentPart` list via Pydantic to verify canonical model compatibility
5. Confirm provider-native translation and `Agent.run()` convenience usage remain deferred to Phase 2+ / Phase 4

### Acceptance Scenarios

1. **Given** a `FileAttachment` created from a local file path, **When** `from_path()` is called, **Then** the attachment contains base64-encoded data, correct MIME type, and original filename
2. **Given** a `FileAttachment` created from raw bytes, **When** `from_bytes()` is called, **Then** the attachment contains the base64-encoded data and caller-specified MIME type
3. **Given** a `FileAttachment` created from a URL, **When** `from_url()` is called, **Then** the attachment stores the URL with a provided MIME type
4. **Given** a `UserMessage` with `content: str`, **When** the message is serialized or translated, **Then** behavior is identical to the existing `str`-only path
5. **Given** a `UserMessage` with `content: list[ContentPart]`, **When** the message is constructed and serialized, **Then** the `ContentPart` variants are preserved correctly through Pydantic serialization round-trips
6. **Given** a `ToolResultMessage` with `content: list[ContentPart]`, **When** the message is constructed, **Then** file attachments in tool results are correctly carried through the canonical message types

### Edge Cases

- What happens when `from_path()` receives a non-existent file path?
- How does the system handle unsupported or unknown MIME types?
- What is the behavior when `file_id` is provided but `data` is not (cached file reference)?
- How are very large files handled — can `from_path()` stream or must it load fully?
- Source fields `data`, `url`, and `file_id` are mutually exclusive — providing more than one raises a `ValidationError`

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST define a `FileAttachment` model with fields: `data` (Optional base64 string), `mime_type`, `filename` (Optional), `url` (Optional), `file_id` (Optional)
- **FR-002**: System MUST define a `ContentPart` model with `type: "text" | "file"` and corresponding `text: str | None` and `file: FileAttachment | None` fields, where text parts require `text` to be set and file parts require `file` to be set, and variant fields are mutually exclusive
- **FR-003**: `UserMessage.content` MUST accept `str | list[ContentPart]` (backward-compatible union)
- **FR-004**: `ToolResultMessage.content` MUST accept `str | list[ContentPart]`
- **FR-005**: System MUST provide `FileAttachment.from_path(path: str | Path, mime_type: str | None = None, stream: bool = False) -> FileAttachment` that reads file, detects MIME type via `mimetypes` (caller-provided `mime_type` overrides detection), and base64-encodes the data. When `stream=True`, uses chunked input reading while still returning a materialized base64 string.
- **FR-006**: System MUST provide `FileAttachment.from_bytes(data: bytes, mime_type: str, filename: str | None = None) -> FileAttachment` that base64-encodes the bytes
- **FR-007**: System MUST provide `FileAttachment.from_url(url: str, mime_type: str, filename: str | None = None) -> FileAttachment` that stores the URL
- **FR-008**: System MUST support `from_path()` with a `stream: bool` parameter that, when `True`, uses chunked input reading to avoid loading raw file bytes all at once, while materializing the final base64 string. True lazy/OOM-safe streaming is deferred to Phase 5.
- **FR-009**: All existing `str`-based message handling MUST remain unchanged (backward compatibility)

### Key Entities

- **FileAttachment**: Represents a file to be sent to an LLM provider. Contains base64-encoded data, MIME type, filename, URL, and/or provider file ID. Exactly one of `data`, `url`, or `file_id` must be present.
- **ContentPart**: A tagged Pydantic model representing a single part of a multimodal message. Has two variants via `type: "text" | "file"`: `text` (with text content) and `file` (with a `FileAttachment`). Explicit validators enforce that each variant only contains its relevant fields.
- **UserMessage**: A canonical input TypedDict representing a user message. Its `content` field accepts both simple strings and structured content parts.
- **ToolResultMessage**: A canonical input TypedDict representing a tool result. Its `content` field similarly accepts both strings and content parts.

---

## Success Criteria

- [x] **Canonical models accept file attachments**: A `UserMessage` with `list[ContentPart]` containing a file attachment is constructed, serialized, and deserialized correctly via Pydantic round-trip
- [x] **Backward compatible**: All existing tests pass without modification — `str`-only messages unchanged
- [x] **Helper methods work**: `FileAttachment.from_path()`, `from_bytes()`, `from_url()` produce correct attachments
- [x] **MIME detection works**: `from_path()` correctly detects MIME types for common file formats (JPEG, PNG, PDF, MP3, MP4)
- [x] **Streaming parity**: `from_path(stream=True)` produces base64 output identical to the non-streaming path, verified via chunked reading
- [x] **ContentPart serialization**: `ContentPart` models serialize/deserialize correctly via Pydantic

---

## Testing Plan

### Unit Tests

- `test_file_attachment_model()` — creation, field defaults, required fields, serialization round-trip
- `test_file_attachment_from_path()` — valid file, missing file, MIME detection, streaming mode
- `test_file_attachment_from_bytes()` — encodes correctly, MIME type validation
- `test_file_attachment_from_url()` — URL storage, MIME type
- `test_content_part_model()` — text part, file part, variant validation, serialization
- `test_user_message_content_union()` — `content: str` works, `content: list[ContentPart]` works
- `test_tool_result_message_content_union()` — `content: str` works, `content: list[ContentPart]` works

### Integration Tests

- None for Phase 1 (model-only). Phase 2+ will add provider translation integration tests.

### Manual Tests

- Verify that `FileAttachment.from_path(stream=True)` produces base64 output identical to `from_path(stream=False)` for a file larger than the chunk size

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| FileAttachment model | DONE | |
| ContentPart model | DONE | |
| UserMessage.content union | DONE | |
| ToolResultMessage.content union | DONE | |
| from_path() helper | DONE | |
| from_bytes() helper | DONE | |
| from_url() helper | DONE | |
| Unit tests | DONE | |

---

## Open Questions

*(No open questions — all previously discussed items have been decided; see **Technical Decisions** in `design.md`.)*

---

## Review Checklist

- [X] No implementation details (no code, framework, or architecture choices)
- [X] All mandatory sections completed
- [X] No `[NEEDS CLARIFICATION]` markers remain
- [X] Requirements are testable and unambiguous
- [X] Scope is clearly bounded with explicit non-goals
- [X] Success criteria are measurable
