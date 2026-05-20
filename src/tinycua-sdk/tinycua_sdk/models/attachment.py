"""Canonical SDK models for file attachments and structured multimodal content.

Provides :class:`FileAttachment` for representing file data (base64-encoded
bytes, URL references, or cached file IDs) and :class:`ContentPart` for
multimodal content parts (text or file) within canonical agent message types.
"""

import base64
import binascii
import mimetypes
import pathlib
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

# Chunk size for streaming file reads (divisible by 3 so each chunk
# base64-encodes independently without padding issues at boundaries).
_CHUNK_SIZE = 3 * 1024


class FileAttachment(BaseModel):
    """Represents a file attachment within a multimodal content part.

    Exactly one of ``data``, ``url``, or ``file_id`` must be provided
    (the *source field*). This invariant is enforced by a model validator.

    Attributes:
        data: Base64-encoded file bytes.
        mime_type: MIME type of the file (e.g. ``"image/png"``).
        filename: Optional display filename.
        url: Public URL where the file content can be fetched.
        file_id: Provider-side cached file identifier.
    """

    data: str | None = None
    mime_type: str
    filename: str | None = None
    url: str | None = None
    file_id: str | None = None

    @field_validator("data")
    @classmethod
    def _validate_data_is_base64(cls, v: str | None) -> str | None:
        """Validate that when data is provided, it is valid base64-encoded.

        Uses ``validate=True`` so that non-base64 characters and incorrect
        padding raise a ``ValidationError``.  An empty string is valid
        (it represents zero bytes).
        """
        if v is not None:
            try:
                base64.b64decode(v, validate=True)
            except (ValueError, binascii.Error) as exc:
                msg = "data must be a valid base64-encoded string"
                raise ValueError(msg) from exc
        return v

    @model_validator(mode="after")
    def _validate_exactly_one_source(self) -> "FileAttachment":
        """Ensure exactly one of data, url, or file_id is provided."""
        sources = [self.data, self.url, self.file_id]
        provided = [s for s in sources if s is not None]
        if len(provided) == 0:
            msg = "Exactly one of data, url, or file_id is required"
            raise ValueError(msg)
        if len(provided) > 1:
            msg = "Only one of data, url, or file_id may be set"
            raise ValueError(msg)
        return self

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> "FileAttachment":
        """Build an attachment from raw bytes with base64 encoding.

        Args:
            data: Raw file bytes.
            mime_type: MIME type of the file.
            filename: Optional display filename.

        Returns:
            A new FileAttachment with base64-encoded data.
        """
        encoded = base64.b64encode(data).decode("ascii")
        return cls(data=encoded, mime_type=mime_type, filename=filename)

    @classmethod
    def from_url(
        cls,
        url: str,
        mime_type: str,
        filename: str | None = None,
    ) -> "FileAttachment":
        """Build an attachment from a public URL without fetching content.

        Args:
            url: Public URL pointing to the file.
            mime_type: MIME type of the file.
            filename: Optional display filename.

        Returns:
            A new FileAttachment with the URL reference.
        """
        return cls(url=url, mime_type=mime_type, filename=filename)

    @classmethod
    def from_path(
        cls,
        path: str | pathlib.Path,
        mime_type: str | None = None,
        stream: bool = False,
    ) -> "FileAttachment":
        """Build an attachment from a local file path.

        Reads the file, base64-encodes its contents, and auto-detects the
        MIME type from the file extension when ``mime_type`` is not provided.

        Args:
            path: Local filesystem path (``str`` or ``pathlib.Path``).
            mime_type: Optional explicit MIME type.  When omitted, the type
                is guessed from the file extension, falling back to
                ``application/octet-stream``.
            stream: When ``True``, read the file in chunks instead of loading
                the entire file into memory at once.  The returned base64
                data is identical to the non-streaming path.

        Returns:
            A new FileAttachment with base64-encoded data, detected or
            provided MIME type, and the file name preserved from the path.

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        path_obj = pathlib.Path(path)
        resolved_mime = mime_type or mimetypes.guess_type(path_obj)[0] or "application/octet-stream"

        if stream:
            encoded = cls._read_and_encode_streaming(path_obj)
        else:
            encoded = base64.b64encode(path_obj.read_bytes()).decode("ascii")

        return cls(
            data=encoded,
            mime_type=resolved_mime,
            filename=path_obj.name,
        )

    @classmethod
    def _read_and_encode_streaming(cls, path: pathlib.Path) -> str:
        """Read a file in chunks and return the concatenated base64 string.

        Uses a chunk size divisible by 3 so that each chunk can be
        independently base64-encoded without padding issues at chunk
        boundaries.
        """
        chunks: list[str] = []
        with path.open("rb") as f:
            while True:
                chunk = f.read(_CHUNK_SIZE)
                if not chunk:
                    break
                chunks.append(base64.b64encode(chunk).decode("ascii"))
        return "".join(chunks)


class ContentPart(BaseModel):
    """A single content part within a multimodal message.

    Supports text parts (``type="text"``) and file parts
    (``type="file"``).  Cross-field validation ensures that text parts
    include ``text`` and file parts include ``file``, and that the
    irrelevant field for each variant is not set.

    Attributes:
        type: ``"text"`` for text content, ``"file"`` for file attachment.
        text: Text content (required when ``type="text"``).
        file: File attachment (required when ``type="file"``).
    """

    type: Literal["text", "file"]
    text: str | None = None
    file: FileAttachment | None = None

    @field_validator("text")
    @classmethod
    def _text_not_empty_when_set(cls, v: str | None) -> str | None:
        """Allow text to be None or a non-empty string."""
        return v

    @model_validator(mode="after")
    def _validate_content_part_fields(self) -> "ContentPart":
        """Ensure correct fields are set based on part type."""
        if self.type == "text":
            if self.text is None:
                msg = "Text content part requires 'text' field"
                raise ValueError(msg)
            if self.file is not None:
                msg = "Text content part must not have 'file' set"
                raise ValueError(msg)
        elif self.type == "file":
            if self.file is None:
                msg = "File content part requires 'file' field"
                raise ValueError(msg)
            if self.text is not None:
                msg = "File content part must not have 'text' set"
                raise ValueError(msg)
        return self
