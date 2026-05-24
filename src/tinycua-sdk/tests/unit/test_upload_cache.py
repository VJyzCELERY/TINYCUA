"""Unit tests for UploadSession, PersistentCacheStore, InFlightTracker, and URL download.

Tests cover cache hit/miss, content dedup, concurrent dedup, LRU eviction,
persistent store write-read cycle, corruption recovery, graceful degradation,
and SSRF protections.
"""

import asyncio
import base64
import os
import socket
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tinycua_sdk.models.attachment import FileAttachment, StreamingFileAttachment
from tinycua_sdk.providers.upload import (
    InFlightTracker,
    PersistentCacheStore,
    UploadResult,
    UploadSession,
    _PinnedNetworkBackend,
    _download_url_content,
    _make_cache_key,
    _validate_url_safety,
    _verify_connected_peer,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_data_attachment(b64_data: str, mime: str = "application/pdf") -> FileAttachment:
    return FileAttachment(data=b64_data, mime_type=mime, filename="test.pdf")


def _make_file_id_attachment(file_id: str) -> FileAttachment:
    return FileAttachment(file_id=file_id, mime_type="application/pdf", filename="test.pdf")


def _make_url_attachment(url: str) -> FileAttachment:
    return FileAttachment(url=url, mime_type="application/pdf", filename="test.pdf")


# ── _make_cache_key ──────────────────────────────────────────────────────────


class TestMakeCacheKey:
    """Content-based cache key derivation."""

    def test_data_attachment_key_ignores_filename(self):
        """Same content + MIME, different filenames → same key."""
        data = base64.b64encode(b"hello world").decode("ascii")
        att1 = FileAttachment(data=data, mime_type="text/plain", filename="a.txt")
        att2 = FileAttachment(data=data, mime_type="text/plain", filename="b.txt")
        assert _make_cache_key(att1) == _make_cache_key(att2)

    def test_different_content_different_key(self):
        """Different content → different keys."""
        att1 = _make_data_attachment(base64.b64encode(b"hello").decode("ascii"))
        att2 = _make_data_attachment(base64.b64encode(b"world").decode("ascii"))
        assert _make_cache_key(att1) != _make_cache_key(att2)

    def test_file_id_attachment_uses_file_id(self):
        """file_id-only attachments use the file_id as the key."""
        att = _make_file_id_attachment("file-abc123")
        assert _make_cache_key(att) == "file_id:file-abc123"

    def test_url_attachment_uses_url_hash(self):
        """URL attachments include the URL in the key hash."""
        att1 = _make_url_attachment("https://example.com/a.pdf")
        att2 = _make_url_attachment("https://example.com/b.pdf")
        assert _make_cache_key(att1) != _make_cache_key(att2)

    def test_streaming_attachment_key(self, tmp_path):
        """StreamingFileAttachment produces a 64-char hex cache key."""
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(b"hello stream")
        att = FileAttachment.from_path(file_path, stream=True)
        assert isinstance(att, StreamingFileAttachment)
        key = _make_cache_key(att)
        assert len(key) == 64
        import hashlib
        assert all(c in "0123456789abcdef" for c in key)


# ── InFlightTracker ──────────────────────────────────────────────────────────


class TestInFlightTracker:
    """Concurrent upload deduplication."""

    @pytest.mark.asyncio
    async def test_single_call_runs_upload_fn(self):
        """Single call executes the upload function."""
        tracker = InFlightTracker()
        result = await tracker.run_or_wait("key1", lambda: asyncio.sleep(0, result="file-1"))  # type: ignore[arg-type]
        assert result == "file-1"

    @pytest.mark.asyncio
    async def test_concurrent_calls_deduplicate(self):
        """Two concurrent calls for the same key → only one upload."""
        call_count = 0

        async def upload_fn() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return "file-1"

        tracker = InFlightTracker()

        async def task() -> str:
            return await tracker.run_or_wait("key1", upload_fn)

        results = await asyncio.gather(task(), task())
        assert results == ["file-1", "file-1"]
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_error_propagates_to_waiters(self):
        """If the first call fails, error propagates to waiters."""
        call_count = 0

        async def upload_fn() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            raise ValueError("upload failed")

        tracker = InFlightTracker()

        async def task() -> str:
            return await tracker.run_or_wait("key1", upload_fn)

        with pytest.raises(ValueError, match="upload failed"):
            await asyncio.gather(task(), task(), return_exceptions=False)
        assert call_count == 1


# ── UploadSession ────────────────────────────────────────────────────────────


class TestUploadSession:
    """UploadSession cache hit/miss, dedup, LRU eviction."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        uploaded = MagicMock()
        uploaded.id = "file-new-1"
        client.files.create = AsyncMock(return_value=uploaded)
        return client

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_upload(self, mock_client: AsyncMock):
        """Cache miss → upload via client.files.create."""
        session = UploadSession()
        att = _make_data_attachment(base64.b64encode(b"hello").decode("ascii"))
        file_id = await session.ensure_file_id(mock_client, att)
        assert file_id == "file-new-1"
        mock_client.files.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_no_reupload(self, mock_client: AsyncMock):
        """Same attachment twice → only one upload."""
        session = UploadSession()
        att = _make_data_attachment(base64.b64encode(b"hello").decode("ascii"))

        id1 = await session.ensure_file_id(mock_client, att)
        id2 = await session.ensure_file_id(mock_client, att)

        assert id1 == id2 == "file-new-1"
        assert mock_client.files.create.call_count == 1

    @pytest.mark.asyncio
    async def test_file_id_bypass(self, mock_client: AsyncMock):
        """file_id-only attachment returns the file_id without upload."""
        session = UploadSession()
        att = _make_file_id_attachment("file-existing-1")
        file_id = await session.ensure_file_id(mock_client, att)
        assert file_id == "file-existing-1"
        mock_client.files.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_in_memory_lru_eviction(self, mock_client: AsyncMock):
        """In-memory cache evicts oldest entry when over capacity."""
        session = UploadSession(session_cache_max_entries=2)

        att1 = _make_data_attachment(base64.b64encode(b"a").decode("ascii"))
        att2 = _make_data_attachment(base64.b64encode(b"b").decode("ascii"))
        att3 = _make_data_attachment(base64.b64encode(b"c").decode("ascii"))

        await session.ensure_file_id(mock_client, att1)
        await session.ensure_file_id(mock_client, att2)
        # Third upload should evict att1 (oldest)
        await session.ensure_file_id(mock_client, att3)

        assert session.cache_size == 2
        # att1 should have been evicted
        assert _make_cache_key(att1) not in session._cache

    @pytest.mark.asyncio
    async def test_stream_vs_non_stream_same_content_dedup(self, mock_client: AsyncMock, tmp_path):
        """Same content via streaming and non-streaming paths produces identical file_id."""
        content = b"hello world, this is a test file for dedup verification"
        file_path = tmp_path / "dedup_test.bin"
        file_path.write_bytes(content)
        b64_data = base64.b64encode(content).decode("ascii")

        session = UploadSession()

        stream_att = FileAttachment.from_path(str(file_path), stream=True)
        data_att = FileAttachment(data=b64_data, mime_type="application/octet-stream")

        file_id_1 = await session.ensure_file_id(mock_client, stream_att)
        file_id_2 = await session.ensure_file_id(mock_client, data_att)

        assert file_id_1 == file_id_2
        assert mock_client.files.create.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_hit_promotes_lru(self, mock_client: AsyncMock):
        """Accessing an entry promotes it (prevents eviction)."""
        session = UploadSession(session_cache_max_entries=2)

        att1 = _make_data_attachment(base64.b64encode(b"a").decode("ascii"))
        att2 = _make_data_attachment(base64.b64encode(b"b").decode("ascii"))
        att3 = _make_data_attachment(base64.b64encode(b"c").decode("ascii"))

        await session.ensure_file_id(mock_client, att1)
        await session.ensure_file_id(mock_client, att2)
        # Re-access att1 to promote it
        await session.ensure_file_id(mock_client, att1)
        # Third upload should evict att2 (now the oldest)
        await session.ensure_file_id(mock_client, att3)

        assert session.cache_size == 2
        assert _make_cache_key(att1) in session._cache
        assert _make_cache_key(att2) not in session._cache


# ── PersistentCacheStore ─────────────────────────────────────────────────────


class TestPersistentCacheStore:
    """PersistentCacheStore write-read, LRU eviction, corruption recovery."""

    def test_write_read_cycle(self, tmp_path):
        """Write entry, read it back from a new store instance."""
        cache_dir = tmp_path / "cache"
        store = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
        )
        result = UploadResult(file_id="file-1", mime_type="application/pdf")
        store.put("key1", result)

        # New instance — should load from disk
        store2 = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
        )
        retrieved = store2.get("key1")
        assert retrieved is not None
        assert retrieved.file_id == "file-1"

    def test_lru_eviction(self, tmp_path):
        """Exceeding max_entries evicts the least recently accessed entry."""
        cache_dir = tmp_path / "cache"
        store = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=3,
        )
        for i in range(5):
            store.put(f"key{i}", UploadResult(file_id=f"file-{i}", mime_type="text/plain"))
            time.sleep(0.001)  # Ensure distinct timestamps

        assert len(store) == 3
        assert store.get("key0") is None  # Oldest, should be evicted
        assert store.get("key1") is None

    def test_lru_promotion(self, tmp_path):
        """get() promotes an entry to most recently used."""
        cache_dir = tmp_path / "cache"
        store = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=3,
        )
        store.put("key0", UploadResult(file_id="file-0", mime_type="text/plain"))
        time.sleep(0.001)
        store.put("key1", UploadResult(file_id="file-1", mime_type="text/plain"))
        time.sleep(0.001)
        store.put("key2", UploadResult(file_id="file-2", mime_type="text/plain"))

        # Access key0 to promote it
        store.get("key0")
        # Now key1 should be LRU

        store.put("key3", UploadResult(file_id="file-3", mime_type="text/plain"))
        assert store.get("key0") is not None  # Promoted, should survive
        assert store.get("key1") is None      # Evicted
        assert store.get("key2") is not None

    def test_corruption_recovery(self, tmp_path):
        """Malformed JSONL line is skipped, valid entries preserved."""
        cache_dir = tmp_path / "cache"
        store = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
        )
        store.put("key1", UploadResult(file_id="file-1", mime_type="application/pdf"))

        # Corrupt the file by appending garbage
        with open(store._path, "a") as f:
            f.write("this is not valid json\n")
            f.write('{"key": "key2", "file_id": "file-2", "mime_type": "text/plain"}\n')

        # New instance should skip corrupt line, load valid entries
        store2 = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
        )
        assert store2.get("key1") is not None
        assert store2.get("key2") is not None

    def test_empty_cache_file(self, tmp_path):
        """Empty cache file on first run — no error."""
        cache_dir = tmp_path / "cache"
        store = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
        )
        assert len(store) == 0

    def test_provider_scoping(self, tmp_path):
        """Entries are scoped by provider identifier."""
        cache_dir = tmp_path / "cache"
        store_a = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
        )
        store_a.put("key1", UploadResult(file_id="file-a", mime_type="text/plain"))

        store_b = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-chat-completions",
            base_url="https://api.openai.com/v1",
            max_entries=10,
        )
        # store_b should NOT see entries from store_a
        assert store_b.get("key1") is None
        assert len(store_b) == 0

    def test_base_url_scoping(self, tmp_path):
        """Entries are scoped by normalized base URL."""
        cache_dir = tmp_path / "cache"
        store_a = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.example.com/v1",
            max_entries=10,
        )
        store_a.put("key1", UploadResult(file_id="file-a", mime_type="text/plain"))

        store_b = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.other.com/v1",
            max_entries=10,
        )
        assert store_b.get("key1") is None

    def test_namespace_scoping(self, tmp_path):
        """Entries are scoped by cache_namespace."""
        cache_dir = tmp_path / "cache"
        store_a = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
            cache_namespace="account-a",
        )
        store_a.put("key1", UploadResult(file_id="file-a", mime_type="text/plain"))

        store_b = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
            cache_namespace="account-b",
        )
        assert store_b.get("key1") is None

    def test_provider_mismatch_skips_entry(self, tmp_path):
        """Entry written by a different provider is skipped on load."""
        cache_dir = tmp_path / "cache"
        store = PersistentCacheStore(
            cache_dir=cache_dir, provider="openai-responses",
            base_url="https://api.openai.com/v1", max_entries=10,
        )
        store.put("key1", UploadResult(file_id="file-1", mime_type="text/plain"))
        store.put("key2", UploadResult(file_id="file-2", mime_type="text/plain"))
        # Force persist to ensure both entries are on disk before manipulation
        store._persist()

        # Rewrite key1's provider to simulate cross-provider pollution
        lines = store._path.read_text().splitlines()
        lines[0] = lines[0].replace('"openai-responses"', '"openai-chat-completions"')
        store._path.write_text("\n".join(lines) + "\n")

        store2 = PersistentCacheStore(
            cache_dir=cache_dir, provider="openai-responses",
            base_url="https://api.openai.com/v1", max_entries=10,
        )
        assert store2.get("key1") is None
        assert store2.get("key2") is not None

    def test_clear(self, tmp_path):
        """clear() removes all entries."""
        cache_dir = tmp_path / "cache"
        store = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
        )
        store.put("key1", UploadResult(file_id="file-1", mime_type="text/plain"))
        store.put("key2", UploadResult(file_id="file-2", mime_type="text/plain"))
        store.clear()
        assert len(store) == 0

    def test_disk_full_degradation(self, tmp_path):
        """OSError on write via os.open is caught, in-memory state continues."""
        cache_dir = tmp_path / "cache"
        store = PersistentCacheStore(
            cache_dir=cache_dir,
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
            max_entries=10,
        )
        store.put("key1", UploadResult(file_id="file-1", mime_type="text/plain"))

        # Simulate disk full by making os.open raise inside _persist
        with patch.object(os, "open", side_effect=OSError("No space left on device")):
            store.put("key2", UploadResult(file_id="file-2", mime_type="text/plain"))

        # In-memory should still have both entries
        assert store.get("key1") is not None
        assert store.get("key2") is not None

    def test_permission_denied_degradation(self, tmp_path):
        """PermissionError on cache dir init is caught, store operates in-memory only."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True, mode=0o000)
        try:
            store = PersistentCacheStore(
                cache_dir=str(cache_dir),
                provider="openai-responses",
                base_url="https://api.openai.com/v1",
                max_entries=10,
            )
            # Degraded gracefully: persistence disabled, in-memory store works
            assert len(store) == 0
            store._max_entries = 10  # Re-enable in-memory for this test
            store.put("key1", UploadResult(file_id="file-1", mime_type="text/plain"))
            assert store.get("key1") is not None
        finally:
            # Restore permissions so pytest can clean up the temp directory
            cache_dir.chmod(0o755)


# ── URL Download ─────────────────────────────────────────────────────────────


class TestValidateUrlSafety:
    """SSRF protection for URL downloads."""

    @pytest.mark.asyncio
    async def test_http_scheme_allowed(self):
        """HTTP scheme is allowed."""
        await _validate_url_safety("http://example.com/file.pdf")

    @pytest.mark.asyncio
    async def test_https_scheme_allowed(self):
        """HTTPS scheme is allowed."""
        await _validate_url_safety("https://example.com/file.pdf")

    @pytest.mark.asyncio
    async def test_ftp_scheme_rejected(self):
        """Non-HTTP(S) schemes are rejected."""
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            await _validate_url_safety("ftp://example.com/file.pdf")

    @pytest.mark.asyncio
    async def test_localhost_rejected(self):
        """localhost is rejected."""
        with pytest.raises(ValueError, match="blocked IP"):
            await _validate_url_safety("http://localhost:8080/file.pdf")

    @pytest.mark.asyncio
    async def test_loopback_ipv4_rejected(self):
        """127.0.0.1 is rejected."""
        with pytest.raises(ValueError, match="blocked IP"):
            await _validate_url_safety("http://127.0.0.1/file.pdf")

    @pytest.mark.asyncio
    async def test_loopback_ipv6_rejected(self):
        """::1 is rejected."""
        with pytest.raises(ValueError, match="blocked IP"):
            await _validate_url_safety("http://[::1]/file.pdf")

    @pytest.mark.asyncio
    async def test_private_ipv4_10_rejected(self):
        """10.0.0.1 is rejected."""
        with pytest.raises(ValueError, match="blocked IP"):
            await _validate_url_safety("http://10.0.0.1/file.pdf")

    @pytest.mark.asyncio
    async def test_private_ipv4_192_rejected(self):
        """192.168.0.1 is rejected."""
        with pytest.raises(ValueError, match="blocked IP"):
            await _validate_url_safety("http://192.168.0.1/file.pdf")

    @pytest.mark.asyncio
    async def test_private_ipv4_172_rejected(self):
        """172.16.0.1 is rejected."""
        with pytest.raises(ValueError, match="blocked IP"):
            await _validate_url_safety("http://172.16.0.1/file.pdf")

    @pytest.mark.asyncio
    async def test_cloud_metadata_endpoint_rejected(self):
        """169.254.169.254 is rejected."""
        with pytest.raises(ValueError, match="blocked IP"):
            await _validate_url_safety("http://169.254.169.254/latest/meta-data/")

    @pytest.mark.asyncio
    async def test_zero_zero_zero_zero_rejected(self):
        """0.0.0.0 is rejected (this network / all interfaces)."""
        with pytest.raises(ValueError, match="blocked IP"):
            await _validate_url_safety("http://0.0.0.0/file.pdf")


class TestDownloadUrlContent:
    """URL download with httpx mocking."""

    @pytest.mark.asyncio
    async def test_successful_download(self):
        """Mock a successful HTTP download end-to-end including peer verification."""
        validated_ips = frozenset({"93.184.216.34"})
        mock_stream = MagicMock()
        mock_stream.get_extra_info.return_value = ("93.184.216.34", 443)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake file content"
        mock_response.extensions = {"network_stream": mock_stream}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.aclose = AsyncMock()

        with (
            patch(
                "tinycua_sdk.providers.upload._validate_url_safety",
                AsyncMock(return_value=validated_ips),
            ),
            patch(
                "tinycua_sdk.providers.upload.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            content = await _download_url_content("https://example.com/file.pdf")
            assert content == b"fake file content"
            mock_client.get.assert_called_once()
            call_args, call_kwargs = mock_client.get.call_args
            assert call_args[0] == "https://example.com/file.pdf"
            # The timeout keyword is now passed to enforce the deadline
            assert "timeout" in call_kwargs

    @pytest.mark.asyncio
    async def test_invalid_url_rejected(self):
        """Invalid URL is rejected."""
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            await _download_url_content("ftp://example.com/file.pdf")

    @pytest.mark.asyncio
    async def test_successful_redirect_chain(self):
        """Follows a redirect chain and returns final content."""
        validated_ips = frozenset({"93.184.216.34"})
        mock_stream = MagicMock()
        mock_stream.get_extra_info.return_value = ("93.184.216.34", 443)

        def build_response(status_code, content=b"", headers=None):
            resp = MagicMock()
            resp.status_code = status_code
            resp.content = content
            resp.headers = headers or {}
            resp.extensions = {"network_stream": mock_stream}
            return resp

        redirect_resp = build_response(302, headers={"location": "https://example.com/final.pdf"})
        final_resp = build_response(200, content=b"final content")

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=[redirect_resp, final_resp])
        mock_client.aclose = AsyncMock()

        with (
            patch(
                "tinycua_sdk.providers.upload._validate_url_safety",
                AsyncMock(return_value=validated_ips),
            ),
            patch(
                "tinycua_sdk.providers.upload.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            content = await _download_url_content("https://example.com/initial.pdf")
            assert content == b"final content"
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_redirect_limit_exceeded(self):
        """Exceeding max redirects raises ValueError."""
        validated_ips = frozenset({"93.184.216.34"})
        mock_stream = MagicMock()
        mock_stream.get_extra_info.return_value = ("93.184.216.34", 443)

        def build_redirect(headers=None):
            resp = MagicMock()
            resp.status_code = 302
            resp.content = b""
            resp.headers = headers or {"location": "https://example.com/next"}
            resp.extensions = {"network_stream": mock_stream}
            return resp

        redirects = [build_redirect() for _ in range(6)]

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=redirects)
        mock_client.aclose = AsyncMock()

        with (
            patch(
                "tinycua_sdk.providers.upload._validate_url_safety",
                AsyncMock(return_value=validated_ips),
            ),
            patch(
                "tinycua_sdk.providers.upload.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            with pytest.raises(ValueError, match="Too many redirects"):
                await _download_url_content("https://example.com/initial.pdf")

    @pytest.mark.asyncio
    async def test_redirect_missing_location(self):
        """Redirect without Location header raises ValueError."""
        validated_ips = frozenset({"93.184.216.34"})
        mock_stream = MagicMock()
        mock_stream.get_extra_info.return_value = ("93.184.216.34", 443)

        redirect_resp = MagicMock()
        redirect_resp.status_code = 302
        redirect_resp.headers = {}
        redirect_resp.extensions = {"network_stream": mock_stream}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=redirect_resp)
        mock_client.aclose = AsyncMock()

        with (
            patch(
                "tinycua_sdk.providers.upload._validate_url_safety",
                AsyncMock(return_value=validated_ips),
            ),
            patch(
                "tinycua_sdk.providers.upload.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            with pytest.raises(ValueError, match="missing Location"):
                await _download_url_content("https://example.com/initial.pdf")

    @pytest.mark.asyncio
    async def test_public_to_private_redirect_rejected(self):
        """Redirect from public to private IP is rejected."""
        mock_stream = MagicMock()
        mock_stream.get_extra_info.return_value = ("93.184.216.34", 443)

        redirect_resp = MagicMock()
        redirect_resp.status_code = 302
        redirect_resp.headers = {"location": "http://10.0.0.1/secret.pdf"}
        redirect_resp.extensions = {"network_stream": mock_stream}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=redirect_resp)
        mock_client.aclose = AsyncMock()

        with (
            patch(
                "tinycua_sdk.providers.upload._validate_url_safety",
                AsyncMock(
                    side_effect=[
                        frozenset({"93.184.216.34"}),
                        ValueError("blocked IP"),
                    ],
                ),
            ),
            patch(
                "tinycua_sdk.providers.upload.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            with pytest.raises(ValueError, match="blocked IP"):
                await _download_url_content("https://example.com/initial.pdf")

    @pytest.mark.asyncio
    async def test_timeout_exception_raises(self):
        """httpx.TimeoutException is caught and re-raised as ValueError."""
        validated_ips = frozenset({"93.184.216.34"})
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.aclose = AsyncMock()

        with (
            patch(
                "tinycua_sdk.providers.upload._validate_url_safety",
                AsyncMock(return_value=validated_ips),
            ),
            patch(
                "tinycua_sdk.providers.upload.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            with pytest.raises(ValueError, match="Timeout"):
                await _download_url_content("https://example.com/file.pdf")

    @pytest.mark.asyncio
    async def test_connect_error_raises(self):
        """httpx.ConnectError is caught and re-raised as ValueError."""
        validated_ips = frozenset({"93.184.216.34"})
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        mock_client.aclose = AsyncMock()

        with (
            patch(
                "tinycua_sdk.providers.upload._validate_url_safety",
                AsyncMock(return_value=validated_ips),
            ),
            patch(
                "tinycua_sdk.providers.upload.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            with pytest.raises(ValueError, match="Connection error"):
                await _download_url_content("https://example.com/file.pdf")

    @pytest.mark.asyncio
    async def test_http_404_raises(self):
        """HTTP 404 response is caught and re-raised as ValueError."""
        validated_ips = frozenset({"93.184.216.34"})
        mock_stream = MagicMock()
        mock_stream.get_extra_info.return_value = ("93.184.216.34", 443)

        response_404 = MagicMock()
        response_404.status_code = 404
        response_404.reason_phrase = "Not Found"
        response_404.text = "Not found"
        response_404.extensions = {"network_stream": mock_stream}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=response_404)
        mock_client.aclose = AsyncMock()

        with (
            patch(
                "tinycua_sdk.providers.upload._validate_url_safety",
                AsyncMock(return_value=validated_ips),
            ),
            patch(
                "tinycua_sdk.providers.upload.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            with pytest.raises(ValueError, match="HTTP 404"):
                await _download_url_content("https://example.com/file.pdf")

    @pytest.mark.asyncio
    async def test_http_500_raises(self):
        """HTTP 500 response is caught and re-raised as ValueError."""
        validated_ips = frozenset({"93.184.216.34"})
        mock_stream = MagicMock()
        mock_stream.get_extra_info.return_value = ("93.184.216.34", 443)

        response_500 = MagicMock()
        response_500.status_code = 500
        response_500.reason_phrase = "Internal Server Error"
        response_500.text = "Server error"
        response_500.extensions = {"network_stream": mock_stream}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=response_500)
        mock_client.aclose = AsyncMock()

        with (
            patch(
                "tinycua_sdk.providers.upload._validate_url_safety",
                AsyncMock(return_value=validated_ips),
            ),
            patch(
                "tinycua_sdk.providers.upload.httpx.AsyncClient",
                return_value=mock_client,
            ),
        ):
            with pytest.raises(ValueError, match="HTTP 500"):
                await _download_url_content("https://example.com/file.pdf")


# ── UploadSession with Persistent Cache ──────────────────────────────────────


class TestUploadSessionWithPersistentCache:
    """Integration of UploadSession with PersistentCacheStore."""

    @pytest.mark.asyncio
    async def test_persistent_cache_hit_prevents_upload(self, tmp_path):
        """Entry in persistent cache → no upload."""
        cache_dir = tmp_path / "cache"
        mock_client = AsyncMock()
        uploaded = MagicMock()
        uploaded.id = "file-persisted-1"
        mock_client.files.create = AsyncMock(return_value=uploaded)

        # First session: upload and persist
        session1 = UploadSession(
            cache_dir=str(cache_dir),
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
        )
        att = _make_data_attachment(base64.b64encode(b"hello").decode("ascii"))
        file_id = await session1.ensure_file_id(mock_client, att)
        await session1.close()

        assert file_id == "file-persisted-1"
        assert mock_client.files.create.call_count == 1

        # Second session: should hit persistent cache, no upload
        session2 = UploadSession(
            cache_dir=str(cache_dir),
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
        )
        mock_client2 = AsyncMock()
        mock_client2.files.create = AsyncMock()
        file_id2 = await session2.ensure_file_id(mock_client2, att)
        await session2.close()

        assert file_id2 == "file-persisted-1"
        mock_client2.files.create.assert_not_called()


    @pytest.mark.asyncio
    async def test_close_persists_pending_entries(self, tmp_path):
        """Put 2 entries, close, reopen — both should survive."""
        cache_dir = tmp_path / "cache"
        mock_client = AsyncMock()

        def make_upload(file_id: str) -> AsyncMock:
            uploaded = MagicMock()
            uploaded.id = file_id
            return AsyncMock(return_value=uploaded)

        # First session: upload 2 attachments
        session1 = UploadSession(
            cache_dir=str(cache_dir),
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
        )
        att1 = _make_data_attachment(base64.b64encode(b"hello").decode("ascii"))
        att2 = _make_data_attachment(base64.b64encode(b"world").decode("ascii"))

        mock_client.files.create = make_upload("file-1")
        await session1.ensure_file_id(mock_client, att1)

        mock_client.files.create = make_upload("file-2")
        await session1.ensure_file_id(mock_client, att2)

        await session1.close()

        # Second session: both entries should be found in persistent cache
        session2 = UploadSession(
            cache_dir=str(cache_dir),
            provider="openai-responses",
            base_url="https://api.openai.com/v1",
        )
        mock_client2 = AsyncMock()
        mock_client2.files.create = AsyncMock()

        file_id1 = await session2.ensure_file_id(mock_client2, att1)
        file_id2 = await session2.ensure_file_id(mock_client2, att2)

        await session2.close()

        assert file_id1 == "file-1"
        assert file_id2 == "file-2"
        mock_client2.files.create.assert_not_called()


# ── SSRF: _verify_connected_peer ─────────────────────────────────────────────


class TestVerifyConnectedPeer:
    """Peer verification for DNS-rebinding TOCTOU protection."""

    def test_valid_peer_passes(self):
        """Peer IP in validated set → no error."""
        response = MagicMock()
        response.extensions = {}
        response.extensions["network_stream"] = MagicMock()
        response.extensions["network_stream"].get_extra_info.return_value = (
            "93.184.216.34",
            443,
        )
        validated = frozenset({"93.184.216.34", "1.2.3.4"})
        _verify_connected_peer(response, validated)

    def test_unvalidated_peer_raises(self):
        """Peer IP not in validated set → ValueError."""
        response = MagicMock()
        response.extensions = {}
        response.extensions["network_stream"] = MagicMock()
        response.extensions["network_stream"].get_extra_info.return_value = (
            "93.184.216.35",
            443,
        )
        validated = frozenset({"93.184.216.34"})
        with pytest.raises(ValueError, match="unvalidated peer"):
            _verify_connected_peer(response, validated)

    def test_missing_extensions_raises(self):
        """No extensions attribute → ValueError."""
        response = MagicMock(spec=["status_code"])
        del response.extensions
        with pytest.raises(ValueError, match="response.extensions not available"):
            _verify_connected_peer(response, frozenset())

    def test_extensions_not_dict_raises(self):
        """Extensions attribute is not a dict → ValueError."""
        response = MagicMock()
        response.extensions = None
        with pytest.raises(ValueError, match="response.extensions not available"):
            _verify_connected_peer(response, frozenset())

    def test_missing_network_stream_raises(self):
        """No network_stream in extensions → ValueError."""
        response = MagicMock()
        response.extensions = {}
        with pytest.raises(ValueError, match="no network_stream"):
            _verify_connected_peer(response, frozenset())

    def test_none_peername_raises(self):
        """peername is None → ValueError."""
        response = MagicMock()
        response.extensions = {}
        response.extensions["network_stream"] = MagicMock()
        response.extensions["network_stream"].get_extra_info.return_value = None
        with pytest.raises(ValueError, match="peername is None"):
            _verify_connected_peer(response, frozenset({"93.184.216.34"}))


# ── SSRF: _PinnedNetworkBackend ──────────────────────────────────────────────


class TestPinnedNetworkBackend:
    """Transport-level IP pinning for DNS-rebinding protection."""

    @pytest.mark.asyncio
    async def test_ip_literal_validated_passes(self):
        """IP literal in validated set → delegates to real backend."""
        real_backend = AsyncMock()
        backend = _PinnedNetworkBackend(frozenset({"93.184.216.34"}), real_backend)

        result = await backend.connect_tcp("93.184.216.34", 443)

        assert result is real_backend.connect_tcp.return_value
        real_backend.connect_tcp.assert_called_once_with(
            "93.184.216.34", 443, None, None, None,
        )

    @pytest.mark.asyncio
    async def test_ip_literal_not_validated_raises(self):
        """IP literal not in validated set → ValueError."""
        real_backend = AsyncMock()
        backend = _PinnedNetworkBackend(frozenset({"1.2.3.4"}), real_backend)

        with pytest.raises(ValueError, match="not allowed"):
            await backend.connect_tcp("93.184.216.34", 443)

        real_backend.connect_tcp.assert_not_called()

    @pytest.mark.asyncio
    async def test_hostname_resolves_to_validated_ip(self):
        """Hostname resolves to a validated IP → connects via that IP."""
        real_backend = AsyncMock()
        backend = _PinnedNetworkBackend(frozenset({"93.184.216.34"}), real_backend)

        addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443)),
        ]

        with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait:
            mock_wait.return_value = addrinfo
            result = await backend.connect_tcp("example.com", 443)

        assert result is real_backend.connect_tcp.return_value
        real_backend.connect_tcp.assert_called_once_with(
            "93.184.216.34", 443, None, None, None,
        )

    @pytest.mark.asyncio
    async def test_hostname_no_validated_ip_raises(self):
        """Hostname resolves only to non-validated IPs → ValueError."""
        real_backend = AsyncMock()
        backend = _PinnedNetworkBackend(frozenset({"1.2.3.4"}), real_backend)

        addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443)),
        ]

        with patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait:
            mock_wait.return_value = addrinfo
            with pytest.raises(ValueError, match="No validated IP"):
                await backend.connect_tcp("example.com", 443)

        real_backend.connect_tcp.assert_not_called()

    @pytest.mark.asyncio
    async def test_dns_timeout_raises(self):
        """DNS resolution timeout → ValueError."""
        real_backend = AsyncMock()
        backend = _PinnedNetworkBackend(frozenset({"93.184.216.34"}), real_backend)

        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError("timeout")):
            with pytest.raises(ValueError, match="DNS resolution timeout"):
                await backend.connect_tcp("example.com", 443)

        real_backend.connect_tcp.assert_not_called()

    @pytest.mark.asyncio
    async def test_dns_resolution_failure_raises(self):
        """DNS resolution error (gaierror) → ValueError."""
        real_backend = AsyncMock()
        backend = _PinnedNetworkBackend(frozenset({"93.184.216.34"}), real_backend)

        with patch("asyncio.wait_for", side_effect=socket.gaierror("Name or service not known")):
            with pytest.raises(ValueError, match="Failed to resolve hostname"):
                await backend.connect_tcp("example.com", 443)

        real_backend.connect_tcp.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_unix_socket_delegates(self):
        """Unix socket connections delegate to real backend unchanged."""
        real_backend = AsyncMock()
        backend = _PinnedNetworkBackend(frozenset(), real_backend)

        await backend.connect_unix_socket("/tmp/test.sock", 30.0)

        real_backend.connect_unix_socket.assert_awaited_once_with(
            "/tmp/test.sock", 30.0,
        )

    @pytest.mark.asyncio
    async def test_sleep_delegates(self):
        """Sleep delegates to real backend unchanged."""
        real_backend = AsyncMock()
        backend = _PinnedNetworkBackend(frozenset(), real_backend)

        await backend.sleep(1.5)

        real_backend.sleep.assert_awaited_once_with(1.5)
