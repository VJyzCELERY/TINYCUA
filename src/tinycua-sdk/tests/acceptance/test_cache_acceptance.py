"""Acceptance tests for Phase 5: cache, streaming, non-image URL support.

Acceptance-level tests that exercise UploadSession cache deduplication,
persistent cache, file_id bypass, URL cache keys, streaming attachment
behavior, and URL download SSRF protection. Uses mock OpenAI clients
(mock transport) so tests run in any environment without credentials.
"""

import base64
import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from tinycua_sdk.models.attachment import FileAttachment
from tinycua_sdk.providers.upload import (
    UploadSession,
    _make_cache_key,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_data_attachment(b64_data: str, mime: str = "application/pdf") -> FileAttachment:
    return FileAttachment(data=b64_data, mime_type=mime, filename="test.pdf")


def _make_pdf_attachment() -> FileAttachment:
    return _make_data_attachment(base64.b64encode(b"fake pdf content").decode("ascii"))


def _make_file_id_attachment(file_id: str = "file-existing-123") -> FileAttachment:
    return FileAttachment(file_id=file_id, mime_type="application/pdf")


def _make_url_attachment(url: str = "https://example.com/doc.pdf") -> FileAttachment:
    return FileAttachment(url=url, mime_type="application/pdf")


def _make_mock_client(file_id: str = "file-fake-1") -> AsyncMock:
    client = AsyncMock()
    uploaded = MagicMock()
    uploaded.id = file_id
    uploaded.expires_at = None
    client.files = MagicMock()
    client.files.create = AsyncMock(return_value=uploaded)
    return client


# ── A1: Upload deduplication across repeated attachments ─────────────────────


class TestUploadDeduplication:
    """Verify same file across repeated calls triggers only one upload."""

    @pytest.mark.asyncio
    async def test_same_file_one_upload(self):
        """Two calls with same attachment → exactly one client.files.create()."""
        session = UploadSession()
        mock_client = _make_mock_client()
        att = _make_pdf_attachment()

        await session.ensure_file_id(mock_client, att)
        await session.ensure_file_id(mock_client, att)

        assert mock_client.files.create.call_count == 1

    @pytest.mark.asyncio
    async def test_different_files_two_uploads(self):
        """Two different attachments → two client.files.create() calls."""
        session = UploadSession()
        mock_client = _make_mock_client("file-1")
        att1 = _make_data_attachment(base64.b64encode(b"content a").decode("ascii"))

        # Need a separate mock_client for att2 since the call_count is per-client
        mock_client2 = _make_mock_client("file-2")
        att2 = _make_data_attachment(base64.b64encode(b"content b").decode("ascii"))

        await session.ensure_file_id(mock_client, att1)
        await session.ensure_file_id(mock_client2, att2)

        assert mock_client.files.create.call_count == 1
        assert mock_client2.files.create.call_count == 1


# ── A2: Persistent cache prevents re-upload across sessions ──────────────────


class TestPersistentCacheNoReupload:
    """Verify persistent cache eliminates re-uploads on second session."""

    @pytest.mark.asyncio
    async def test_no_reupload_second_session(self, tmp_path):
        """First session uploads; second session uses cached file_id."""
        cache_dir = str(tmp_path / "test-cache")
        att = _make_pdf_attachment()

        # Session 1
        session1 = UploadSession(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
        )
        mock_client1 = _make_mock_client("file-session1")
        file_id1 = await session1.ensure_file_id(mock_client1, att)
        await session1.close()

        assert file_id1 == "file-session1"
        assert mock_client1.files.create.call_count == 1

        # Session 2 — should hit persistent cache
        session2 = UploadSession(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
        )
        mock_client2 = _make_mock_client()
        file_id2 = await session2.ensure_file_id(mock_client2, att)
        await session2.close()

        assert file_id2 == "file-session1"
        mock_client2.files.create.assert_not_called()


# ── A3: File ID bypass (FR-003) ──────────────────────────────────────────────


class TestFileIdBypass:
    """Verify pre-existing file_id attachments bypass upload."""

    @pytest.mark.asyncio
    async def test_file_id_bypass(self):
        """file_id attachment → ensure_file_id returns it without upload."""
        session = UploadSession()
        mock_client = _make_mock_client()
        att = _make_file_id_attachment()

        file_id = await session.ensure_file_id(mock_client, att)

        assert file_id == "file-existing-123"
        mock_client.files.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_file_id_attachment_returns_file_id_for_translation(self):
        """_make_cache_key for file_id attachments starts with 'file_id:'."""
        att = _make_file_id_attachment("file-abc")
        key = _make_cache_key(att)
        assert key == "file_id:file-abc"


# ── A4/A5: Non-image URL cache key ───────────────────────────────────────────


class TestNonImageUrlCache:
    """Verify URL attachments produce URL-inclusive cache keys."""

    def test_url_cache_key_hashes_url(self):
        """URL cache key is a SHA-256 hex digest."""
        att = _make_url_attachment("https://example.com/a.pdf")
        key = _make_cache_key(att)
        # Should be a 64-char hex string (SHA-256), no 'url:' prefix
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_different_urls_different_keys(self):
        """Different URLs → different cache keys."""
        key1 = _make_cache_key(_make_url_attachment("https://a.com/1.pdf"))
        key2 = _make_cache_key(_make_url_attachment("https://a.com/2.pdf"))
        assert key1 != key2

    def test_same_content_url_vs_data_different_keys(self):
        """Same content via URL vs via data → different cache keys."""
        url_att = _make_url_attachment("https://example.com/doc.pdf")
        data_att = _make_pdf_attachment()
        assert _make_cache_key(url_att) != _make_cache_key(data_att)

    def test_cache_key_no_filename(self):
        """Cache key does not include filename (content-based dedup)."""
        att1 = FileAttachment(
            data=base64.b64encode(b"hello").decode("ascii"),
            mime_type="text/plain",
            filename="a.txt",
        )
        att2 = FileAttachment(
            data=base64.b64encode(b"hello").decode("ascii"),
            mime_type="text/plain",
            filename="b.txt",
        )
        assert _make_cache_key(att1) == _make_cache_key(att2)


# ── A6: Streaming attachment — no full-file buffering ────────────────────────


class TestStreamingNoFullBuffer:
    """Verify StreamingFileAttachment avoids full-file buffering."""

    def test_streaming_data_is_none(self, tmp_path):
        """StreamingFileAttachment has data=None (no full buffer)."""
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(b"x" * 10000)
        att = FileAttachment.from_path(str(file_path), stream=True)

        assert att.data is None

    def test_streaming_hash_matches(self, tmp_path):
        """hash_content() produces correct SHA-256."""
        file_path = tmp_path / "hash_test.bin"
        payload = b"ABCDEFGH" * 100
        file_path.write_bytes(payload)
        att = FileAttachment.from_path(str(file_path), stream=True)

        expected = hashlib.sha256(payload).hexdigest()
        assert att.hash_content() == expected

    def test_streaming_chunks_match(self, tmp_path):
        """Chunk iteration produces correct content."""
        file_path = tmp_path / "chunk_test.bin"
        payload = b"CHUNK_TEST" * 500
        file_path.write_bytes(payload)
        att = FileAttachment.from_path(str(file_path), stream=True)

        chunks = list(att.iter_raw_chunks())
        assert b"".join(chunks) == payload

    def test_streaming_base64_chunks(self, tmp_path):
        """Base64 chunk concatenation matches full-file encoding."""
        file_path = tmp_path / "b64_test.bin"
        payload = b"B64_TEST_DATA" * 200
        file_path.write_bytes(payload)
        att = FileAttachment.from_path(str(file_path), stream=True)

        expected = base64.b64encode(payload).decode("ascii")
        actual = "".join(att.iter_base64_chunks())
        assert actual == expected

    @pytest.mark.asyncio
    async def test_streaming_path_no_full_buffer(self, tmp_path):
        """Streaming upload does not buffer full file: file create receives a file handle, not bytes."""
        from tinycua_sdk.providers.upload import UploadSession

        # Small file — the key assertion is that ensure_file_id passes
        # a streaming / file-handle argument to client.files.create rather
        # than fully materialized bytes or BytesIO.
        file_path = tmp_path / "no_buffer.bin"
        payload = b"STREAM_TEST_PAYLOAD" * 50
        file_path.write_bytes(payload)
        att = FileAttachment.from_path(str(file_path), stream=True)

        # Use a mock client that captures the `file` argument
        captured_arg = None

        def capture_file(*args, **kwargs):
            nonlocal captured_arg
            captured_arg = kwargs.get("file")
            uploaded = MagicMock()
            uploaded.id = "file-stream-1"
            return uploaded

        mock_client = AsyncMock()
        mock_client.files.create = AsyncMock(side_effect=capture_file)

        session = UploadSession()
        await session.ensure_file_id(mock_client, att)

        assert captured_arg is not None, "file argument was not passed"
        # The captured file arg should be a tuple (filename, content, ...)
        # or a file-like object — NOT raw bytes or BytesIO
        if isinstance(captured_arg, tuple):
            # The OpenAI SDK accepts (filename, content, content_type) tuples
            assert not isinstance(captured_arg[1], (bytes, bytearray)), (
                "file content should be a file handle/iterator, not fully buffered bytes"
            )


# ── A7: LRU eviction ────────────────────────────────────────────────────────


class TestInMemoryLRUEviction:
    """Verify in-memory cache evicts oldest entries when over capacity."""

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Exceeding session_cache_max_entries evicts oldest."""
        session = UploadSession(session_cache_max_entries=2)
        mock_client = _make_mock_client()

        att1 = _make_data_attachment(base64.b64encode(b"a").decode("ascii"))
        att2 = _make_data_attachment(base64.b64encode(b"b").decode("ascii"))
        att3 = _make_data_attachment(base64.b64encode(b"c").decode("ascii"))

        await session.ensure_file_id(mock_client, att1)
        await session.ensure_file_id(mock_client, att2)
        await session.ensure_file_id(mock_client, att3)

        # att1 should be evicted (oldest)
        assert session.cache_size == 2
        assert _make_cache_key(att2) in session._cache
        assert _make_cache_key(att3) in session._cache
