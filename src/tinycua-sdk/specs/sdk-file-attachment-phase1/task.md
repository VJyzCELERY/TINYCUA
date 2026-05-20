# Tasks: SDK-wide File Attachment Support — Phase 1

Implementation tasks for SDK-wide File Attachment Support Phase 1. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration-boundary tests from `implementation-plan.md` in `src/tinycua-sdk/tests/integration/test_file_attachment_models.py` <!-- id: 0 -->
  - [ ] Cover `FileAttachment.from_path()` flowing into `UserMessage.content`
  - [ ] Cover `from_bytes()` and `from_url()` serialization round trips
  - [ ] Cover `ToolResultMessage.content` with file content parts
  - [ ] Cover invalid attachment/content-part validation errors
  - [ ] Cover `from_path(stream=True)` parity with non-streaming output
- [ ] Run integration-boundary tests — expect RED because models are not implemented yet: `cd src/tinycua-sdk && uv run pytest tests/integration/test_file_attachment_models.py` <!-- id: 1 -->
- [ ] Write focused unit tests in `src/tinycua-sdk/tests/unit/test_file_attachment.py` <!-- id: 2 -->
  - [ ] Test `FileAttachment` direct construction, source-field validation, and `file_id`-only cached references
  - [ ] Test `from_path()` success, missing file propagation, MIME detection, MIME fallback, and filename preservation
  - [ ] Test `from_bytes()` encoding and required MIME type
  - [ ] Test `from_url()` URL storage and optional filename
  - [ ] Test `ContentPart` text/file variants and serialization round trips
- [ ] Update canonical schema tests for structured `UserMessage` and `ToolResultMessage` content, preserving existing string tests <!-- id: 3 -->

## Implementation Phase

- [ ] Create `src/tinycua-sdk/tinycua_sdk/models/attachment.py` with `FileAttachment` <!-- id: 4 -->
  - [ ] Add fields `data`, `mime_type`, `filename`, `url`, and `file_id`
  - [ ] Add cross-field validation requiring at least one of `data`, `url`, or `file_id`
  - [ ] Add docstrings compatible with the SDK's Ruff pydocstyle settings
- [ ] Implement `FileAttachment` factory helpers <!-- id: 5 -->
  - [ ] Implement `from_bytes()` with standard-library base64 encoding
  - [ ] Implement `from_url()` without fetching the URL
  - [ ] Implement `from_path()` with `Path` support, MIME detection, fallback MIME type, and filename preservation
  - [ ] Implement `from_path(stream=True)` using chunked reading while returning a single base64 string
- [ ] Add `ContentPart` to `attachment.py` <!-- id: 6 -->
  - [ ] Support `type: Literal["text", "file"]`
  - [ ] Require `text` for text parts
  - [ ] Require `file` for file parts
  - [ ] Reject incompatible fields for each variant if tests require strict discriminated behavior
- [ ] Export new models from `src/tinycua-sdk/tinycua_sdk/models/__init__.py` <!-- id: 7 -->
  - [ ] Import `ContentPart` and `FileAttachment`
  - [ ] Add both names to `__all__`
- [ ] Widen canonical event message content types in `src/tinycua-sdk/tinycua_sdk/agent/events.py` <!-- id: 8 -->
  - [ ] Import `ContentPart`
  - [ ] Change `UserMessage.content` to `str | list[ContentPart]`
  - [ ] Change `ToolResultMessage.content` to `str | list[ContentPart]`
  - [ ] Leave provider translation and other message types unchanged for Phase 1

## Testing Phase

- [ ] Run integration-boundary tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/integration/test_file_attachment_models.py` <!-- id: 9 -->
- [ ] Run new unit tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/unit/test_file_attachment.py` <!-- id: 10 -->
- [ ] Run canonical schema tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/unit/test_canonical_schema.py` <!-- id: 11 -->
- [ ] Run full SDK test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 12 -->
- [ ] Run lint if available for changed SDK files: `cd src/tinycua-sdk && uv run ruff check tinycua_sdk tests` <!-- id: 13 -->

## Verification Phase

- [ ] Manually verify public imports work: `from tinycua_sdk.models import ContentPart, FileAttachment` <!-- id: 14 -->
- [ ] Manually verify a plain string `UserMessage` and `ToolResultMessage` still type and behave like before <!-- id: 15 -->
- [ ] Manually verify a text+file `UserMessage` can be constructed without touching provider clients <!-- id: 16 -->
- [ ] Confirm no provider translation files were modified in this phase <!-- id: 17 -->
- [ ] Confirm streaming-mode output matches non-streaming output for a file larger than the chunk size <!-- id: 18 -->

## Documentation Phase

- [ ] Update `src/tinycua-sdk/specs/sdk-file-attachment-phase1/spec.md` status tracker from TODO to DONE for completed Phase 1 items if implementation is completed <!-- id: 19 -->
- [x] ~~Update `src/tinycua-sdk/specs/sdk-file-attachment-phase1/design.md` if implementation needs a documented validator detail such as `model_validator` instead of `field_validator` <!-- id: 20 -->~~ _(Already applied — design.md now uses `@model_validator(mode="after")`)_
- [ ] Update SDK README or docs only if the public import path needs to be advertised in this phase <!-- id: 21 -->

## Review and Merge

- [ ] Review changed files for Phase 1 scope control: models, exports, event types, and tests only <!-- id: 22 -->
- [ ] Address review feedback <!-- id: 23 -->
- [ ] Merge via the project PR workflow after CI/review approval <!-- id: 24 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-20*
