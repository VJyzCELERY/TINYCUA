# Implementation: SDK-wide File Attachment Support — Phase 1

Add canonical SDK models for file attachments and structured multimodal content, then widen canonical user/tool-result message types so callers can pass either plain strings or typed content parts without breaking existing usage.

## Context

- **Spec Reference**: `src/tinycua-sdk/specs/sdk-file-attachment-phase1/spec.md`
- **Design Reference**: `src/tinycua-sdk/specs/sdk-file-attachment-phase1/design.md`
- **Priority**: P1
- **Estimated Effort**: M
- **Dependencies**: Existing `pydantic>=2.6.0` dependency and Python 3.12 runtime in `src/tinycua-sdk/pyproject.toml`

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| None | No | N/A | N/A |

### Data / Fixtures

- [ ] **None** — tests create local temporary files with pytest `tmp_path`

### Access / Permissions

- [ ] **None** — no special access required


### Developer Tooling

- [ ] **Runtime**: Python 3.12+ as declared by `src/tinycua-sdk/pyproject.toml`
- [ ] **Package manager**: `uv`
- [ ] **Test runner**: `cd src/tinycua-sdk && uv run pytest`

---

## Success Criteria — Integration Tests (TDD First)

These tests are written before implementation. Phase 1 is model-only, so the integration tests are SDK-boundary tests that exercise public imports, helper constructors, Pydantic serialization, and canonical message TypedDict compatibility without calling external providers.

```python
# Test file: tests/integration/test_file_attachment_models.py
"""Integration tests for SDK file attachment content models."""

import base64

import pytest
from pydantic import ValidationError

from tinycua_sdk.agent.events import ToolResultMessage, UserMessage
from tinycua_sdk.models import ContentPart, FileAttachment


def test_file_attachment_from_path_flows_into_user_message(tmp_path):
    """A local image attachment can be embedded in a canonical user message."""
    image_path = tmp_path / "photo.jpg"
    image_bytes = b"\xff\xd8\xff\xe0tinycua\xff\xd9"
    image_path.write_bytes(image_bytes)

    attachment = FileAttachment.from_path(image_path)
    content = [
        ContentPart(type="text", text="What is in this image?"),
        ContentPart(type="file", file=attachment),
    ]
    message: UserMessage = {"role": "user", "content": content}

    assert attachment.data == base64.b64encode(image_bytes).decode("ascii")
    assert attachment.mime_type == "image/jpeg"
    assert attachment.filename == "photo.jpg"
    assert message["content"][1].file == attachment


def test_file_attachment_from_bytes_and_url_round_trip_serialization():
    """Bytes and URL helpers produce serializable attachment content parts."""
    byte_attachment = FileAttachment.from_bytes(
        b"hello", mime_type="text/plain", filename="hello.txt"
    )
    url_attachment = FileAttachment.from_url(
        "https://example.com/report.pdf",
        mime_type="application/pdf",
        filename="report.pdf",
    )

    byte_part = ContentPart(type="file", file=byte_attachment)
    url_part = ContentPart.model_validate(
        ContentPart(type="file", file=url_attachment).model_dump()
    )

    assert byte_attachment.data == base64.b64encode(b"hello").decode("ascii")
    assert url_part.file is not None
    assert url_part.file.url == "https://example.com/report.pdf"
    assert url_part.file.data is None


def test_tool_result_message_accepts_file_content_parts():
    """Tool results can carry generated file attachments back to the loop."""
    attachment = FileAttachment.from_bytes(
        b"generated", mime_type="application/octet-stream", filename="artifact.bin"
    )
    message: ToolResultMessage = {
        "role": "tool_result",
        "call_id": "call_123",
        "content": [ContentPart(type="file", file=attachment)],
    }

    assert message["content"][0].file.filename == "artifact.bin"


def test_invalid_content_part_and_empty_attachment_are_rejected():
    """Pydantic validation enforces attachment and content-part invariants."""
    with pytest.raises(ValidationError):
        FileAttachment(mime_type="image/png")

    with pytest.raises(ValidationError):
        ContentPart(type="text")

    with pytest.raises(ValidationError):
        ContentPart(
            type="file",
            text="not allowed for file parts",
            file=FileAttachment.from_url("https://example.com/a.png", "image/png"),
        )


def test_from_path_streaming_matches_non_streaming_output(tmp_path):
    """stream=True uses chunked reading while returning identical base64 data."""
    data_path = tmp_path / "payload.bin"
    payload = (b"0123456789abcdef" * 1024) + b"tail"
    data_path.write_bytes(payload)

    regular = FileAttachment.from_path(data_path, mime_type="application/octet-stream")
    streamed = FileAttachment.from_path(
        data_path, mime_type="application/octet-stream", stream=True
    )

    assert streamed.data == regular.data
    assert streamed.data == base64.b64encode(payload).decode("ascii")
```

### Key Test Scenarios

- [ ] **Local file attachment in `UserMessage`**: proves `from_path()` encodes bytes, detects MIME type, preserves filename, and the canonical `UserMessage.content` union accepts `list[ContentPart]`.
- [ ] **Bytes and URL helper serialization**: proves `from_bytes()`, `from_url()`, and Pydantic model dump/validate round trips work for attachment content.
- [ ] **Tool result attachment content**: proves `ToolResultMessage.content` accepts structured parts for generated artifacts.
- [ ] **Validation edge cases**: rejects attachments with no source (`data`, `url`, or `file_id`) and content parts missing the field required by their `type`.
- [ ] **Streaming parity**: proves `from_path(stream=True)` returns the same base64 payload as the non-streaming path while exercising the chunked code path.
- [ ] **TypedDict annotation validation**: proves that `UserMessage.__annotations__["content"]` / `ToolResultMessage.__annotations__["content"]` resolve to `str | list[ContentPart]` via `typing.get_type_hints()` / `typing.get_args()`, ensuring the union type is correctly widened beyond runtime dict-assignment tests alone.

## Verification Plan

### Automated Tests

- [ ] Integration boundary tests above: `cd src/tinycua-sdk && uv run pytest tests/integration/test_file_attachment_models.py`
- [ ] Unit tests for `FileAttachment` and `ContentPart`: `cd src/tinycua-sdk && uv run pytest tests/unit/test_file_attachment.py`
- [ ] Canonical schema tests after widening `UserMessage` / `ToolResultMessage`: `cd src/tinycua-sdk && uv run pytest tests/unit/test_canonical_schema.py`
- [ ] Full SDK suite for regressions: `cd src/tinycua-sdk && uv run pytest`

### Manual Verification

- [ ] In a Python REPL or small script, import `FileAttachment` and `ContentPart` from `tinycua_sdk.models` and build a text+file user message.
- [ ] Confirm existing plain-string `UserMessage` and `ToolResultMessage` examples still run unchanged.

### Performance Considerations

- [ ] Add a unit/integration test that exercises `from_path(stream=True)` on a file larger than the chunk size and checks output parity.
- [ ] Keep `stream=True` chunked internally; Phase 1 still returns a single base64 string, so true lazy streaming and provider upload streaming remain deferred.

## Proposed Changes

### Attachment Models

#### [NEW] `src/tinycua-sdk/tinycua_sdk/models/attachment.py`

- **Description**: Define `FileAttachment` and `ContentPart` Pydantic models.
- **Rationale**: Provides the canonical file and multimodal content abstractions required by the spec.
- **Implementation details**:
  - `FileAttachment` fields: `data: str | None = None`, `mime_type: str`, `filename: str | None = None`, `url: str | None = None`, `file_id: str | None = None`.
  - Use a Pydantic v2 `@model_validator(mode="after")` rather than a single-field validator so the “at least one of data/url/file_id” invariant is evaluated after all fields are populated.
  - `from_bytes()` base64-encodes bytes with `base64.b64encode(...).decode("ascii")`.
  - `from_url()` stores URL, MIME type, and optional filename without fetching remote content.
  - `from_path()` accepts `str | Path`, preserves `Path.name`, uses caller-provided MIME type when present, otherwise falls back from `mimetypes.guess_type()` to `application/octet-stream`, and raises `FileNotFoundError` naturally for missing paths.
  - For `stream=True`, read binary content in chunks and base64-encode incrementally while preserving correct output for arbitrary chunk boundaries.
  - `ContentPart` keeps the design’s single-class API with `type: Literal["text", "file"]`, `text: str | None`, and `file: FileAttachment | None`, plus model validation that text parts require `text` and file parts require `file`.

#### [MODIFY] `src/tinycua-sdk/tinycua_sdk/models/__init__.py`

- **Description**: Import and export `FileAttachment` and `ContentPart` in `__all__`.
- **Rationale**: Enables ergonomic public imports via `from tinycua_sdk.models import FileAttachment, ContentPart`.

### Canonical Agent Events

#### [MODIFY] `src/tinycua-sdk/tinycua_sdk/agent/events.py`

- **Description**: Import `ContentPart` and update message content types.
- **Rationale**: Makes canonical input message types accept structured multimodal content while preserving existing strings.
- **Implementation details**:
  - `UserMessage.content`: `str | list[ContentPart]`.
  - `ToolResultMessage.content`: `str | list[ContentPart]`.
  - Leave `SystemMessage` and `AssistantMessage` unchanged for Phase 1.
  - Add `ContentPart` to imports only; no provider translation behavior changes in this phase.

### Tests

#### [NEW] `src/tinycua-sdk/tests/integration/test_file_attachment_models.py`

- **Description**: Add integration-boundary tests from the TDD success criteria.
- **Rationale**: Proves the feature works through public SDK imports and canonical event types before implementation.

#### [NEW] `src/tinycua-sdk/tests/unit/test_file_attachment.py`

- **Description**: Add focused unit tests for model constructors, MIME fallback, missing file errors, validation errors, serialization round trips, and streaming parity.
- **Rationale**: Covers edge cases and provides fast feedback for the core model behavior.

#### [MODIFY] `src/tinycua-sdk/tests/unit/test_canonical_schema.py`

- **Description**: Add tests that `UserMessage` and `ToolResultMessage` still accept plain strings and now accept `list[ContentPart]`. MUST also include annotation-inspection tests using `typing.get_type_hints()` and `typing.get_args()` to verify that `UserMessage.__annotations__["content"]` and `ToolResultMessage.__annotations__["content"]` resolve to `str | list[ContentPart]`. This protects against silent regressions where the TypedDict definition is accidentally narrowed back to `str`.
- **Rationale**: Protects backward compatibility while documenting the widened message contract. Annotation inspection catches type-level regressions that runtime dict-assignment tests cannot detect.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua_sdk.models.attachment` | New | Canonical Pydantic models and factory helpers for file attachments and content parts |
| `tinycua_sdk.models` | Modify | Public re-export of `FileAttachment` and `ContentPart` |
| `tinycua_sdk.agent.events` | Modify | Canonical `UserMessage` and `ToolResultMessage` content fields widened to `str | list[ContentPart]` |
| Provider translation layers | No change | Explicitly deferred to Phase 2+ |

## Data Model Changes

```python
class FileAttachment(BaseModel):
    data: str | None = None
    mime_type: str
    filename: str | None = None
    url: str | None = None
    file_id: str | None = None


class ContentPart(BaseModel):
    type: Literal["text", "file"]
    text: str | None = None
    file: FileAttachment | None = None


class UserMessage(TypedDict):
    role: Literal["user"]
    content: str | list[ContentPart]


class ToolResultMessage(TypedDict):
    role: Literal["tool_result"]
    call_id: str
    content: str | list[ContentPart]
```

## API Changes

### New Endpoints

No HTTP API endpoints are added.

### Modified Endpoints

No HTTP API endpoints are modified.

### New Python APIs

| API | Description |
|-----|-------------|
| `FileAttachment.from_path(path, mime_type=None, stream=False)` | Build an attachment from local file bytes with MIME detection and base64 data |
| `FileAttachment.from_bytes(data, mime_type, filename=None)` | Build an attachment from bytes supplied by the caller |
| `FileAttachment.from_url(url, mime_type, filename=None)` | Build an attachment that references a public URL |
| `ContentPart(type="text", text=...)` | Represent a text content part |
| `ContentPart(type="file", file=...)` | Represent a file content part |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | `>=2.6.0` | Existing dependency for `BaseModel` and validation |

No new external package dependencies are required; use Python standard-library modules `base64`, `mimetypes`, and `pathlib`.

### Internal Dependencies

- [ ] Depends on the existing `tinycua_sdk.models` package and `tinycua_sdk.agent.events` module.
- [ ] Blocks Phase 2+ provider translation work that maps file content to OpenAI-native request formats.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Changing canonical TypedDict imports introduces circular imports | Medium | Keep attachment models independent of `agent.events`; import only from `models.attachment` into `events.py` |
| Pydantic validation fails to see all attachment fields | Medium | Use `@model_validator(mode="after")` for cross-field invariants |
| Base64 chunking corrupts output when chunk boundaries are not multiples of three | High | Buffer remainder bytes between chunks or use a chunk size divisible by three; verify `stream=True` parity with non-streaming output |
| Backward-compatible string message handling regresses | High | Keep union type order simple and run existing canonical schema and full SDK tests unchanged |
| Scope creep into provider translation | Medium | Do not modify provider clients or translation functions in Phase 1; document that Phase 2+ handles provider-native formats |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-20*
