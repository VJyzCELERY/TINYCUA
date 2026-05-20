# Design Document: SDK-wide File Attachment Support

**Spec**: `src/tinycua-sdk/specs/sdk-file-attachment-phase1/spec.md`
**Status**: Complete
**Last Updated**: 2026-05-20

---

## Overview

This design adds a canonical `FileAttachment` Pydantic model, a `ContentPart` tagged model with explicit validators for multimodal messages, and updates the canonical `UserMessage` / `ToolResultMessage` TypedDicts to accept `list[ContentPart]` in addition to plain `str`. The design also includes ergonomic factory methods (`from_path`, `from_bytes`, `from_url`) for constructing file attachments. All changes live in `tinycua_sdk/models/` and `tinycua_sdk/agent/events.py`, with no changes to provider translation layers (deferred to Phase 2).

---

## Architecture

### Component Overview

```
Caller Code
    |
    v
FileAttachment.from_path() / from_bytes() / from_url()    ← New factory methods
    |
    v
FileAttachment (Pydantic BaseModel)                       ← New model
ContentPart (Pydantic tagged model with explicit validators) ← New model
    |
    v
UserMessage(content: str | list[ContentPart])              ← Modified TypedDict
ToolResultMessage(content: str | list[ContentPart])        ← Modified TypedDict
    |
    v
Provider translation (unchanged in Phase 1)                ← Phase 2+
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/models/attachment.py` | **New** | `FileAttachment` and `ContentPart` models |
| `tinycua_sdk/models/__init__.py` | Modified | Export new models |
| `tinycua_sdk/agent/events.py` | Modified | Update `UserMessage.content` and `ToolResultMessage.content` type unions |

---

## Data Model

### New Entities

```python
# tinycua_sdk/models/attachment.py

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator


class FileAttachment(BaseModel):
    """Represents a file to be sent to an LLM provider."""

    data: str | None = None        # base64-encoded file content
    mime_type: str                  # MIME type (e.g., "image/jpeg")
    filename: str | None = None     # original filename
    url: str | None = None          # public URL to the file
    file_id: str | None = None      # provider-assigned file ID (for caching)

    @model_validator(mode="after")
    def _validate_source_fields(self):
        """Exactly one of data, url, or file_id must be set."""
        sources = [self.data, self.url, self.file_id]
        provided = [s for s in sources if s is not None]
        if len(provided) == 0:
            raise ValueError("At least one of 'data', 'url', or 'file_id' must be provided")
        if len(provided) > 1:
            raise ValueError("Only one of 'data', 'url', or 'file_id' may be provided")
        return self

    @classmethod
    def from_path(cls, path: str | Path, mime_type: str | None = None, stream: bool = False) -> FileAttachment:
        """Read a file from disk, detect MIME type, base64-encode, and return a FileAttachment."""
        ...

    @classmethod
    def from_bytes(cls, data: bytes, mime_type: str, filename: str | None = None) -> FileAttachment:
        """Create a FileAttachment from raw bytes."""
        ...

    @classmethod
    def from_url(cls, url: str, mime_type: str, filename: str | None = None) -> FileAttachment:
        """Create a FileAttachment from a URL."""
        ...


class ContentPart(BaseModel):
    """A part of a multimodal message."""

    type: Literal["text", "file"]
    text: str | None = None
    file: FileAttachment | None = None

    @model_validator(mode="after")
    def _validate_variant_fields(self):
        """Text parts must have text set; file parts must have file set.
        Incompatible fields for each variant are rejected."""
        if self.type == "text":
            if not self.text:
                raise ValueError("ContentPart(type='text') must have text set")
            if self.file is not None:
                raise ValueError("ContentPart(type='text') must not have file set")
        if self.type == "file":
            if not self.file:
                raise ValueError("ContentPart(type='file') must have file set")
            if self.text is not None:
                raise ValueError("ContentPart(type='file') must not have text set")
        return self
```

### Schema Changes

- **`UserMessage` in `events.py`**: `content` field changes from `str` to `str | list[ContentPart]`; optional `attachments: list[FileAttachment]` field added for the basic message shape (`content: str` + `attachments: list[FileAttachment]`)
- **`ToolResultMessage` in `events.py`**: `content` field changes from `str` to `str | list[ContentPart]`; optional `attachments: list[FileAttachment]` field added
- No migration needed — existing `str`-only usage remains valid via the union type

---

## API / Interface Contracts

### New / Modified Functions

```python
# FileAttachment factory methods
FileAttachment.from_path(
    path: str | Path,
    mime_type: str | None = None,
    stream: bool = False,
) -> FileAttachment

FileAttachment.from_bytes(
    data: bytes,
    mime_type: str,
    filename: str | None = None,
) -> FileAttachment

FileAttachment.from_url(
    url: str,
    mime_type: str,
    filename: str | None = None,
) -> FileAttachment
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| File not found (`from_path`) | `FileNotFoundError` | Propagated from `open()` |
| No data, url, or file_id provided | `ValueError("At least one of 'data', 'url', or 'file_id' must be provided")` | Pydantic validation |
| Multiple source fields provided (data+url, data+file_id, url+file_id) | `ValueError("Only one of 'data', 'url', or 'file_id' may be provided")` | Pydantic validation — source fields are mutually exclusive |
| Unknown MIME type (`from_path`) | Falls back to `"application/octet-stream"` | `mimetypes.guess_type` returns `None` |
| File too large for streaming | Depends on `stream` parameter | Without streaming: loads fully into memory; with streaming: processes in chunks |

---

## Implementation Phases

### Phase 1 — Canonical Models (this phase)

- [ ] Create `tinycua_sdk/models/attachment.py` with `FileAttachment` and `ContentPart`
- [ ] Add `FileAttachment.from_path()`, `from_bytes()`, `from_url()` factory methods
- [ ] Update `tinycua_sdk/agent/events.py`: `UserMessage.content` → `str | list[ContentPart]`
- [ ] Update `tinycua_sdk/agent/events.py`: `ToolResultMessage.content` → `str | list[ContentPart]`
- [ ] Update `tinycua_sdk/models/__init__.py` to export new models
- [ ] Write unit tests for model creation, serialization, and helper methods
- [ ] Verify backward compatibility: all existing tests pass

> **Note**: Phases 2-6 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use Pydantic `BaseModel` for `FileAttachment` and `ContentPart` rather than TypedDicts or dataclasses
   - **Reason**: Pydantic provides built-in validation, serialization, tagged model support with validators, and is already a project dependency
   - **Alternatives Considered**: TypedDicts (no runtime validation), dataclasses (no built-in validation), msgspec (additional dependency)

2. **Decision**: Use a single `ContentPart` model with `type: Literal["text", "file"]` and explicit `@model_validator` enforcement, rather than a Pydantic discriminated union (`Annotated[Union[TextPart, FilePart], Discriminator]`) or separate `TextPart`/`FilePart` class hierarchy
   - **Reason**: Simpler API surface; single `ContentPart` class with tagged `type` field and validators is easier to use and understand than multiple concrete part classes
   - **Alternatives Considered**: Discriminated union via `Annotated[Union[TextPart, FilePart], Field(discriminator="type")]` — more type-safe but more complex for callers and adds schema complexity

3. **Decision**: `UserMessage` and `ToolResultMessage` expose an optional `attachments: NotRequired[list[FileAttachment]]` field in addition to the `content` union
   - **Reason**: Supports the basic message shape (`content: str` + `attachments: list[FileAttachment]`) without requiring callers to use `ContentPart` for simple text-only messages. This is the canonical boundary for provider translation: providers that accept message-level attachment lists can source from this field.
   - **Alternatives Considered**: Only `list[ContentPart]` — forces callers to wrap every message in ContentPart types even for simple text content. Allowing a separate attachments list alongside plain `str` content provides a simpler, more ergonomic entry point.

4. **Decision**: `from_path()` with `stream=True` uses an internal chunked base64 encoder but still returns a single `FileAttachment`
   - **Reason**: Keeps the public API simple. A fully lazy streaming API (async generator of base64 chunks) is conceptually clean but adds complexity that can be deferred to Phase 5
   - **Alternatives Considered**: Returning `AsyncIterator[FileAttachment]` or `AsyncIterator[str]` for streaming — adds caller complexity not yet justified

5. **Decision**: `FileAttachment` source fields (`data`, `url`, `file_id`) are mutually exclusive — exactly one must be provided; multi-source attachments are rejected with `ValidationError`
   - **Reason**: A canonical model should have a single, unambiguous source of file content. Allowing multiple source fields forces provider translation (Phase 2+) to guess which one wins, leading to inconsistent behavior. If multi-source support is needed later, it can be added with explicit precedence rules as a non-breaking extension.
   - **Alternatives Considered**: Allowing multi-source and documenting precedence order — adds complexity without a clear use case for Phase 1.

6. **Decision**: ContentPart model lives in `attachment.py` alongside `FileAttachment` rather than in `events.py`
   - **Reason**: Keeps events.py focused on TypedDict definitions. The `ContentPart` is a data model, not an event shape
   - **Alternatives Considered**: Placing `ContentPart` in `events.py` — would mix model and event concerns

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Breaking existing callers by changing `content` type | Low | High | Use `str | list[ContentPart]` union — all existing `str`-only code compiles and runs unchanged |
| Large files causing OOM in `from_path(stream=False)` | Medium | Medium | Document that `stream=True` should be used for large files; implement chunked reading in streaming mode |
| Tagged model validation complexity in Pydantic v2 | Low | Medium | Pin to Pydantic v2 which has stable `@model_validator` support; add serialization round-trip tests |

---

## Open Questions

*(No open questions — all previously discussed items have been decided and captured in the Technical Decisions above.)*

---

## References

- Spec: `specs/sdk-file-attachment-phase1/spec.md`
- Related issue: [#46](https://github.com/VJyzCELERY/TINYCUA/issues/46) — Implementation: SDK-wide File Attachment Support
