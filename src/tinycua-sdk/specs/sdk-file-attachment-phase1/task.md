# Tasks: SDK-wide File Attachment Support — Phase 1

Implementation tasks for SDK-wide File Attachment Support Phase 1. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration-boundary tests from `implementation-plan.md` in `src/tinycua-sdk/tests/integration/test_file_attachment_models.py` <!-- id: 0 -->
  - [x] Cover `FileAttachment.from_path()` flowing into `UserMessage.content`
  - [x] Cover `from_bytes()` and `from_url()` serialization round trips
  - [x] Cover `ToolResultMessage.content` with file content parts
  - [x] Cover invalid attachment/content-part validation errors
  - [x] Cover `from_path(stream=True)` parity with non-streaming output
- [x] Run integration-boundary tests — expect RED because models are not implemented yet: `cd src/tinycua-sdk && uv run pytest tests/integration/test_file_attachment_models.py` <!-- id: 1 -->
- [x] Write focused unit tests in `src/tinycua-sdk/tests/unit/test_file_attachment.py` <!-- id: 2 -->
  - [x] Test `FileAttachment` direct construction, source-field mutex (exactly one of `data`/`url`/`file_id`), and `file_id`-only cached references
  - [x] Test `from_path()` success, missing file propagation, MIME detection, MIME fallback, and filename preservation
  - [x] Test `from_bytes()` encoding and required MIME type
  - [x] Test `from_url()` URL storage and optional filename
  - [x] Test `ContentPart` text/file variants and serialization round trips
- [x] Update canonical schema tests for structured `UserMessage` and `ToolResultMessage` content, preserving existing string tests <!-- id: 3 -->
  - [x] Add annotation-inspection tests using `typing.get_type_hints()` and `typing.get_args()` to verify `UserMessage.__annotations__["content"]` resolves to `str | list[ContentPart]`
  - [x] Add annotation-inspection tests verifying `ToolResultMessage.__annotations__["content"]` resolves to `str | list[ContentPart]`
- [x] Add tests for message-level attachments shape <!-- id: 3b -->
  - [x] Add tests for `UserMessage` with `content: str` + `attachments: list[FileAttachment]`
  - [x] Add tests for `ToolResultMessage` with `content: str` + `attachments: list[FileAttachment]`
  - [x] Add annotation-inspection tests for `UserMessage.__annotations__["attachments"]` and `ToolResultMessage.__annotations__["attachments"]`

## Implementation Phase

- [x] Create `src/tinycua-sdk/tinycua_sdk/models/attachment.py` with `FileAttachment` <!-- id: 4 -->
  - [x] Add fields `data`, `mime_type`, `filename`, `url`, and `file_id`
  - [x] Add cross-field validation requiring at least one of `data`, `url`, or `file_id`
  - [x] Add docstrings compatible with the SDK's Ruff pydocstyle settings
- [x] Implement `FileAttachment` factory helpers <!-- id: 5 -->
  - [x] Implement `from_bytes()` with standard-library base64 encoding
  - [x] Implement `from_url()` without fetching the URL
  - [x] Implement `from_path()` with `Path` support, MIME detection, fallback MIME type, and filename preservation
  - [x] Implement `from_path(stream=True)` using chunked reading while returning a single base64 string
- [x] Add `ContentPart` to `attachment.py` <!-- id: 6 -->
  - [x] Support `type: Literal["text", "file"]`
  - [x] Require `text` for text parts
  - [x] Require `file` for file parts
  - [x] Reject incompatible fields for each variant: text parts must not have file set, file parts must not have text set
- [x] Export new models from `src/tinycua-sdk/tinycua_sdk/models/__init__.py` <!-- id: 7 -->
  - [x] Import `ContentPart` and `FileAttachment`
  - [x] Add both names to `__all__`
- [x] Widen canonical event message content types in `src/tinycua-sdk/tinycua_sdk/agent/events.py` <!-- id: 8 -->
  - [x] Import `ContentPart` and `FileAttachment`, add `NotRequired` import
  - [x] Change `UserMessage.content` to `str | list[ContentPart]`
  - [x] Change `ToolResultMessage.content` to `str | list[ContentPart]`
  - [x] Add `attachments: NotRequired[list[FileAttachment]]` to `UserMessage`
  - [x] Add `attachments: NotRequired[list[FileAttachment]]` to `ToolResultMessage`
  - [x] Leave provider translation and other message types unchanged for Phase 1

## Testing Phase

- [x] Run integration-boundary tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/integration/test_file_attachment_models.py` <!-- id: 9 -->
- [x] Run new unit tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/unit/test_file_attachment.py` <!-- id: 10 -->
- [x] Run canonical schema tests — expect GREEN: `cd src/tinycua-sdk && uv run pytest tests/unit/test_canonical_schema.py` <!-- id: 11 -->
- [x] Run full SDK test suite: `cd src/tinycua-sdk && uv run pytest` <!-- id: 12 -->
- [x] Run lint if available for changed SDK files: `cd src/tinycua-sdk && uv run ruff check tinycua_sdk tests` <!-- id: 13 -->

## Verification Phase

- [x] Manually verify public imports work: `from tinycua_sdk.models import ContentPart, FileAttachment` <!-- id: 14 -->
- [x] Manually verify a plain string `UserMessage` and `ToolResultMessage` still type and behave like before <!-- id: 15 -->
- [x] Manually verify a text+file `UserMessage` can be constructed without touching provider clients <!-- id: 16 -->
- [x] Confirm no provider translation files were modified in this phase <!-- id: 17 -->
- [x] Confirm streaming-mode output matches non-streaming output for a file larger than the chunk size <!-- id: 18 -->

## Documentation Phase

- [x] Update `src/tinycua-sdk/specs/sdk-file-attachment-phase1/spec.md` status tracker from TODO to DONE for completed Phase 1 items if implementation is completed <!-- id: 19 -->
- [x] ~~Update `src/tinycua-sdk/specs/sdk-file-attachment-phase1/design.md` if implementation needs a documented validator detail such as `model_validator` instead of `field_validator` <!-- id: 20 -->~~ _(Already applied — design.md now uses `@model_validator(mode="after")`)_
- [x] ~~Update SDK README or docs only if the public import path needs to be advertised in this phase~~ <!-- id: 21 --> _(Not required — Phase 1 is model-only; public import path unchanged for existing callers)_

## Review and Merge

- [ ] Review changed files for Phase 1 scope control: models, exports, event types, and tests only <!-- id: 22 -->
- [x] Address review feedback <!-- id: 23 -->
- [ ] Merge via the project PR workflow after CI/review approval <!-- id: 24 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-20*
