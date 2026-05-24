"""Unit tests for FileAttachment and ContentPart models.

Tests cover model construction, source-field mutex, factory helpers,
serialization round trips, and streaming parity.
"""

import base64
import hashlib

import pytest
from pydantic import ValidationError

from tinycua_sdk.models import ContentPart, FileAttachment


# ── FileAttachment direct construction ───────────────────────────────────────


class TestFileAttachmentConstruction:
    """Direct construction and source-field mutex validation."""

    def test_data_only_attachment(self):
        """Attachment with only data and mime_type is valid."""
        attachment = FileAttachment(
            data=base64.b64encode(b"hello").decode("ascii"),
            mime_type="text/plain",
        )
        assert attachment.data is not None
        assert attachment.mime_type == "text/plain"
        assert attachment.filename is None
        assert attachment.url is None
        assert attachment.file_id is None

    def test_url_only_attachment(self):
        """Attachment with only url and mime_type is valid."""
        attachment = FileAttachment(
            url="https://example.com/file.txt",
            mime_type="text/plain",
        )
        assert attachment.url == "https://example.com/file.txt"
        assert attachment.data is None
        assert attachment.file_id is None

    def test_file_id_only_attachment(self):
        """Attachment with only file_id and mime_type is valid."""
        attachment = FileAttachment(
            file_id="file_abc123",
            mime_type="image/png",
            filename="img.png",
        )
        assert attachment.file_id == "file_abc123"
        assert attachment.data is None
        assert attachment.url is None

    def test_empty_attachment_rejected(self):
        """Attachment without any source field is rejected."""
        with pytest.raises(ValidationError):
            FileAttachment(mime_type="image/png")

    def test_multi_source_attachment_rejected(self):
        """Attachment with more than one source field is rejected."""
        with pytest.raises(ValidationError):
            FileAttachment(
                mime_type="image/png",
                data="base64data",
                url="https://example.com/img.png",
            )

    def test_data_and_file_id_rejected(self):
        """Attachment with both data and file_id is rejected."""
        with pytest.raises(ValidationError):
            FileAttachment(
                mime_type="image/png",
                data=base64.b64encode(b"data").decode("ascii"),
                file_id="file_123",
            )

    def test_url_and_file_id_rejected(self):
        """Attachment with both url and file_id is rejected."""
        with pytest.raises(ValidationError):
            FileAttachment(
                mime_type="image/png",
                url="https://example.com/img.png",
                file_id="file_123",
            )


# ── FileAttachment.from_path() ───────────────────────────────────────────────


class TestFileAttachmentFromPath:
    """from_path() factory helper tests."""

    def test_from_path_success(self, tmp_path):
        """from_path reads file, base64 encodes, and detects MIME type."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello, world!")
        attachment = FileAttachment.from_path(file_path)

        expected_data = base64.b64encode(b"Hello, world!").decode("ascii")
        assert attachment.data == expected_data
        assert attachment.mime_type == "text/plain"
        assert attachment.filename == "test.txt"

    def test_from_path_missing_file(self, tmp_path):
        """from_path raises FileNotFoundError for missing paths."""
        missing = tmp_path / "nonexistent.txt"
        with pytest.raises(FileNotFoundError):
            FileAttachment.from_path(missing)

    def test_from_path_mime_fallback(self, tmp_path):
        """from_path falls back to application/octet-stream for unknown extensions."""
        file_path = tmp_path / "payload.bin"
        file_path.write_bytes(b"\x00\x01\x02")
        attachment = FileAttachment.from_path(file_path)

        assert attachment.mime_type == "application/octet-stream"

    def test_from_path_with_custom_mime(self, tmp_path):
        """from_path uses caller-provided MIME type when given."""
        file_path = tmp_path / "script.xyz"
        file_path.write_text("custom")
        attachment = FileAttachment.from_path(file_path, mime_type="text/x-custom")

        assert attachment.mime_type == "text/x-custom"

    def test_from_path_filename_preserved(self, tmp_path):
        """from_path preserves the filename from the path."""
        file_path = tmp_path / "my_document.pdf"
        file_path.write_bytes(b"%PDF-1.4")
        attachment = FileAttachment.from_path(file_path)

        assert attachment.filename == "my_document.pdf"

    def test_from_path_accepts_str(self, tmp_path):
        """from_path accepts string paths too."""
        file_path = tmp_path / "data.csv"
        file_path.write_text("a,b,c")
        attachment = FileAttachment.from_path(str(file_path))

        assert attachment.filename == "data.csv"
        assert attachment.mime_type == "text/csv"

    def test_from_path_jpeg_mime_detection(self, tmp_path):
        """from_path detects image/jpeg for .jpg files."""
        file_path = tmp_path / "photo.jpg"
        file_path.write_bytes(b"\xff\xd8\xff\xe0")
        attachment = FileAttachment.from_path(file_path)

        assert attachment.mime_type == "image/jpeg"


# ── FileAttachment.from_bytes() ──────────────────────────────────────────────


class TestFileAttachmentFromBytes:
    """from_bytes() factory helper tests."""

    def test_from_bytes_basic(self):
        """from_bytes base64-encodes provided bytes."""
        attachment = FileAttachment.from_bytes(
            b"hello bytes",
            mime_type="application/octet-stream",
        )
        assert attachment.data == base64.b64encode(b"hello bytes").decode("ascii")
        assert attachment.mime_type == "application/octet-stream"
        assert attachment.filename is None

    def test_from_bytes_with_filename(self):
        """from_bytes accepts an optional filename."""
        attachment = FileAttachment.from_bytes(
            b"data",
            mime_type="text/plain",
            filename="note.txt",
        )
        assert attachment.filename == "note.txt"

    def test_from_bytes_required_mime_type(self):
        """from_bytes requires a mime_type argument."""
        with pytest.raises(TypeError):
            FileAttachment.from_bytes(b"data")  # type: ignore[call-arg]

    def test_from_bytes_empty_bytes(self):
        """from_bytes handles empty bytes gracefully."""
        attachment = FileAttachment.from_bytes(
            b"",
            mime_type="application/octet-stream",
        )
        assert attachment.data == base64.b64encode(b"").decode("ascii")


# ── FileAttachment.from_url() ────────────────────────────────────────────────


class TestFileAttachmentFromUrl:
    """from_url() factory helper tests."""

    def test_from_url_basic(self):
        """from_url stores URL and MIME type without fetching."""
        attachment = FileAttachment.from_url(
            "https://example.com/report.pdf",
            mime_type="application/pdf",
        )
        assert attachment.url == "https://example.com/report.pdf"
        assert attachment.mime_type == "application/pdf"
        assert attachment.data is None
        assert attachment.filename is None

    def test_from_url_with_filename(self):
        """from_url accepts an optional filename."""
        attachment = FileAttachment.from_url(
            "https://example.com/img.png",
            mime_type="image/png",
            filename="img.png",
        )
        assert attachment.filename == "img.png"

    def test_from_url_does_not_fetch(self):
        """from_url does not attempt to fetch the URL content."""
        attachment = FileAttachment.from_url(
            "https://nonexistent.example.com/file.pdf",
            mime_type="application/pdf",
        )
        assert attachment.url == "https://nonexistent.example.com/file.pdf"
        assert attachment.data is None


# ── ContentPart ──────────────────────────────────────────────────────────────


class TestContentPart:
    """ContentPart model tests."""

    def test_text_part(self):
        """Text content part stores text."""
        part = ContentPart(type="text", text="Hello")
        assert part.type == "text"
        assert part.text == "Hello"
        assert part.file is None

    def test_file_part(self):
        """File content part stores a FileAttachment."""
        attachment = FileAttachment.from_bytes(
            b"data", mime_type="text/plain", filename="hello.txt"
        )
        part = ContentPart(type="file", file=attachment)
        assert part.type == "file"
        assert part.file is not None
        assert part.file.filename == "hello.txt"
        assert part.text is None

    def test_text_part_missing_text_rejected(self):
        """Text part without text is rejected."""
        with pytest.raises(ValidationError):
            ContentPart(type="text")

    def test_file_part_missing_file_rejected(self):
        """File part without file is rejected."""
        with pytest.raises(ValidationError):
            ContentPart(type="file")

    def test_text_part_with_file_rejected(self):
        """Text part with file field set is rejected."""
        attachment = FileAttachment.from_bytes(
            b"data", mime_type="text/plain"
        )
        with pytest.raises(ValidationError):
            ContentPart(type="text", text="hello", file=attachment)

    def test_file_part_with_text_rejected(self):
        """File part with text field set is rejected."""
        attachment = FileAttachment.from_bytes(
            b"data", mime_type="text/plain"
        )
        with pytest.raises(ValidationError):
            ContentPart(type="file", text="not allowed", file=attachment)

    def test_serialization_round_trip_text(self):
        """Text ContentPart survives model_dump/model_validate round trip."""
        original = ContentPart(type="text", text="Hello!")
        data = original.model_dump()
        restored = ContentPart.model_validate(data)
        assert restored.type == "text"
        assert restored.text == "Hello!"
        assert restored.file is None

    def test_serialization_round_trip_file(self):
        """File ContentPart survives model_dump/model_validate round trip."""
        attachment = FileAttachment.from_bytes(
            b"data", mime_type="text/plain", filename="hello.txt"
        )
        original = ContentPart(type="file", file=attachment)
        data = original.model_dump()
        restored = ContentPart.model_validate(data)
        assert restored.type == "file"
        assert restored.file is not None
        assert restored.file.filename == "hello.txt"
        assert restored.file.data == base64.b64encode(b"data").decode("ascii")


# ── Streaming parity ─────────────────────────────────────────────────────────


class TestStreamingParity:
    """Streaming vs non-streaming from_path parity tests."""

    def test_streaming_returns_streaming_attachment(self, tmp_path):
        """Stream=True returns StreamingFileAttachment with data=None."""
        file_path = tmp_path / "small.bin"
        file_path.write_bytes(b"small payload")
        streamed = FileAttachment.from_path(file_path, stream=True)
        assert streamed.data is None
        # Content is readable via hash
        assert len(streamed.hash_content()) == 64  # SHA-256 hex

    def test_streaming_hash_matches_non_streaming_content(self, tmp_path):
        """Streaming hash matches SHA-256 of non-streaming decoded data."""
        import hashlib
        file_path = tmp_path / "large.bin"
        payload = (b"ABCDEFGHIJ" * 1000) + b"tail"
        file_path.write_bytes(payload)
        regular = FileAttachment.from_path(file_path)
        streamed = FileAttachment.from_path(file_path, stream=True)
        # Hash of streamed content should match hash of regular decoded bytes
        regular_hash = hashlib.sha256(
            base64.b64decode(regular.data)  # type: ignore[arg-type]
        ).hexdigest()
        assert streamed.hash_content() == regular_hash

    def test_streaming_preserves_mime_and_filename(self, tmp_path):
        """Stream=True preserves MIME type and filename."""
        file_path = tmp_path / "streamed.dat"
        file_path.write_bytes(b"x" * 100)
        attachment = FileAttachment.from_path(
            file_path, mime_type="application/x-custom", stream=True
        )
        assert attachment.mime_type == "application/x-custom"
        assert attachment.filename == "streamed.dat"
        assert attachment.data is None  # Streaming contract

    def test_streaming_empty_file(self, tmp_path):
        """Stream=True handles empty files correctly."""
        file_path = tmp_path / "empty.bin"
        file_path.write_bytes(b"")
        attachment = FileAttachment.from_path(file_path, stream=True)
        assert attachment.data is None
        assert attachment.hash_content() == hashlib.sha256(b"").hexdigest()

    def test_streaming_missing_file(self, tmp_path):
        """Stream=True raises FileNotFoundError for missing files."""
        missing = tmp_path / "missing.bin"
        with pytest.raises(FileNotFoundError):
            FileAttachment.from_path(missing, stream=True)
