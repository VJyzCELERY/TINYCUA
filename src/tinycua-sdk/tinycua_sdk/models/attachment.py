"""Canonical SDK models for file attachments and structured multimodal content.

Provides :class:`FileAttachment` for representing file data (base64-encoded
bytes, URL references, or cached file IDs), :class:`StreamingFileAttachment`
for stream-aware file reading without full buffering, and :class:`ContentPart`
for multimodal content parts (text or file) within canonical agent message
types.
"""

import base64
import binascii
import hashlib
import mimetypes
import pathlib
from typing import ClassVar, Iterator, Literal

from pydantic import BaseModel, PrivateAttr, field_validator, model_validator


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
        """Ensure exactly one of data, url, or file_id is provided.

        StreamingFileAttachment subclasses use _file_path as their source
        instead — they skip this invariant.
        """
        # StreamingFileAttachment uses _file_path as source instead
        if isinstance(self, StreamingFileAttachment):
            return self
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

        When ``stream=True``, returns a :class:`StreamingFileAttachment`
        that reads file content on demand in chunks instead of loading the
        entire file into memory. The ``.data`` field is always ``None`` on a
        ``StreamingFileAttachment`` — use ``iter_base64_chunks()`` or
        ``iter_raw_chunks()`` instead.

        Args:
            path: Local filesystem path (``str`` or ``pathlib.Path``).
            mime_type: Optional explicit MIME type.  When omitted, the type
                is guessed from the file extension, falling back to
                ``application/octet-stream``.
            stream: When ``True``, returns a ``StreamingFileAttachment``
                instead of loading the full file into memory.

        Returns:
            A new ``FileAttachment`` (or ``StreamingFileAttachment`` when
            ``stream=True``) with detected/provided MIME type and the file
            name preserved from the path.

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        path_obj = pathlib.Path(path)
        if not path_obj.is_file():
            raise FileNotFoundError(f"Not a regular file: {path_obj}")
        # Resolve to an absolute path so that streaming operations are not
        # affected by later changes to the process working directory.
        resolved = path_obj.resolve()
        resolved_mime = mime_type or mimetypes.guess_type(resolved)[0] or "application/octet-stream"

        if stream:
            streaming = StreamingFileAttachment(
                data=None,
                mime_type=resolved_mime,
                filename=resolved.name,
            )
            streaming._file_path = resolved
            return streaming

        encoded = base64.b64encode(resolved.read_bytes()).decode("ascii")
        return cls(
            data=encoded,
            mime_type=resolved_mime,
            filename=path_obj.name,
        )


class StreamingFileAttachment(FileAttachment):
    """Subclass of :class:`FileAttachment` for stream-aware file reading.

    The ``data`` field is always ``None``; file content is read on demand
    in chunks from the underlying file path via :meth:`iter_base64_chunks`
    or :meth:`iter_raw_chunks`. This avoids loading the full file into
    memory.

    The parent class invariant requiring exactly one of ``data``, ``url``,
    or ``file_id`` is relaxed: streaming attachments are backed by a
    ``_file_path`` instead.

    Attributes:
        _file_path: Path to the file on disk for chunked reading.
        _CHUNK_SIZE: Chunk size in bytes (divisible by 3 for base64 alignment).
    """

    _file_path: pathlib.Path | None = PrivateAttr(default=None)
    _CHUNK_SIZE: ClassVar[int] = 3 * 1024

    @model_validator(mode="after")
    def _validate_streaming_source(self) -> "StreamingFileAttachment":
        """Validate streaming attachment source contract.

        Ensures data is None and url/file_id are not mixed with the
        file path source. The parent ``_validate_exactly_one_source``
        already skips validation for streaming attachments.
        """
        if self.data is not None:
            raise ValueError(
                "StreamingFileAttachment must have data=None. "
                "Use iter_base64_chunks() or iter_raw_chunks() instead."
            )
        if self.url is not None or self.file_id is not None:
            raise ValueError(
                "StreamingFileAttachment should not have url or file_id set. "
                "Use _file_path instead."
            )
        return self

    def iter_raw_chunks(self) -> Iterator[bytes]:
        """Yield raw bytes chunks from the file.

        Reads the file in ``_CHUNK_SIZE`` byte chunks without base64
        encoding. Suitable for direct upload via ``client.files.create()``.

        Yields:
            Raw bytes chunks.

        Raises:
            ValueError: If ``_file_path`` is not set.
        """
        if self._file_path is None:
            raise ValueError(
                "StreamingFileAttachment has no _file_path. "
                "Create via FileAttachment.from_path(path, stream=True)."
            )
        with self._file_path.open("rb") as f:
            while True:
                chunk = f.read(self._CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    def iter_base64_chunks(self) -> Iterator[str]:
        """Yield base64-encoded chunks from the file.

        Each chunk is independently base64-encoded. The concatenation
        of all yielded strings produces the same result as encoding
        the full file at once.

        Yields:
            Base64-encoded chunk strings.

        Raises:
            ValueError: If ``_file_path`` is not set.
        """
        for raw_chunk in self.iter_raw_chunks():
            yield base64.b64encode(raw_chunk).decode("ascii")

    def hash_content(self) -> str:
        """Compute the SHA-256 hash of the full file content.

        Reads the file in chunks so the full content is never held in
        memory at once. The returned hash matches the hash that would
        be produced by hashing the full file with SHA-256.

        Returns:
            SHA-256 hex digest of the raw file bytes.

        Raises:
            ValueError: If ``_file_path`` is not set.
        """
        if self._file_path is None:
            raise ValueError(
                "StreamingFileAttachment has no _file_path. "
                "Create via FileAttachment.from_path(path, stream=True)."
            )
        sha = hashlib.sha256()
        for chunk in self.iter_raw_chunks():
            sha.update(chunk)
        return sha.hexdigest()


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
        if v is not None and v == "":
            raise ValueError("text must not be empty when type='text'")
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
