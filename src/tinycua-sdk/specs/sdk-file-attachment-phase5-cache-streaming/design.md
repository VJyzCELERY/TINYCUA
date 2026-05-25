# Design Document: Phase 5 — File ID Cache, Streaming Upload, and Non-Image URL Support

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-05-23

---

## Overview

This design extends the Phase 1–4 file attachment system with three capabilities: (1) a unified per-session file upload cache shared across Chat Completions and Responses providers, (2) a streaming file upload path that avoids loading entire files into memory, and (3) non-image URL attachment support with download-then-upload semantics for Chat Completions and download-then-inline-encode semantics for Responses. An optional persistent disk-backed cache enables file ID reuse across process restarts. All changes are contained within the `tinycua_sdk/` package, spanning `agent/`, `models/`, and `providers/` sub-packages.

---

## Architecture

### Component Overview

```
Caller
  └─ FileAttachment.from_path("large.mp4", stream=True)  → StreamingFileAttachment
  └─ FileAttachment.from_url("https://.../doc.pdf", ...)  → url-backed attachment

Agent.run(query, file_attachments=[attachment])

  v
Provider Client (OpenAIChatCompletionsClient / OpenAIResponsesClient)
  │
  ├─ UploadSession (per-client, shared)
    │   ├─ InMemoryCache: dict[content_hash → UploadResult] with LRU eviction
    │   │   └─ UploadResult: file_id, mime_type, created_at, last_accessed, expires_at
    │   ├─ PersistentCacheStore (optional, disk-backed)
    │   │   └─ LRU eviction, corruption recovery, graceful degradation, namespaced by provider+base_url+namespace
  │   └─ InFlightTracker: dict[content_hash → asyncio.Event]
  │       (prevents concurrent duplicate uploads)
  │
  ├─ _translate_chat_attachment(attachment)
  │   ├─ image/* data/url → inline image_url content parts (unchanged)
  │   ├─ file_id → direct reference (new for Chat Completions)
  │   └─ non-image data/url → upload via UploadSession → file_id reference
  │
  └─ _translate_responses_attachment(attachment)
      ├─ image/* data/url → inline input_image (unchanged)
      ├─ file_id → direct reference (unchanged, Phase 3)
      ├─ non-image data → inline via input_file + file_data (no upload)
      ├─ non-image streaming → upload via UploadSession
      ├─ non-image URL → download → inline via input_file + file_data (or upload for streaming mode)
      └─ non-image url → download → base64-encode → inline file_data (new)
```

The key architectural change is extracting the per-session upload cache and upload logic from `OpenAIResponsesClient._file_id_cache` / `_ensure_uploaded_file_id()` into a shared `UploadSession` object that both provider clients own. This eliminates code duplication and ensures consistent cache semantics.

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_sdk/providers/open_ai_chat_completions.py` | Modified | Add upload path, cache integration, non-image MIME support, file_id support |
| `tinycua_sdk/providers/open_ai_responses.py` | Modified | Refactor `_ensure_uploaded_file_id` to use shared `UploadSession`; add URL download |
| `tinycua_sdk/providers/upload.py` | New | `UploadSession`, `PersistentCacheStore`, `InFlightTracker` |
| `tinycua_sdk/models/attachment.py` | Modified | Add `StreamingFileAttachment` for stream-aware file reading |
| `tinycua_sdk/agent/config.py` | Modified | Add `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` to `AgentConfig` |
| `tinycua_sdk/agent/agent.py` | Modified | Add `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` to `Agent.__init__` and forward to `AgentConfig` |
| `tinycua_sdk/agent/executor.py` | Modified | Pass full upload cache configuration (`cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout`, plus provider/base URL) from config to provider factory |
| `tinycua_sdk/providers/registry.py` | Modified | Accept optional `UploadSession` in provider factory functions |
| `tinycua_sdk/providers/utility.py` | Modified | Update `ProviderFactory` type alias to accept optional `UploadSession` |
| `tests/unit/test_upload_cache.py` | New | Unit tests for `UploadSession`, persistent cache, streaming upload |
| `tests/unit/test_llm_client.py` | Modified | Add Chat Completions upload + URL tests |
| `tests/unit/test_openai_chat_client.py` | Modified | Extend attachment translation tests for non-image/URL/file_id |
| `tests/integration/test_cache_streaming_integration.py` | New | Integration tests for persistent cache reuse |

---

## Data Model

### New Entity: `StreamingFileAttachment`

```python
# Conceptual — extends FileAttachment semantics
StreamingFileAttachment(FileAttachment):
    data: None                          # Always None; uses _file_path instead
    _file_path: pathlib.Path            # Local file path for chunked reading
    _CHUNK_SIZE: ClassVar[int] = 3 * 1024  # Chunk size (divisible by 3)
    
    def iter_base64_chunks(self) -> Iterator[str]:
        """Yield base64-encoded chunks without full in-memory materialization."""
    
    def iter_raw_chunks(self) -> Iterator[bytes]:
        """Yield raw bytes chunks for direct upload."""
```

**Behavioral change from Phase 1–4**: The `stream=True` path in `FileAttachment.from_path()` currently creates a standard `FileAttachment` with the full base64 string in `data`. After this change, `stream=True` creates a `StreamingFileAttachment` subclass where `data` is `None` and file contents are read on demand. The `StreamingFileAttachment` provides both base64-encoded chunk iteration (for image data URLs) and raw chunk iteration (for uploads).

**Migration for existing `stream=True` consumers**: Callers that currently use `from_path(stream=True)` and later access `attachment.data` (which was populated with the full base64 string in Phase 1–4) must be updated:
- Use `attachment.iter_base64_chunks()` or `attachment.iter_raw_chunks()` for chunked reading.
- Pass `stream=False` (the default) to retain the fully-materialized `data` behavior.
- `attachment.data` on a `StreamingFileAttachment` is always `None` — callers should check for streaming attachments via `isinstance` and use chunked iteration methods.

**Backward compatibility**: Existing attachment shapes remain valid. Provider translation layers check `isinstance(attachment, StreamingFileAttachment)` and use chunked reading when available, falling back to `attachment.data` for in-memory attachments. The `FileAttachment` base type itself is unchanged — only the `stream=True` return type differs.

### New Entity: `UploadSession`

```python
# Conceptual
class UploadSession:
    """Per-client session managing file uploads, caching, and deduplication."""
    
    _cache: InMemoryCache               # dict[str, UploadResult] with LRU eviction
    _max_entries: int                   # Max in-memory cache entries (default 500)
    _persistent: PersistentCacheStore | None  # Optional disk store
    _in_flight: dict[str, asyncio.Event]      # Concurrent upload dedup
    
    async def ensure_file_id(
        self,
        client: openai.AsyncOpenAI,
        attachment: FileAttachment,
    ) -> str:
        """Return cached file_id or upload + cache. Thread-safe.
        
        On cache miss: uploads, then stores result in the in-memory cache.
        If the in-memory cache exceeds _max_entries, evicts the entry with
        the oldest last_accessed timestamp (LRU). URL-backed entries are
        included in the in-memory LRU eviction scope.
        """
    
    async def download_and_upload(
        self,
        client: openai.AsyncOpenAI,
        url: str,
        mime_type: str,
        filename: str | None,
    ) -> str:
        """Download URL content, upload, cache, return file_id."""
    
    def _make_cache_key(self, attachment: FileAttachment) -> str:
        """SHA-256 of (content or URL) + MIME type. Content-based for data
        attachments; URL-inclusive for URL attachments. URL-backed keys are
        excluded from persistent storage to prevent stale-content reuse across
        sessions."""


class UploadResult:
    file_id: str
    mime_type: str
    created_at: float
    last_accessed: float                # Updated on get() and put() for LRU recency
    expires_at: float | None            # None for in-memory; optional TTL for persistent
```

### New Entity: `PersistentCacheStore`

```python
# Conceptual
class PersistentCacheStore:
    """Disk-backed LRU cache for file_id persistence across sessions."""
    
    _path: pathlib.Path                 # Path to cache file (JSONL) — derived from cache_dir + provider + base_url_hash + cache_namespace
    _max_entries: int                   # Default 1000
    _entries: dict[str, UploadResult]   # Loaded on init, persisted on write
    
    def get(self, key: str) -> UploadResult | None: ...
    def put(self, key: str, result: UploadResult) -> None: ...
    def evict_lru(self) -> None:        # Evict entry with oldest last_accessed timestamp
    def _load(self) -> None:            # Load from disk, with corruption recovery
    def _persist(self) -> None:         # Write to disk, atomic via temp file + rename
    
    # Graceful degradation:
    # - File not found: treat as empty cache (first run)
    # - Corrupt line: skip and warn, keep valid entries
    # - Disk full: warn, continue in-memory only
    # - Permission denied: warn, continue in-memory only
```

### Schema Changes

**`AgentConfig`**:
```python
class AgentConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    # ... existing fields unchanged ...
    cache_dir: str | None = None         # NEW: enables persistent cache
    cache_max_entries: int = 1000        # NEW: max persistent cache entries
    session_cache_max_entries: int = 500 # NEW: max in-memory session cache entries
    cache_namespace: str | None = None   # NEW: account/project namespace for persistent cache
    upload_timeout: float = 30.0         # NEW: URL download timeout (seconds)

    # Also update to_config() and from_config() to round-trip the new fields,
    # including the TINYCUA_CACHE_DIR env var fallback for cache_dir.
```

**`ProviderRegistry` factory signature** — the `ProviderFactory` type alias and `ProviderRegistry.create_client()` accept an optional keyword-only `upload_session: UploadSession | None` parameter. The registry forwards the `UploadSession` object to provider constructors. Cache configuration (`cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout`) is centralized in `AgentConfig`; `AgentExecutor._get_llm_client()` constructs the `UploadSession` from config and passes it through the registry, so provider factories receive a ready-to-use session rather than raw cache parameters.

### Cache Key Changes

| Attachment Source | Old Key (Phase 3) | New Key (Phase 5) | Persistent? |
|-------------------|-------------------|-------------------|-------------|
| `data`-backed | `SHA-256({data}\|{mime}\|{filename})` | `SHA-256(content + MIME)` | Yes |
| `url`-backed | Rejected (not cached) | `SHA-256({url}\|{mime})` | **No** (in-memory only) |
| `file_id`-backed | Not cached (direct use) | Not cached (direct use) | N/A |

**Rationale**: Removing `filename` from the data cache key enables content-level deduplication. Including URL in URL cache keys prevents conflating different URLs that happen to serve identical content (they may have different access characteristics or lifetimes). URL-backed entries are **excluded from the persistent cache** because remote content at a URL may change across process restarts; a cached `file_id` from a previous upload would serve stale content. Each new session with a URL attachment re-downloads and re-uploads to ensure the model receives the current file content.

### Provider-Native Content Shape Changes

**Chat Completions — new shapes**:

```python
# File reference via file_id (pre-existing or cached)
{
    "type": "file",
    "file": {"file_id": "file-abc123"},
}

# NOTE: The Chat Completions API does NOT support inline ``file_data``
# in content parts — all non-image, non-text files are uploaded via
# ``/v1/files`` and referenced by ``file_id``. The ``file_data`` shape
# below is only available in the Responses API.
```

**Responses — new shape for URL downloads**:

```python
# Non-image URL: download, base64-encode, send inline — no /v1/files upload needed:
{
    "type": "input_file",
    "file_data": "data:application/pdf;base64,<payload>",
    "filename": "document.pdf",
}
```

---

## API / Interface Contracts

### Streaming File Reading

```python
class FileAttachment(BaseModel):
    # ... existing fields unchanged ...
    
    @classmethod
    def from_path(
        cls,
        source: str | pathlib.Path,
        mime_type: str | None = None,
        stream: bool = False,
    ) -> "FileAttachment | StreamingFileAttachment":
        """
        When stream=True, returns a StreamingFileAttachment whose ``data``
        is None and whose contents are read on demand via chunked iteration.
        
        When stream=False (default), returns a standard FileAttachment with
        the full base64-encoded data (existing behavior, unchanged).
        """
```

### UploadSession.ensure_file_id

```python
async def ensure_file_id(
    self,
    client: AsyncOpenAI,
    attachment: FileAttachment,
) -> str:
    """
    Return a provider file_id for the given attachment.
    
    Data-backed (non-image) attachments:
        - Compute cache key from content hash + MIME type.
        - On cache hit: return cached file_id.
        - On cache miss: upload, cache, return new file_id.
        - Streaming attachments: read and upload in chunks without
          full in-memory buffering.
    
    URL-backed (non-image) attachments:
        - Download file from URL with timeout.
        - Upload downloaded content.
        - Cache with URL-inclusive key in the in-memory session cache only.
        - URL-backed entries are NOT stored in the persistent disk cache
          (stale-content protection — see Technical Decision 3).
        - Return file_id.
    
    Image attachments: Should not reach this method (images use inline
    data/URL paths). Raises ValueError if called with image MIME.
    
    Pre-existing file_id attachments: Should not reach this method
    (callers check attachment.file_id first). Raises ValueError if
    called when file_id is already set.
    
    Thread safety: Uses InFlightTracker to ensure only one in-progress
    upload per unique cache key. Concurrent callers for the same key
    wait for the first upload to complete.
    """
```

### Translation Integration

**Chat Completions `_translate_chat_attachment`** — new behavior:

```python
def _translate_chat_attachment(
    attachment: FileAttachment,
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """
    Translate a FileAttachment to a Chat Completions content part.
    
    Mapping matrix:
    
    | Source         | MIME       | Result                                          |
    |----------------|------------|-------------------------------------------------|
    | file_id        | any        | {"type":"file","file":{"file_id":...}}           |
    | data + image/* | inline     | {"type":"image_url","image_url":{"url":"data:..."}} |
    | url + image/*  | URL ref    | {"type":"image_url","image_url":{"url":"..."}}  |
    | streaming img  | image/*    | {"type":"image_url","image_url":{"url":"data:..."}} |
    | data + text/*  | text       | {"type":"text","text":"..."}                    |
    | streaming text | text/*     | {"type":"text","text":"..."}                    |
    | data + non-img | upload     | {"type":"file","file":{"file_id":<cached>}}     |
    | streaming non  | upload     | {"type":"file","file":{"file_id":<cached>}}     |
    | url + non-img  | dl+upload  | {"type":"file","file":{"file_id":<cached>}}     |
    
    Raises ValueError for unsupported MIME/source combinations.
    """
```

**Responses `_translate_responses_attachment`** — modified (add URL support):

```python
async def _translate_responses_attachment(
    attachment: FileAttachment,
    *,
    _upload_fn: Callable[[FileAttachment], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """
    Mapping matrix (updated from Phase 3):
    
    | Source         | MIME       | Result                                          |
    |----------------|------------|-------------------------------------------------|
    | file_id + img  | image/*    | {"type":"input_image","file_id":...,"detail":"auto"} |
    | file_id + non  | non-image  | {"type":"input_file","file_id":...}             |
    | data + img     | image/*    | {"type":"input_image","image_url":"data:...","detail":"auto"} |
    | url + img      | image/*    | {"type":"input_image","image_url":"...","detail":"auto"} |
    | streaming img  | image/*    | {"type":"input_image","image_url":"data:...","detail":"auto"} |
    | data + text    | text/*     | {"type":"input_text","text":"..."}              |
    | streaming text | text/*     | {"type":"input_text","text":"..."}              |
    | data + non     | non-image  | Inline file_data → {"type":"input_file","file_id":null,"file_data":"data:<mime>;base64,<payload>"} |
    | streaming non  | non-image  | Upload → {"type":"input_file","file_id":...}    |
    | url + non      | non-image  | Download → {"type":"input_file","file_data":"data:<mime>;base64,<payload>"} |
    """
```

### URL Download

```python
async def _download_url_content(
    url: str,
    timeout: float = 30.0,
) -> bytes:
    """
    Download file content from a URL.
    
    Args:
        url: The URL to download from.
        timeout: Maximum time in seconds for the download.
    
    Returns:
        Raw bytes of the downloaded file.
    
    Raises:
        ValueError: If the URL is invalid, download fails, HTTP error
            occurs, or timeout is exceeded. The error message includes
            the URL and failure context.
    """
```

A simple `httpx` or `aiohttp` async HTTP GET (the SDK already depends on `httpx` via the OpenAI SDK). Uses a configurable timeout. Does not follow redirects beyond a configurable limit (default: 5). Rejects URLs with non-200 responses.

Before making any network request, the downloader validates the target IP address against loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`, `fe80::/10`), private (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`), multicast (`224.0.0.0/4`, `ff00::/8`), and unspecified (`0.0.0.0`, `::`) ranges. Literal IP URLs in these ranges are rejected at parse time. Hostname-based URLs resolve the hostname and reject the target if any resolved address falls in a prohibited range. Every redirect target is re-validated against the same policy before following, preventing public-to-private redirect bypass. Rejected requests raise `ValueError` with the rejected address in the message for auditing.

**DNS rebinding / TOCTOU protection**: The downloader resolves the hostname once to obtain the set of validated public addresses, then passes those validated addresses to the HTTP transport. The strategy uses `httpx` with a custom transport or resolver hook that connects to the validated address set directly. After the connection is established, the implementation checks that the connected peer address is one of the validated addresses and rejects the connection with `ValueError` if it is not. This closes the time-of-check/time-of-use gap: even if a second DNS resolution by the transport yields a different address (DNS rebinding attack), the connected peer is validated against the original resolution set. The accepted implementation approach is:

1. Resolve the hostname via `getaddrinfo()` to obtain all addresses.
2. Validate the complete address set against the prohibited ranges.
3. Create an `httpx.AsyncClient` transport that connects to one of the validated addresses explicitly (by IP, not hostname), and after connection, verify the peer address matches a validated address.
4. If `httpx` does not support a pinned-address transport, use a custom async HTTP client that implements the same protocol directly over a socket connected to a validated address.

### Persistent Cache

The persistent cache uses **one JSONL file per provider + base URL hash + namespace**. The `provider`, `base_url`, and `cache_namespace` parameters in the constructor determine the directory path (e.g., `{cache_dir}/openai-chat-completions/{base_url_hash}/{namespace}/cache.jsonl`). This scoping ensures that two agents using the same `cache_dir` but different base URLs or credential namespaces do not reuse each other's cached `file_id` values, preventing the cache from returning a file ID that the current client cannot access. The `provider` field in each entry is preserved for cross-verification on load — it must match the store's provider identifier, and mismatches trigger a warning and skip.

```python
class PersistentCacheStore:
    """
    Disk-backed LRU cache for provider file IDs — one file per namespace.
    
    Storage format: JSON lines file, one entry per line.
    Each line: {"key": "...", "file_id": "...", "mime_type": "...",
                 "provider": "openai-chat-completions", "created_at": 1234567890.0,
                 "last_accessed": 1234567890.0}
    
    Directory structure: {cache_dir}/{provider_name}/{base_url_hash}/{cache_namespace}/cache.jsonl
    - provider_name: The LanguageModel.provider string (e.g., "openai-chat-completions").
    - base_url_hash: SHA-256 of the normalized base URL (lowercase, trailing `/` stripped,
      default OpenAI endpoint if unset). Ensures agents with different base URLs
      do not reuse cached file_ids.
    - cache_namespace: User-provided string to disambiguate different API keys,
      accounts, or projects sharing the same cache_dir. Defaults to "default" when
      cache_namespace is None. API keys themselves MUST NOT be stored.
    
    The ``provider`` field in each entry is for cross-verification on load —
    it must match the store's provider identifier, and mismatches trigger a
    warning and skip.
    
    Atomic writes: Writes to a temp file, then renames to the target path.
    Corruption recovery: Skips malformed lines on load, logs a warning.
    """
    
    def __init__(
        self,
        cache_dir: str | pathlib.Path,
        provider: str,
        base_url: str,
        cache_namespace: str | None = None,
        max_entries: int = 1000,
    ) -> None: ...
    
    def get(self, key: str) -> UploadResult | None:
        """Return cached entry or None. Updates last_accessed to promote to most-recently-used."""
    
    def put(self, key: str, result: UploadResult) -> None:
        """Insert or update entry. Sets last_accessed. Evicts least-recently-accessed
        entry based on last_accessed timestamps if over max_entries."""
    
    def clear(self) -> None:
        """Remove all entries for this provider."""
```

### Error Handling

| Error Case | Exception | Notes |
|------------|-----------|-------|
| Chat Completions receives non-image MIME without upload path | `ValueError` only if no `_upload_fn` provided | With Phase 5, non-image uploads are supported |
| Streaming attachment used with non-streaming consumer | `ValueError("Streaming attachment requires chunked upload")` | Provider must handle streaming |
| URL download timeout | `ValueError("Timed out downloading URL '{url}' after {timeout}s")` | |
| URL download HTTP error (4xx/5xx) | `ValueError("Failed to download URL '{url}': HTTP {status}")` | |
| URL download network error | `ValueError("Failed to download URL '{url}': {error}")` | |
| Persistent cache file corrupt | Warning logged, entry skipped, continues | Graceful degradation |
| Persistent cache disk full | Warning logged, in-memory fallback | Graceful degradation |
| Persistent cache permission denied | Warning logged, in-memory fallback | Graceful degradation |
| Upload endpoint fails | Existing `ProviderApiError` / `ProviderAuthError` | Preserves current behavior |

---

## Implementation Phases

### Phase 1 — UploadSession Extraction (Refactor)

- [x] Extract `_file_id_cache` and `_ensure_uploaded_file_id` from `OpenAIResponsesClient` into new `upload.py` module.
- [x] Create `UploadSession` class with `InMemoryCache`, `InFlightTracker`.
- [x] Change cache key from `{data}|{mime}|{filename}` to `{data}|{mime}` (content-based).
- [x] Wire `UploadSession` into `OpenAIResponsesClient` — existing tests must pass.
- [x] Verify existing Phase 3 Responses tests still pass.

### Phase 2 — Chat Completions Upload + Cache

- [x] Add `_upload_fn` parameter to `_translate_chat_attachment` and `_translate_chat_user_message`.
- [x] Remove ValueError for non-image MIME types and file_id in Chat Completions — delegate to upload.
- [x] Wire `UploadSession` into `OpenAIChatCompletionsClient`.
- [x] Make `_translate_chat_messages` async (or pass upload fn through sync wrapper).
- [x] Add unit tests: upload, cache hit, cache miss, file_id bypass, content dedup.

### Phase 3 — Streaming Upload

- [x] Add `StreamingFileAttachment` subclass to `attachment.py`.
- [x] Update `FileAttachment.from_path(stream=True)` to return `StreamingFileAttachment`.
- [x] Add `iter_raw_chunks()` and `iter_base64_chunks()` to `StreamingFileAttachment`.
- [x] Update `UploadSession.ensure_file_id()` to support chunked upload via `client.files.create(file=chunked_reader)`.
- [x] Add unit tests: streaming parity, chunk boundary correctness, memory usage.

### Phase 4 — Non-Image URL Support

- [x] Add `_download_url_content()` utility to `upload.py`.
- [x] Update `_translate_chat_attachment` to handle non-image URL — download content, upload to provider, obtain `file_id`.
- [x] Update `_translate_responses_attachment` to handle non-image URL → download → base64-encode → inline `file_data` with `data:<mime>;base64,<payload>` prefix (was ValueError).
- [x] Add unit tests: URL download success, timeout, HTTP errors, cache for URL attachments.
- [x] Add integration test: real URL attachment through both providers.

### Phase 5 — Persistent Cache

- [x] Create `PersistentCacheStore` with JSONL-based storage.
- [x] Add `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` fields to `AgentConfig`.
- [x] Wire `PersistentCacheStore` into `UploadSession` when `cache_dir` is configured.
- [x] Implement LRU eviction.
- [x] Implement graceful degradation (corruption, disk full, permissions).
- [x] Add unit tests: write-read cycle, eviction, corruption recovery, degradation.
- [x] Add integration test: persistent cache reuse across simulated restarts.

### Phase 6 — Provider Factory Wiring

- [x] Update `ProviderRegistry` factory to accept `UploadSession`.
- [x] Update `AgentExecutor._call_llm()` to create `UploadSession` (with optional persistent store) and pass to provider clients.
- [x] Update `AgentConfig` with `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout`.
- [x] Verify end-to-end: `Agent.run()` with `file_attachments`, `cache_dir`, and large files.

### Phase 7 — Verification

- [x] Run full unit test suite for both providers.
- [x] Run integration tests with network-dependent tests guarded.
- [x] Run the broader tinycua-sdk test suite.
- [ ] Manual smoke test: large file upload, URL attachment, persistent cache restart.

---

## Technical Decisions

1. **Decision**: Extract upload cache into shared `UploadSession` instead of keeping per-provider caches.
   - **Reason**: Both providers use the same OpenAI upload endpoint (`client.files.create()`). A shared cache avoids code duplication and ensures consistent behavior. The cache key differentiates by content, not by provider, since the OpenAI `file_id` is provider-wide.
   - **Scope**: This decision applies to the in-memory `UploadSession` cache only. The persistent cache (`PersistentCacheStore`) DOES scope by provider per FR-011, since cached `file_id` values may be valid for a different provider on a subsequent run.
   - **Alternatives Considered**: Keep separate `_file_id_cache` per provider — rejected because it duplicates logic and risks inconsistent cache semantics.

2. **Decision**: Change data-backed cache key to exclude filename.
   - **Reason**: Two attachments with identical content but different filenames produce identical upload payloads. Including filename causes unnecessary duplicate uploads. The content hash alone (SHA-256 of data + MIME type) correctly identifies identical files.
   - **Alternatives Considered**: Keep filename in the key (Phase 3 behavior) — rejected because it prevents content deduplication, which degrades cache effectiveness for multi-turn scenarios.

3. **Decision**: URL-backed attachments include the URL in their cache key and are excluded from the persistent cache.
    - **Reason**: Different URLs may serve different content over time or have different access characteristics. Caching only by content would conflate distinct URLs. URL-inclusive keys keep url-backed entries isolated within the session. Excluding URL-backed entries from the persistent disk cache prevents serving stale content across process restarts — without a content validator (ETag, Last-Modified) or TTL, there is no reliable way to detect that remote URL content has changed. Each new session with a URL attachment re-downloads and re-uploads to guarantee the model receives current file content.
    - **Alternatives Considered**: Download first, then cache by content hash — rejected because it requires downloading on every cache miss even if the URL was previously downloaded with different content. Persistent cache with ETag/Last-Modified validation — rejected for initial release to avoid complexity; can be added later when validation tokens are available from download responses.

4. **Decision**: Use JSONL for persistent cache storage instead of SQLite.
   - **Reason**: JSONL is human-readable, trivially debuggable, append-friendly, and has zero dependencies. At the expected scale (≤1000 entries), a simple file format is sufficient. SQLite adds a dependency and complexity without proportional benefit.
   - **Alternatives Considered**: SQLite — rejected because it adds a persistent state dependency without meaningful benefit at this scale. In-memory dict pickled to disk — rejected because it's not human-readable and prone to corruption on full writes.

5. **Decision**: `StreamingFileAttachment` as a `FileAttachment` subclass instead of a separate model.
   - **Reason**: Subclass preserves the `FileAttachment` interface contract. All existing code that accepts `FileAttachment` also accepts `StreamingFileAttachment`. Provider translation layers can use `isinstance` checks to choose chunked vs. in-memory reading.
   - **Alternatives Considered**: A separate `StreamingAttachment` class — rejected because it would require duplicating all the provider translation logic. A single class with an internal `_file_path` flag — rejected because it makes the `data` field ambiguous.

6. **Decision**: Use `InFlightTracker` with `asyncio.Event` for concurrent upload deduplication.
   - **Reason**: When two concurrent translations encounter the same cache-miss key, the second should wait for the first upload to complete and share the result. `asyncio.Event` provides a lightweight, lock-free mechanism.
   - **Alternatives Considered**: `asyncio.Lock` — rejected because it serializes all uploads, not just same-key uploads. `threading.Lock` — rejected because the upload path is async-first.

7. **Decision**: Persistent cache degrades gracefully on failure.
   - **Reason**: The persistent cache is an optimization, not a correctness requirement. If it fails (corruption, disk full, permissions), the system should continue with in-memory-only caching. Crashing on cache failure would make the feature more fragile than not having it.
   - **Alternatives Considered**: Raise error on cache failure — rejected because it makes the SDK less reliable.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cache key change (removing filename) breaks existing cached entries | High | Low | Existing cache is in-memory only and per-session; no persistent data to migrate. Old sessions simply start fresh. |
| Streaming upload produces different payload than non-streaming | Medium | High | Comprehensive parity tests: same file, both paths, byte-identical results at the provider boundary. |
| URL download exposes SSRF risk | Low | High | Restrict to HTTP(S) schemes only; validate resolved IP against loopback, link-local, private, multicast, and unspecified ranges (v4+v6); reject literal private/local IP URLs before request; re-validate every redirect target against the same policy; use custom transport that connects to validated addresses to prevent DNS rebinding/TOCTOU; configurable timeout prevents hanging; redirect limit prevents infinite loops. |
| Large URL downloads cause OOM | Medium | Medium | `_download_url_content()` buffers the full response in memory. Document this as a known limitation. Callers dealing with very large remote files should download locally and use `from_path(stream=True)` instead. |
| JSONL cache file grows unbounded if entries are never evicted | Low | Medium | LRU eviction caps entries at `cache_max_entries`; atomic write-then-rename prevents partial writes. |
| OpenAI file upload endpoint changes behavior | Low | Medium | Upload logic is centralized in `UploadSession`; one change point to update. Integration tests serve as canaries. |
| Concurrent upload deduplication has edge cases with streaming | Medium | Medium | `InFlightTracker` uses content hash as key; streaming attachments compute the hash on first chunk read and check the tracker before starting the full upload. |
| Chat Completions non-image file support varies by model | Medium | Medium | Provider enforces only what the API accepts. Unsupported model errors surface as `ProviderApiError` at request time — same as other unsupported parameters. |
| `client.files.create(file=chunked_reader)` may not accept an async generator | Medium | High | The OpenAI Python SDK's `client.files.create()` may not accept an async generator for the `file` parameter. A **Phase 0 spike task** (see `task.md` <!-- id: 00 -->) must validate accepted `client.files.create()` inputs against the pinned SDK version before Phase 3 implementation begins. Based on the spike result, the implementation will use one of: direct file object (`open("path", "rb")`), sync file-like wrapper, or `tempfile.SpooledTemporaryFile` fallback. The spike outcome updates the design, tasks, and memory-behavior acceptance criteria. |

---

## Open Questions

1. **Should `StreamingFileAttachment` expose the chunk size?**
   - **Status**: Resolved
   - **Decision**: Deferred. Keep chunk size private (`_CHUNK_SIZE = 3 * 1024`) for this phase. It is an implementation detail tuned for base64 boundary alignment. Expose as a configurable parameter in a future phase if callers need control. Non-blocking.

2. **Should persistent cache entries expire after a TTL?**
   - **Status**: Resolved
   - **Decision**: Deferred. OpenAI file IDs do not have documented expiry. Adding TTL complicates the storage format without clear benefit at this stage. LRU eviction is sufficient for the initial release. Non-blocking.

3. **Should the persistent cache have a dedicated `provider` scoping?**
    - **Status**: Resolved
    - **Decision**: Yes. The persistent cache is scoped by three dimensions: provider identifier, normalized base URL (hashed), and an optional user-provided `cache_namespace`. The provider identifier is the string from `LanguageModel.provider` (e.g., `"openai-chat-completions"`, `"openai-responses"`). The base URL is normalized and hashed to avoid storing raw URLs in directory paths, ensuring agents with different base URLs do not reuse each other's cached `file_id` values. The `cache_namespace` (default `"default"` when `None`) allows users to disambiguate different API keys, accounts, or projects. API keys MUST NOT be stored in the cache. This three-level scoping is stored in the directory structure (`{cache_dir}/{provider}/{base_url_hash}/{namespace}/cache.jsonl`) and in the `provider` field of each entry for cross-verification.

---

## References

- Spec: `./spec.md`
- Phase 1 Spec: `../sdk-file-attachment-phase1/spec.md`
- Phase 1 Design: `../sdk-file-attachment-phase1/design.md`
- Phase 2 Chat Completions Spec: `../sdk-file-attachment-phase2-chat-completions/spec.md`
- Phase 2 Chat Completions Design: `../sdk-file-attachment-phase2-chat-completions/design.md`
- Phase 3 Responses Spec: `../sdk-file-attachment-phase3-openai-responses/spec.md`
- Phase 3 Responses Design: `../sdk-file-attachment-phase3-openai-responses/design.md`
- Phase 4 Agent Integration Spec: `../stage-4-agent-loop-integration/spec.md`
- Phase 4 Agent Integration Design: `../stage-4-agent-loop-integration/design.md`

> **Note**: Phase 4 uses the `stage-4-agent-loop-integration` directory naming convention, which differs from Phases 1–3 and 5 (`sdk-file-attachment-phase{N}-...`). The references above are correct and point to the existing directory.
- Issue #46: SDK-wide File Attachment Support (https://github.com/VJyzCELERY/TINYCUA/issues/46)
