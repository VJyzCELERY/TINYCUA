"""Upload session, persistent cache, in-flight dedup, and URL download.

Provides :class:`UploadSession` for managing file uploads to provider APIs
with in-memory LRU caching, optional persistent disk-backed storage across
sessions, concurrent upload deduplication via :class:`InFlightTracker`, and
SSRF-safe URL download via :func:`_download_url_content`.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import logging
import os
import pathlib
import socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from tinycua_sdk.models.attachment import StreamingFileAttachment  # noqa: E402

if TYPE_CHECKING:

    from openai import AsyncOpenAI

    from tinycua_sdk.models.attachment import FileAttachment

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

# Maximum redirects for URL downloads.
_MAX_REDIRECTS = 5

# Prohibited IPv4 networks for SSRF protection.
_BLOCKED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),        # "This" network
    ipaddress.ip_network("10.0.0.0/8"),       # Private
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local
    ipaddress.ip_network("172.16.0.0/12"),    # Private
    ipaddress.ip_network("192.168.0.0/16"),   # Private
    ipaddress.ip_network("224.0.0.0/4"),      # Multicast
    ipaddress.ip_network("240.0.0.0/4"),      # Reserved (including 255.255.255.255)
]

# Prohibited IPv6 networks for SSRF protection.
_BLOCKED_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),          # Loopback
    ipaddress.ip_network("::/128"),           # Unspecified
    ipaddress.ip_network("fe80::/10"),        # Link-local
    ipaddress.ip_network("fc00::/7"),         # Unique local (private)
    ipaddress.ip_network("ff00::/8"),         # Multicast
]


# ── UploadResult ──────────────────────────────────────────────────────────────


@dataclass
class UploadResult:
    """Result of a file upload to a provider API.

    Attributes:
        file_id: Provider-issued file identifier.
        mime_type: MIME type of the uploaded file.
        created_at: Unix timestamp when the upload was created.
        last_accessed: Unix timestamp of last cache access (for LRU eviction).
        expires_at: Optional expiry timestamp from the provider.
    """

    file_id: str
    mime_type: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    expires_at: float | None = None


# ── InFlightTracker ───────────────────────────────────────────────────────────


class InFlightTracker:
    """Prevents duplicate concurrent uploads for the same cache key.

    Uses :class:`asyncio.Future` so the first caller performs the upload
    while subsequent callers for the same key wait and receive the result
    without issuing a second upload.  Completed futures are removed from
    the tracker so that LRU cache eviction and retry work correctly.
    """

    def __init__(self) -> None:
        self._in_flight: dict[str, asyncio.Future[str]] = {}

    async def run_or_wait(
        self,
        key: str,
        upload_fn: Callable[[], Awaitable[str]],
    ) -> str:
        """Execute *upload_fn* exactly once per *key* at a time.

        If another coroutine is already uploading for *key*, this call
        waits for the existing upload to complete and returns its result.
        Once the upload completes, the future is removed so subsequent
        calls for the same key will re-execute *upload_fn* (supporting
        LRU eviction and retry).

        Args:
            key: Cache key identifying the upload.
            upload_fn: Async callable that performs the actual upload.

        Returns:
            The ``file_id`` from the upload.

        Raises:
            Exception: Re-raises any exception from the upload.
        """
        fut = self._in_flight.get(key)
        if fut is not None and not fut.done():
            return await fut

        fut = asyncio.Future()
        self._in_flight[key] = fut
        try:
            result = await upload_fn()
            fut.set_result(result)
            return result
        except Exception as exc:
            fut.set_exception(exc)
            raise
        finally:
            # Only remove if our future is still the one in the dict
            if self._in_flight.get(key) is fut:
                del self._in_flight[key]


# ── PersistentCacheStore ─────────────────────────────────────────────────────


class PersistentCacheStore:
    """Disk-backed JSONL cache for file upload results.

    Scoped by provider identifier, base URL hash, and cache namespace.
    Entries are stored as one JSON line per record in a JSONL file at
    ``{cache_dir}/{provider}/{base_url_hash}/{namespace}/cache.jsonl``.

    API keys MUST NOT be stored in any cache entry or directory path.

    The ``base_url_hash`` is the SHA-256 hex digest of the normalized
    base URL (trailing slash stripped per ``normalize_base_url()``).

    Note:
        This cache is designed for single-process use. Concurrent
        access from multiple processes may lose entries (last-writer-wins).

    Attributes:
        _max_entries: Maximum number of entries before LRU eviction.
    """

    def __init__(
        self,
        cache_dir: str | pathlib.Path,
        provider: str,
        base_url: str,
        max_entries: int = 1000,
        cache_namespace: str | None = None,
    ) -> None:
        """Initialize the persistent cache store.

        Args:
            cache_dir: Root directory for cache storage.
            provider: Provider identifier (e.g. ``"openai-responses"``).
            base_url: Normalized base URL for the provider.
            max_entries: Maximum entries before LRU eviction (default 1000).
            cache_namespace: Account/project namespace for cache isolation.
        """
        if max_entries < 0:
            raise ValueError(f"max_entries must be >= 0, got {max_entries}")
        self._max_entries = max_entries
        self._provider = provider
        self._base_url_hash = hashlib.sha256(base_url.encode()).hexdigest()
        self._cache_namespace = cache_namespace or "default"
        self._validate_provider()
        self._validate_namespace()
        self._entries: dict[str, UploadResult] = {}

        self._path = (
            pathlib.Path(cache_dir)
            / provider
            / self._base_url_hash
            / self._cache_namespace
            / "cache.jsonl"
        )
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self._max_entries > 0:
                self._load()
        except (OSError, PermissionError) as exc:
            logger.warning(
                "Failed to initialize persistent cache at %s: %s (continuing in-memory only)",
                self._path,
                exc,
            )
            self._max_entries = 0

    def _validate_provider(self) -> None:
        """Validate that *provider* is a safe single path component.

        Prevents path-traversal escapes (``..``, separators, absolute
        paths) through the provider identifier that could write cache
        files outside the scoped directory.

        Raises:
            ValueError: If the provider contains path separators, is an
                absolute path, or is ``.`` / ``..``.
        """
        p = self._provider
        if p.startswith("/") or "\\" in p:
            raise ValueError(
                f"provider cannot be an absolute path or contain "
                f"backslashes: {p!r}"
            )
        name_component = pathlib.PurePosixPath(p)
        if str(name_component) != name_component.name or name_component.name in (".", ".."):
            raise ValueError(
                f"provider must be a single path component, "
                f"got: {p!r}"
            )

    def _validate_namespace(self) -> None:
        """Validate that *cache_namespace* is a safe single path component.

        Prevents path-traversal escapes (``..``, separators, absolute
        paths) that could write cache files outside the scoped directory.

        Raises:
            ValueError: If the namespace contains path separators, is an
                absolute path, or is ``.`` / ``..``.
        """
        ns = self._cache_namespace
        if ns.startswith("/") or "\\" in ns:
            raise ValueError(
                f"cache_namespace cannot be an absolute path or contain "
                f"backslashes: {ns!r}"
            )
        name_component = pathlib.PurePosixPath(ns)
        if str(name_component) != name_component.name or name_component.name in (".", ".."):
            raise ValueError(
                f"cache_namespace must be a single path component, "
                f"got: {ns!r}"
            )

    def _load(self) -> None:
        """Load entries from the cache file, recovering from corruption.

        After loading, trims entries to *max_entries* via LRU eviction
        so that existing cache files that exceed the configured limit are
        brought back within bounds immediately.
        """
        if not self._path.exists():
            return

        try:
            lines = self._path.read_text().splitlines()
        except PermissionError:
            logger.warning(
                "Persistent cache permission denied: %s (continuing in-memory only)",
                self._path,
            )
            return

        for line_no, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                # Cross-verify the provider field: skip entries that were
                # written by a different provider to prevent returning a
                # file_id that the current provider cannot access.
                record_provider = data.get("provider")
                if record_provider is not None and record_provider != self._provider:
                    logger.warning(
                        "Skipping cache entry with mismatched provider "
                        "(expected %r, got %r) at line %d in %s",
                        self._provider,
                        record_provider,
                        line_no,
                        self._path,
                    )
                    continue
                key = data["key"]
                self._entries[key] = UploadResult(
                    file_id=data["file_id"],
                    mime_type=data["mime_type"],
                    created_at=data.get("created_at", 0.0),
                    last_accessed=data.get("last_accessed", 0.0),
                    expires_at=data.get("expires_at"),
                )
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning(
                    "Corrupt cache line %d in %s: %s (skipping)",
                    line_no,
                    self._path,
                    exc,
                )

        # Trim to max_entries if the loaded file exceeds the limit
        while len(self._entries) > self._max_entries:
            self._evict_lru()
        if lines and len(self._entries) < len([line for line in lines if line.strip()]):
            self._persist()

    def _persist(self) -> None:
        """Atomically write all entries to the cache file."""
        tmp_path = self._path.with_suffix(".tmp")
        fd = None
        try:
            # Write to a private temporary file (0600) before atomic replace
            fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            f = os.fdopen(fd, "w")
            fd = None  # os.fdopen took ownership
            with f:
                for key, entry in self._entries.items():
                    record = {
                        "key": key,
                        "file_id": entry.file_id,
                        "mime_type": entry.mime_type,
                        "provider": self._provider,
                        "created_at": entry.created_at,
                        "last_accessed": entry.last_accessed,
                    }
                    if entry.expires_at is not None:
                        record["expires_at"] = entry.expires_at
                    f.write(json.dumps(record) + "\n")
            tmp_path.replace(self._path)
            try:
                os.chmod(self._path, 0o600)
            except OSError as exc:
                logger.warning(
                    "Failed to set permissions on cache file %s: %s",
                    self._path,
                    exc,
                )
        except OSError as exc:
            logger.warning(
                "Failed to persist cache to %s: %s (continuing in-memory only)",
                self._path,
                exc,
            )
            if fd is not None:
                os.close(fd)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def get(self, key: str) -> UploadResult | None:
        """Retrieve an entry and promote it to most-recently-used.

        Persists the updated recency to disk so that LRU order survives
        process restarts (FR-010/FR-012 durability requirement).

        Args:
            key: Cache key.

        Returns:
            The ``UploadResult`` if found, or ``None``.
        """
        entry = self._entries.get(key)
        if entry is not None:
            entry.last_accessed = time.time()
            # Persist the promoted LRU order so that a subsequent
            # store instance sees the updated recency (FR-010).
            if self._max_entries > 0:
                self._persist()
        return entry

    def put(self, key: str, result: UploadResult) -> None:
        """Insert or update an entry, evicting LRU if over capacity.

        Persists immediately after every insert/update so entries are
        durable under normal operation (FR-010/FR-012).

        When *max_entries* is 0, this is a no-op (persistent caching
        disabled).

        Args:
            key: Cache key.
            result: Upload result to store.
        """
        if self._max_entries == 0:
            return
        result.last_accessed = time.time()
        self._entries[key] = result

        while len(self._entries) > self._max_entries:
            self._evict_lru()
        self._persist()

    def _evict_lru(self) -> None:
        """Evict the entry with the oldest ``last_accessed`` timestamp."""
        if not self._entries:
            return
        lru_key = min(self._entries, key=lambda k: self._entries[k].last_accessed)
        del self._entries[lru_key]

    def clear(self) -> None:
        """Remove all entries for the current provider scope.

        When *max_entries* is 0 (persistent caching disabled), this only
        clears the in-memory dict without writing to disk.
        """
        self._entries.clear()
        if self._max_entries > 0:
            self._persist()

    def __len__(self) -> int:
        """Return number of cached entries."""
        return len(self._entries)


# ── UploadSession ─────────────────────────────────────────────────────────────


def _derive_cache_key(raw_hash: str, mime: str) -> str:
    """Derive a canonical cache key from a raw content hash and MIME type.

    Args:
        raw_hash: SHA-256 hex digest of the raw file bytes.
        mime: MIME type of the file.

    Returns:
        A SHA-256 hex digest of the combined content.
    """
    return hashlib.sha256(f"{raw_hash}|{mime}".encode()).hexdigest()


def _make_cache_key(
    attachment: FileAttachment,
) -> str:
    """Generate a content-based cache key from attachment data and MIME type.

    Uses a canonical hash that is identical for the same file content
    regardless of whether it was loaded via ``stream=True`` or
    ``stream=False``.  For data-backed and streaming attachments, the
    raw bytes are hashed and combined with the MIME type.  For URL-backed
    attachments, the URL and MIME type are hashed together.  For
    file_id-backed attachments, the file_id itself is the key.

    The filename is deliberately excluded so that identical content with
    different filenames produces the same cache key (canonical
    content-based deduplication).

    .. note::
       For streaming attachments, this function uses
       :meth:`~StreamingFileAttachment.hash_content` which reads the file
       in chunks (no full-file buffering).  The caller
       (:meth:`UploadSession.ensure_file_id`) handles the TOCTOU race by
       computing the cache key from the same open file handle that is
       used for upload.

    Args:
        attachment: A canonical ``FileAttachment``.

    Returns:
        A SHA-256 hex digest string, or the ``file_id`` for file_id-only
        attachments.
    """
    if attachment.file_id is not None:
        return f"file_id:{attachment.file_id}"

    mime = attachment.mime_type

    # Compute canonical content hash from raw bytes, regardless of
    # streaming mode.  data-backed and streaming-backed attachments
    # produce the same hash for identical content.
    if isinstance(attachment, StreamingFileAttachment) and attachment._file_path is not None:
        raw_hash = attachment.hash_content()
    elif attachment.data is not None:
        raw_bytes = base64.b64decode(attachment.data)
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
    elif attachment.url is not None:
        # URL-backed: no raw bytes to hash — use URL + MIME
        content = f"{attachment.url}|{mime}"
        return hashlib.sha256(content.encode()).hexdigest()
    else:
        raise ValueError("Attachment has no usable source for cache key")

    return _derive_cache_key(raw_hash, mime)


class UploadSession:
    """Per-provider upload manager with in-memory LRU cache.

    Handles upload deduplication, optional persistent cache integration,
    and concurrent request coordination via :class:`InFlightTracker`.

    Attributes:
        _cache: In-memory cache mapping keys to ``UploadResult``.
        _max_entries: Max in-memory entries before LRU eviction.
        _in_flight: Tracker for concurrent upload dedup.
        _persistent: Optional persistent cache store.
    """

    def __init__(
        self,
        provider: str | None = None,
        base_url: str | None = None,
        cache_dir: str | None = None,
        cache_max_entries: int = 1000,
        session_cache_max_entries: int = 500,
        cache_namespace: str | None = None,
        upload_timeout: float = 30.0,
    ) -> None:
        """Initialize the upload session.

        Args:
            provider: Provider identifier for persistent cache scoping.
            base_url: Normalized base URL for persistent cache scoping.
            cache_dir: Root directory for persistent cache storage.
            cache_max_entries: Max persistent cache entries (default 1000).
            session_cache_max_entries: Max in-memory entries (default 500).
            cache_namespace: Account/project namespace for cache isolation.
            upload_timeout: Timeout for URL downloads.
        """
        if upload_timeout <= 0:
            raise ValueError(
                f"upload_timeout must be positive, got {upload_timeout}"
            )
        if session_cache_max_entries < 0:
            raise ValueError(
                f"session_cache_max_entries must be >= 0, got {session_cache_max_entries}"
            )
        self._cache: dict[str, UploadResult] = {}
        self._max_entries = session_cache_max_entries
        self._in_flight = InFlightTracker()
        self._upload_timeout = upload_timeout
        self._provider = provider
        self._base_url = base_url
        self._persistent: PersistentCacheStore | None = None

        if cache_dir and provider and base_url:
            try:
                self._persistent = PersistentCacheStore(
                    cache_dir=cache_dir,
                    provider=provider,
                    base_url=base_url,
                    max_entries=cache_max_entries,
                    cache_namespace=cache_namespace,
                )
            except (OSError, PermissionError) as exc:
                logger.warning(
                    "Failed to initialize persistent cache: %s (continuing in-memory only)",
                    exc,
                )

    async def ensure_file_id(
        self,
        client: AsyncOpenAI,
        attachment: FileAttachment,
    ) -> str:
        """Return the provider file ID for the attachment.

        Checks in-memory cache first, then persistent store, then uploads
        via ``client.files.create()``. Uses :class:`InFlightTracker` to
        prevent duplicate concurrent uploads for the same cache key.

        For file_id-only attachments, returns the file_id directly
        without performing any upload or cache lookup.

        For URL-backed attachments, downloads the file content first,
        then uploads it.

        Args:
            client: The ``AsyncOpenAI`` client instance.
            attachment: The file attachment to upload.

        Returns:
            The provider ``file_id`` string.

        Raises:
            ValueError: If the attachment has no uploadable content.
        """
        # file_id-only attachments bypass upload entirely (FR-003)
        if attachment.file_id is not None:
            return attachment.file_id

        # Image attachments should not reach this method (images use
        # inline data/URL paths). Reject early per design contract.
        if attachment.mime_type.startswith("image/"):
            raise ValueError(
                "Image attachments should not reach ensure_file_id. "
                "Images are sent inline, not uploaded."
            )

        # For streaming attachments backed by a file path, open the
        # file once, hash incrementally from the file descriptor to
        # compute the cache key, then seek back to the beginning.
        # The same open file handle is passed to _perform_upload so
        # the exact content that was hashed is what gets uploaded,
        # eliminating both the TOCTOU race and full-file buffering.
        stream_fh: Any = None
        if isinstance(attachment, StreamingFileAttachment) and attachment._file_path is not None:
            stream_fh = open(str(attachment._file_path), "rb")  # noqa: SIM115
            try:
                raw_hasher = hashlib.sha256()
                for chunk in iter(lambda: stream_fh.read(8192), b""):
                    raw_hasher.update(chunk)
                stream_fh.seek(0)
                raw_hash = raw_hasher.hexdigest()
                mime = attachment.mime_type
                cache_key = _derive_cache_key(raw_hash, mime)
            except Exception:
                stream_fh.close()
                raise
        else:
            cache_key = _make_cache_key(attachment)

        # Check in-memory cache
        if cache_key in self._cache:
            if stream_fh is not None:
                stream_fh.close()
            entry = self._cache[cache_key]
            entry.last_accessed = time.time()
            return entry.file_id

        # URL-backed attachments: download first, then upload (FR-006).
        # Skip persistent cache to guarantee fresh content each session.
        if attachment.url is not None:
            return await self._upload_from_url(client, attachment)

        # Check persistent cache (file-data attachments only)
        if self._persistent is not None:
            persisted = self._persistent.get(cache_key)
            if persisted is not None:
                if stream_fh is not None:
                    stream_fh.close()
                # Promote to in-memory
                self._cache[cache_key] = UploadResult(
                    file_id=persisted.file_id,
                    mime_type=persisted.mime_type,
                    created_at=persisted.created_at,
                    last_accessed=persisted.last_accessed,
                    expires_at=persisted.expires_at,
                )
                if len(self._cache) > self._max_entries:
                    self._evict_in_memory_lru()
                return persisted.file_id

        # Use in-flight tracker for concurrent dedup
        async def _do_upload() -> str:
            return await self._perform_upload(
                client, attachment, cache_key, stream_fh=stream_fh,
            )

        try:
            return await self._in_flight.run_or_wait(cache_key, _do_upload)
        finally:
            # On the waiter path, run_or_wait returns the winner's
            # result without calling _do_upload, so the waiter's file
            # handle is never closed by _perform_upload.  Close it here.
            # On the winner path, _perform_upload already closed the
            # handle, so .closed is True and this is a no-op.
            if stream_fh is not None and not stream_fh.closed:
                stream_fh.close()

    async def _perform_upload(
        self,
        client: AsyncOpenAI,
        attachment: FileAttachment,
        cache_key: str,
        stream_fh: Any = None,
    ) -> str:
        """Execute the actual file upload via the provider API.

        For :class:`StreamingFileAttachment`, when *stream_fh* is
        provided (pre-opened by ``ensure_file_id`` with incremental
        hashing already performed and the file position at 0), the
        handle is used directly for streaming upload — no full-file
        buffering occurs.  The handle is closed after upload.

        For standard data-backed attachments, wraps the base64-decoded
        bytes in ``BytesIO``.

        Args:
            client: The ``AsyncOpenAI`` client.
            attachment: The file to upload.
            cache_key: Pre-computed cache key.
            stream_fh: Pre-opened file handle with position at 0 for
                streaming upload.  The handle is closed after upload.
                Defaults to ``None``.

        Returns:
            The provider ``file_id`` string.
        """
        from io import BytesIO

        if stream_fh is not None:
            # Streaming upload with pre-opened file handle (TOCTOU-safe:
            # the same handle used for incremental hashing is used for
            # upload — no full-file buffering).  Use tuple form for
            # client.files.create(file=...) so the filename is provided
            # without attempting to assign to the read-only .name
            # attribute on real file objects.
            try:
                uploaded = await client.files.create(
                    file=(attachment.filename or "file", stream_fh),
                    purpose="user_data",
                )
            finally:
                stream_fh.close()
        elif isinstance(attachment, StreamingFileAttachment) and attachment._file_path is not None:
            # Fallback: open the file for streaming (passes file
            # object to avoid full-file buffering).
            file_obj = open(str(attachment._file_path), "rb")  # noqa: SIM115
            try:
                uploaded = await client.files.create(
                    file=file_obj,
                    purpose="user_data",
                )
            finally:
                file_obj.close()
        elif attachment.data is not None:
            file_bytes = base64.b64decode(attachment.data)
            file_obj = BytesIO(file_bytes)
            file_obj.name = attachment.filename or "file"
            uploaded = await client.files.create(
                file=file_obj,
                purpose="user_data",
            )
        else:
            raise ValueError(
                "Cannot upload attachment: no data source available"
            )

        file_id: str = uploaded.id
        expires_val = getattr(uploaded, "expires_at", None)
        # Guard against mock objects in testing (MagicMock attrs are not
        # serializable). Only store expires_at when it is a real number.
        expires_final: float | None = None
        if isinstance(expires_val, (int, float)):
            expires_final = float(expires_val)
        result = UploadResult(
            file_id=file_id,
            mime_type=attachment.mime_type,
            expires_at=expires_final,
        )

        # Store in in-memory cache
        self._cache[cache_key] = result
        if len(self._cache) > self._max_entries:
            self._evict_in_memory_lru()

        # Store in persistent cache
        if self._persistent is not None:
            self._persistent.put(cache_key, result)

        return file_id

    async def _upload_from_url(
        self,
        client: AsyncOpenAI,
        attachment: FileAttachment,
    ) -> str:
        """Download URL content and upload it.

        Uses :class:`InFlightTracker` to deduplicate concurrent
        downloads+uploads for the same URL.

        Args:
            client: The ``AsyncOpenAI`` client.
            attachment: URL-backed ``FileAttachment``.

        Returns:
            The provider ``file_id`` string.
        """
        from io import BytesIO

        cache_key = _make_cache_key(attachment)

        async def _download_and_upload() -> str:
            content = await _download_url_content(
                attachment.url,  # type: ignore[arg-type]
                timeout=self._upload_timeout,
            )
            file_obj = BytesIO(content)
            file_obj.name = attachment.filename or "downloaded_file"
            uploaded = await client.files.create(
                file=file_obj,
                purpose="user_data",
            )
            file_id: str = uploaded.id
            expires_val = getattr(uploaded, "expires_at", None)
            expires_final: float | None = None
            if isinstance(expires_val, (int, float)):
                expires_final = float(expires_val)
            result = UploadResult(
                file_id=file_id,
                mime_type=attachment.mime_type,
                expires_at=expires_final,
            )
            # Store in in-memory cache (URL results are NOT persisted per FR-006)
            self._cache[cache_key] = result
            if len(self._cache) > self._max_entries:
                self._evict_in_memory_lru()
            return file_id

        return await self._in_flight.run_or_wait(cache_key, _download_and_upload)

    def _evict_in_memory_lru(self) -> None:
        """Evict the in-memory entry with oldest ``last_accessed``."""
        if not self._cache:
            return
        lru_key = min(self._cache, key=lambda k: self._cache[k].last_accessed)
        del self._cache[lru_key]

    async def close(self) -> None:
        """Close the upload session and release resources.

        Persists any remaining in-memory entries to the persistent cache
        if configured, then clears in-memory state.
        """
        if self._persistent is not None:
            self._persistent._persist()
        self._cache.clear()

    # ── Testing helpers ──────────────────────────────────────────────────────

    @property
    def upload_timeout(self) -> float:
        """Return the configured upload/download timeout."""
        return self._upload_timeout

    @property
    def cache_size(self) -> int:
        """Return number of in-memory cache entries (for testing)."""
        return len(self._cache)

    @property
    def persistent_size(self) -> int:
        """Return number of persistent cache entries (for testing)."""
        return len(self._persistent) if self._persistent else 0


# ── URL Download ─────────────────────────────────────────────────────────────


async def _validate_url_safety(url: str, timeout: float | None = None) -> frozenset[str]:
    """Validate that a URL does not target internal/private networks.

    Returns the set of validated IP addresses so callers can pin
    subsequent connections to exactly those addresses, closing the
    DNS-rebinding TOCTOU window.

    DNS resolution is performed asynchronously via
    ``loop.getaddrinfo()`` wrapped in ``asyncio.wait_for()` to enforce
    the *timeout* budget.

    Args:
        url: The URL to validate.
        timeout: Maximum seconds for DNS resolution. ``None`` means no
            timeout.  Should be set to the remaining time from the
            overall upload/download timeout budget.

    Returns:
        A frozenset of validated IP address strings.

    Raises:
        ValueError: If the URL scheme is not HTTP(S), the host resolves
            to a blocked IP address, or DNS resolution exceeds *timeout*.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Unsupported URL scheme: {parsed.scheme!r}. Only HTTP(S) is allowed."
        )

    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("URL must include a valid hostname")

    # Reject literal IP addresses in blocked ranges
    try:
        ip = ipaddress.ip_address(hostname)
        _check_ip_blocked(ip)
        return frozenset({hostname})
    except ValueError:
        # Not a literal IP — proceed to DNS resolution
        pass

    # Resolve hostname asynchronously with timeout enforcement so the
    # overall upload/download timeout budget is not exceeded by a
    # stalled DNS resolver.
    loop = asyncio.get_running_loop()
    try:
        addrinfo = await asyncio.wait_for(
            loop.getaddrinfo(hostname, None),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        raise ValueError(
            f"DNS resolution timeout ({timeout}s) for hostname: "
            f"{hostname!r}"
        )
    except socket.gaierror as exc:
        raise ValueError(
            f"Failed to resolve hostname: {hostname!r}: {exc}"
        ) from exc

    validated_ips: set[str] = set()
    for info in addrinfo:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            # Address with zone ID or other non-standard format — skip
            continue
        _check_ip_blocked(ip)
        validated_ips.add(addr)

    return frozenset(validated_ips)


def _check_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Check if an IP address falls within any blocked network range.

    Detects IPv4-mapped IPv6 addresses (e.g. ``::ffff:127.0.0.1``) and
    checks the embedded IPv4 address against the IPv4 blocklist so that
    mapped-loopback and mapped-private-LAN addresses are rejected.

    Args:
        ip: The IP address to check.

    Raises:
        ValueError: If the IP is in a blocked range.
    """
    # Unwrap IPv4-mapped IPv6 addresses so they don't bypass the
    # IPv4 blocklist (e.g. http://[::ffff:127.0.0.1]/...).
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ipv4 = ip.ipv4_mapped
        for net in _BLOCKED_IPV4_NETWORKS:
            if ipv4 in net:
                raise ValueError(
                    f"URL resolves to blocked IPv4-mapped address: "
                    f"{ip} maps to {ipv4} (in {net})"
                )

    if isinstance(ip, ipaddress.IPv4Address):
        for net in _BLOCKED_IPV4_NETWORKS:
            if ip in net:
                raise ValueError(
                    f"URL resolves to blocked IP address: {ip} (in {net})"
                )
    elif isinstance(ip, ipaddress.IPv6Address):
        for net in _BLOCKED_IPV6_NETWORKS:
            if ip in net:
                raise ValueError(
                    f"URL resolves to blocked IP address: {ip} (in {net})"
                )



def _verify_connected_peer(
    response: httpx.Response,
    validated_ips: frozenset[str],
) -> None:
    """Verify the connected peer address is in the validated set.

    Checks ``response.extensions['network_stream']`` (available in
    httpx >= 0.24) to get the actual connected peer IP and raises
    ``ValueError`` if it is not in *validated_ips*.  This closes the
    DNS-rebinding TOCTOU gap: even if a second DNS lookup returns a
    different address, the connection is only accepted if the peer
    matches the pre-validated set.

    This verification is fail-closed: when ``network_stream`` or
    ``peername`` cannot be determined, a ``ValueError`` is raised
    instead of silently succeeding, because the peer cannot be
    confirmed to be safe.

    Args:
        response: An httpx response object.
        validated_ips: Set of IP addresses validated before the request.

    Raises:
        ValueError: If the peer address cannot be determined or is not
            in the validated set.
    """
    extensions = getattr(response, "extensions", None)
    if not isinstance(extensions, dict):
        raise ValueError(
            "response.extensions not available; "
            "cannot verify connected peer"
        )

    network_stream = extensions.get("network_stream")
    if network_stream is None:
        raise ValueError(
            "response.extensions has no network_stream; "
            "cannot verify connected peer"
        )

    peername = network_stream.get_extra_info("peername")
    if peername is None:
        raise ValueError(
            "Unable to determine connected peer address "
            "(peername is None); cannot verify connection safety"
        )

    peer_ip = peername[0]
    if peer_ip not in validated_ips:
        raise ValueError(
            f"Connected to unvalidated peer {peer_ip!r} "
            f"(expected one of {sorted(validated_ips)})"
        )


class _PinnedNetworkBackend:
    """An async network backend that restricts TCP connections to validated IPs.

    Wraps a real :class:`httpcore.AsyncNetworkBackend` and only allows
    connections to IP addresses in *validated_ips*.  Hostnames are
    resolved and checked against the validated set before connecting,
    closing the DNS-rebinding TOCTOU window at the transport level.
    TLS SNI continues to use the original hostname because httpcore
    passes the request-level host separately to ``start_tls``.

    Args:
        validated_ips: Set of pre-validated IP addresses.
        real_backend: The underlying async network backend to delegate to.
    """

    def __init__(self, validated_ips: frozenset[str], real_backend: Any) -> None:
        self._validated_ips = validated_ips
        self._backend = real_backend

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> Any:
        """Connect to *host*, enforcing validated IP pinning.

        If *host* is already an IP literal, it must be in
        *validated_ips*.  Hostnames are resolved via
        ``getaddrinfo`` and the first validated IP is used for the
        connection.
        """
        # Check if host is already an IP literal
        try:
            ipaddress.ip_address(host)
            is_ip_literal = True
        except ValueError:
            is_ip_literal = False

        if is_ip_literal:
            if host not in self._validated_ips:
                raise ValueError(
                    f"Connection to {host!r} not allowed. "
                    f"Validated IPs: {sorted(self._validated_ips)}"
                )
            return await self._backend.connect_tcp(
                host, port, timeout, local_address, socket_options,
            )

        # Resolve hostname and connect to a validated IP.
        # DNS resolution is bounded by the *timeout* parameter so
        # that the overall upload/download timeout budget is not
        # exceeded by a stalled resolver.
        loop = asyncio.get_running_loop()
        dns_timeout = timeout if timeout is not None else 30.0
        try:
            addrinfo = await asyncio.wait_for(
                loop.getaddrinfo(host, port),
                timeout=dns_timeout,
            )
        except asyncio.TimeoutError:
            raise ValueError(
                f"DNS resolution timeout ({timeout}s) for hostname: "
                f"{host!r}"
            )
        except socket.gaierror as exc:
            raise ValueError(
                f"Failed to resolve hostname {host!r}: {exc}"
            ) from exc

        for _family, _type, _proto, _canonname, sa in addrinfo:
            ip = sa[0]
            if ip in self._validated_ips:
                return await self._backend.connect_tcp(
                    ip, port, timeout, local_address, socket_options,
                )

        raise ValueError(
            f"No validated IP found for hostname {host!r}. "
            f"Validated set: {sorted(self._validated_ips)}"
        )

    async def connect_unix_socket(self, path: str, timeout: float | None = None) -> Any:
        """Delegate Unix socket connections unchanged."""
        return await self._backend.connect_unix_socket(path, timeout)

    async def sleep(self, seconds: float) -> None:
        """Delegate sleep unchanged."""
        await self._backend.sleep(seconds)


def _redact_url_credentials(url: str) -> str:
    """Strip username and password from a URL for safe logging.

    Args:
        url: The URL to redact.

    Returns:
        The URL with credentials removed, or the original if none.
    """
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    if parsed.username or parsed.password:
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url


async def _download_url_content(
    url: str,
    timeout: float = 30.0,
) -> bytes:
    """Download file content from a URL with SSRF protection.

    Follows redirects manually, validating each redirect target against
    SSRF policy before following, preventing public-to-private redirects.
    Uses a transport-level IP pin to close the DNS-rebinding TOCTOU
    window: connections are only allowed to the pre-validated IP set.

    Args:
        url: The URL to download from.
        timeout: Request timeout in seconds.

    Returns:
        The raw response body bytes.

    Raises:
        ValueError: If the URL is invalid, the scheme is not allowed, the
            hostname cannot be resolved, the resolved IP is in a private/
            loopback range, the redirect chain exceeds limits, a redirect
            target fails SSRF validation, the HTTP status is an error, or
            a connection/network error occurs.
    """
    from urllib.parse import urljoin

    # Compute a monotonic deadline so the entire operation (DNS
    # validation, redirect handling, HTTP download) stays within the
    # *timeout* budget.
    deadline = time.monotonic() + timeout if timeout is not None else None

    # Pre-flight SSRF validation — returns the set of validated IPs
    # so downstream connections can be pinned to prevent DNS rebinding.
    # Performed asynchronously so DNS resolution is within the timeout budget.
    remaining = max(deadline - time.monotonic(), 0.0) if deadline is not None else None
    validated_ips = await _validate_url_safety(url, timeout=remaining)

    limits = httpx.Limits(max_keepalive_connections=1, max_connections=1)

    # Helper to build a client with IP-pinned transport for a given IP set
    # and a per-request timeout that respects the remaining deadline budget.
    def _make_client(ips: frozenset[str], remaining_timeout: float | None = None) -> httpx.AsyncClient:
        transport = httpx.AsyncHTTPTransport(limits=limits)
        # Replace the internal network backend with a pinned one
        # that only allows connections to pre-validated IPs.
        if not hasattr(transport, "_pool"):
            raise RuntimeError(
                "httpx version incompatible with SSRF IP-pinning: "
                "transport object has no '_pool' attribute."
            )
        original_backend = transport._pool._network_backend
        try:
            transport._pool._network_backend = _PinnedNetworkBackend(
                ips, original_backend,
            )
        except AttributeError as exc:
            raise RuntimeError(
                f"httpx version incompatible with SSRF IP-pinning: "
                f"transport._pool has no _network_backend attribute ({exc})."
            )
        client_timeout = httpx.Timeout(remaining_timeout) if remaining_timeout is not None else httpx.Timeout(timeout)
        return httpx.AsyncClient(
            timeout=client_timeout,
            follow_redirects=False,
            limits=limits,
            transport=transport,
        )

    client = _make_client(validated_ips, remaining)
    current_url = url

    try:
        for redirect_count in range(_MAX_REDIRECTS + 1):
            # Enforce the end-to-end deadline before every request
            if deadline is not None:
                remaining = max(deadline - time.monotonic(), 0.0)
                if remaining <= 0:
                    raise ValueError(
                        f"Download deadline ({timeout}s) exhausted "
                        f"before requesting {_redact_url_credentials(current_url)!r}"
                    )
            else:
                remaining = None

            try:
                response = await client.get(current_url, timeout=remaining)
            except httpx.TimeoutException:
                raise ValueError(
                    f"Timeout ({timeout}s) exceeded while downloading "
                    f"from {_redact_url_credentials(current_url)!r}"
                )
            except httpx.ConnectError:
                raise ValueError(
                    f"Connection error while downloading from {_redact_url_credentials(current_url)!r}"
                )
            except httpx.HTTPError as exc:
                raise ValueError(
                    f"HTTP error downloading from {_redact_url_credentials(current_url)!r}: {exc}"
                )

            # Verify the connected peer is one of the validated IPs
            # (layered defense — transport pinning above is the primary
            # TOCTOU protection; this is a post-request re-validation).
            _verify_connected_peer(response, validated_ips)

            # Follow redirects manually with SSRF validation
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    raise ValueError(
                        f"Redirect from {_redact_url_credentials(current_url)!r} missing "
                        f"Location header"
                    )
                next_url = urljoin(current_url, location)
                remaining = max(deadline - time.monotonic(), 0.0) if deadline is not None else None
                validated_ips = await _validate_url_safety(next_url, timeout=remaining)
                current_url = next_url
                # Close current client and re-create with updated IP set
                # and the remaining deadline budget
                # TODO: Optimize by reusing transport infrastructure across redirect hops
                await client.aclose()
                client = _make_client(validated_ips, remaining)
                continue

            if response.status_code >= 400:
                body = response.text[:200] if response.text else ""
                raise ValueError(
                    f"HTTP {response.status_code} ({response.reason_phrase}) error downloading "
                    f"from {_redact_url_credentials(current_url)!r}: {body}"
                )

            return response.content

        raise ValueError(
            f"Too many redirects (max {_MAX_REDIRECTS}) for "
            f"URL: {_redact_url_credentials(url)!r}"
        )
    finally:
        await client.aclose()


__all__ = [
    "InFlightTracker",
    "PersistentCacheStore",
    "UploadResult",
    "UploadSession",
    "_download_url_content",
    "_make_cache_key",
    "_validate_url_safety",
]
