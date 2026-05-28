# Feature Specification: Phase 5 — File ID Cache, Streaming Upload, and Non-Image URL Support

**Status**: Implemented (495 unit tests + acceptance tests passing)
**Created**: 2026-05-23
**Last Updated**: 2026-05-24
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

### Goals

Extend the SDK's file attachment system with:

- **Chat Completions upload and caching**: Bring file upload with `file_id` caching to the Chat Completions provider (uses OpenAI `/v1/files` endpoint — Chat Completions API has no inline `file_data` content type equivalent).
- **Responses inline file content**: The Responses provider sends non-image file content inline via `input_file` + `file_data` + `filename` (base64-encoded) — no `/v1/files` upload needed. This works with any OpenAI-compatible Responses endpoint.
- **Text file inline decoding**: Both providers decode text-based MIME types (`text/plain`, `text/markdown`, `text/csv`, `application/json`, etc.) to inline text content parts — no upload or encoding overhead.
- **True streaming file handling**: Avoid materializing entire base64-encoded files in memory during both file reading and provider upload. Current `from_path(stream=True)` still produces a full in-memory base64 string, and the upload path decodes the entire file into a `BytesIO` buffer.
- **Non-image URL attachment support**: Download, upload, and cache non-image files referenced by URL (currently rejected with a `ValueError` in both providers, deferred to Phase 5).
- **Per-agent persistent cache**: Provide an optional disk-backed file ID cache that survives process restarts so previously uploaded files do not need re-uploading across sessions.
- **Cache size management**: Prevent unbounded memory growth with a simple cache eviction policy for both the in-memory session cache and the optional persistent disk cache.

### Gaps

| Gap | Impact |
|-----|--------|
| Chat Completions rejects `file_id` attachments and non-image MIME types entirely | Callers cannot send PDFs, audio, or other non-image files through Chat Completions |
| `FileAttachment.from_path(stream=True)` still materializes a full base64 string | A 100 MB file produces ~133 MB in-memory base64 string; impractical for large files |
| Upload path (`_ensure_uploaded_file_id`) decodes the full base64 payload into `BytesIO` before upload | Memory doubles (raw bytes + base64 string) for every uploaded non-image file |
| Non-image URL attachments raise `ValueError` in both providers | Callers cannot pass `FileAttachment.from_url("https://...", mime_type="application/pdf")` |
| `_file_id_cache` is per-instance and dies with the client | Restarted agents re-upload every file; no cross-session reuse |
| Cache has no eviction policy or size limit | Multi-turn sessions with many unique files leak memory |
| `_make_upload_cache_key` includes filename in the hash | Same file content with different `filename` values produces different cache keys, causing redundant uploads |

### Non-Goals

- Model-level backward compatibility: The `FileAttachment` and `ContentPart` base types are not removed or renamed. A `StreamingFileAttachment` subclass returned by `from_path(stream=True)` is a backward-compatible type addition — existing `isinstance(attachment, FileAttachment)` checks and subclass-based polymorphism continue to work.
- **Behavioral note for `stream=True` consumers**: In Phase 1–4, `from_path(stream=True)` returned a standard `FileAttachment` with `data` containing the full base64 string. In Phase 5, `from_path(stream=True)` returns a `StreamingFileAttachment` with `data=None`. Callers must use `attachment.iter_base64_chunks()` or `attachment.iter_raw_chunks()` for chunked reading, or pass `stream=False` to retain the fully-materialized behavior. This is an intentional behavioral change documented in the design migration notes (design.md §StreamingFileAttachment).
- No changes to `Agent.run(file_attachments=...)`; new optional cache configuration fields on `AgentConfig`/`Agent.__init__` (`cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout`) are in scope.
- No tool-result file support — that is Phase 6.
- No MIME type whitelist per provider beyond what the provider API itself enforces.
- No automatic file compression or format conversion.
- No file download/upload progress callbacks (can be added later).
- No distributed/shared cache across multiple processes or machines.
- No streaming URL download — URL-attached files are fully buffered in memory before upload.

### Constraints

- Backward compatibility: existing string-only messages and all Phase 1–4 attachment flows must not regress.
- All existing tests must continue to pass.
- The persistent cache must be opt-in — default behavior remains in-memory, per-session caching.
- The streaming path must produce byte-identical results to the non-streaming path for the same file.
- Non-image URL download must not block the caller indefinitely; a configurable timeout must be enforced.

---

## User Scenarios & Testing

### Primary Scenarios

1. **Chat Completions with PDF attachment**: A developer builds an agent using the `openai-chat-completions` provider. They attach a PDF via `FileAttachment.from_path("report.pdf")`. The provider uploads the file to OpenAI, caches the `file_id`, and sends a Chat Completions request referencing that `file_id`. The same file attached twice in the session only uploads once.

2. **Large file streaming**: A developer attaches a 500 MB video file via `FileAttachment.from_path("video.mp4", stream=True)`. The SDK reads the file in chunks, uploads via a streaming upload path that does not buffer the full file in memory, and the provider request carries the cached `file_id`.

3. **URL-attached non-image file**: A developer passes `FileAttachment.from_url("https://example.com/doc.pdf", mime_type="application/pdf")`. The provider downloads the file from the URL, uploads it through the provider upload endpoint, caches the `file_id`, and returns a provider-native file reference.

4. **Persistent cache reuse**: A developer enables `cache_dir="./.tinycua-cache"` on their agent. After a process restart, the agent runs with the same file attachment. The cached `file_id` is loaded from disk and used directly — no re-upload occurs.

### Acceptance Scenarios

1. **Given** a non-image file attachment sent through Chat Completions, **When** the attachment is data-backed (not an image), **Then** the Chat Completions provider uploads the file, caches the `file_id`, and emits the appropriate file reference in the request.

2. **Given** the same non-image file attachment used twice in one Chat Completions session, **When** it is translated the second time, **Then** the cached `file_id` is reused without re-uploading.

3. **Given** a file attachment backed by a non-image URL, **When** it is translated by Chat Completions, **Then** the provider downloads the file, uploads it through the upload endpoint, caches the `file_id`, and emits a file reference. **When** it is translated by Responses, **Then** the provider downloads the file, base64-encodes it, and sends it inline as ``input_file.file_data`` (no upload endpoint or cache).

4. **Given** a stream-enabled path attachment (`from_path(..., stream=True)`), **When** a non-image file is uploaded through the provider, **Then** the upload does not materialize the full base64 string or full raw bytes in memory at any point.

5. **Given** a persistent cache configured with a max size, **When** the cache exceeds the limit, **Then** least-recently-used entries are evicted.

6. **Given** the same file content with different filenames, **When** it is cached in a single session, **Then** the cache detects content-level duplication and reuses the same `file_id`.

7. **Given** a persistent cache configured, **When** a process restarts and the same file is attached, **Then** the cached `file_id` is used without re-uploading.

8. **Given** an existing `file_id`-backed attachment passed to Chat Completions, **When** it is translated, **Then** it is used directly (no upload) and emitted as a valid file reference.

9. **Given** a URL download that exceeds the configured timeout, **When** the provider attempts translation, **Then** a clear `ValueError` is raised before making a provider request.

10. **Given** existing string-only messages and Phase 1–4 attachment flows, **When** Phase 5 changes are applied, **Then** all existing tests continue to pass without modification.

11. **Given** a URL attachment with a non-HTTP(S) scheme (e.g., `file://`, `ftp://`), **When** the provider attempts translation, **Then** a `ValueError` is raised before making any network request.

12. **Given** a URL-backed attachment cached in the in-memory session cache, **When** a new session (process restart) re-attaches the same URL with persistent cache enabled, **Then** the URL content is re-downloaded and re-uploaded (the persistent cache does not store URL-backed entries) so the model receives the current file content.

13. **Given** a URL attachment targeting a private or local network address (e.g., `http://localhost/`, `http://127.0.0.1/`, `http://[::1]/`, `http://10.0.0.1/`, `http://169.254.169.254/`), **When** the URL downloader resolves the target, **Then** a `ValueError` is raised before making any network connection.

14. **Given** a URL attachment that redirects from a public URL to a private network address, **When** the URL downloader follows the redirect, **Then** the redirect target fails re-validation and a `ValueError` is raised before making a connection to the private address.

### Edge Cases

- **Empty file content**: A file with zero bytes should upload successfully and produce a valid `file_id`.
- **Very large base64 padding**: Variable-length base64 chunks should produce correct output identical to a single-shot encoding.
- **URL download failure**: DNS failures, HTTP errors, and timeouts should produce clear `ValueError` messages with the URL and error context.
- **Cache key collision**: Different files with the same hash should reuse the same `file_id` — this is correct behavior (content-addressable caching).
- **Concurrent uploads of the same file**: If the same cache-miss file is translated concurrently, only one upload should occur; subsequent requests should wait for the in-progress upload result.
- **Persistent cache file corruption**: Corrupt cache entries should be silently invalidated and re-uploaded rather than crashing.
- **Disk full during persistent cache write**: Should log a warning and continue with in-memory-only cache, not crash.
- **Cache dir permissions**: If the configured cache directory is not writable, the persistent cache should degrade gracefully to in-memory-only with a warning.
- **Provider file_id expiry**: Should not be handled in this phase — cached `file_id` values that have expired at the provider level will surface as provider errors at request time.
- **SSRF via private network URL**: An attachment URL that resolves to `localhost`, `127.0.0.1`, `::1`, private IPv4 ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), link-local addresses (169.254.0.0/16 including cloud metadata endpoint 169.254.169.254), or private IPv6 addresses must raise `ValueError` before any network connection. Redirect targets must be re-validated (public-to-private redirects are blocked).
- **Large URL download memory pressure**: `_download_url_content()` buffers the full response body in memory. Very large remote files may cause memory issues. URL download streaming (reading remote content in chunks) is deferred to a future phase.
- **Streaming attachment with non-streaming consumer**: A `StreamingFileAttachment` (created via `from_path(stream=True)`, `data=None`) passed to a code path that expects `attachment.data` to be populated will receive `None`. Callers should check for streaming attachments with `isinstance(attachment, StreamingFileAttachment)` and use chunked iteration methods when needed.

---

## Requirements

### Functional Requirements

- **FR-001**: Chat Completions provider MUST support non-image file uploads through the OpenAI `/v1/files` endpoint, with the returned `file_id` used in Chat Completions file reference content parts (Chat Completions API has no inline `file_data` equivalent).
- **FR-001a**: Responses provider MUST send non-image data-backed files inline via `input_file` + `file_data` + `filename` (base64-encoded content) — no `/v1/files` upload needed. This works with any OpenAI-compatible Responses endpoint, including local servers. Streaming file attachments (where `data` is `None` and content is read from disk on demand via `StreamingFileAttachment`) go through the upload path like Chat Completions — `/v1/files` upload is required for streaming content regardless of provider because the file size may exceed what is practical for inline encoding.
- **FR-001b**: Both providers MUST decode text-based MIME types (`text/plain`, `text/markdown`, `text/csv`, `text/html`, `application/json`, `application/xml`, etc.) to inline text content parts (`text` for Chat Completions, `input_text` for Responses) — no upload or `/v1/files` needed.
- **FR-002**: Chat Completions provider MUST maintain a per-session upload cache mapping stable content hashes to provider `file_id` values, matching the cache behavior already present in the Responses provider.
- **FR-003**: Chat Completions provider MUST accept pre-existing `FileAttachment.file_id` values and emit them directly without uploading. Responses provider MUST also pass through pre-existing `file_id` values (no upload needed in either case — Responses sends `input_file` + `file_id`).
- **FR-004**: Both Chat Completions and Responses providers MUST support non-image URL attachments by downloading the file. Chat Completions uploads via `/v1/files` and MAY reuse a per-session URL cache entry to avoid re-uploading the same URL within a session. Responses sends downloaded content inline via `input_file` + `file_data` (base64-encoded) without uploading to `/v1/files` — Responses does NOT maintain a file-ID upload cache for URL-backed attachments.
- **FR-005**: The upload cache key MUST be content-based (SHA-256 of file data + MIME type) rather than including filename metadata, so identical content with different filenames reuses the same cache entry.
- **FR-006**: The upload cache key for URL-backed attachments MUST include the URL in the hash to avoid conflating different URLs that happen to serve identical content. URL-backed cache entries MUST be stored only in the in-memory (per-session) cache, never in the persistent disk-backed cache, because remote content at a URL may change across process restarts and a cached `file_id` refers to the previously uploaded content. Each new session with a URL-backed attachment MUST re-download and re-upload the current URL content to ensure the model receives the current file.
- **FR-007**: File reading via `from_path(stream=True)` MUST yield a streaming-aware attachment object that allows the upload layer to read and upload file data without holding the entire file in memory.
- **FR-008**: The non-image upload path MUST support a streaming interface that reads source data in chunks and uploads progressively, without loading the full decoded file into a single memory buffer.
- **FR-009**: Streaming and non-streaming upload paths MUST produce byte-identical upload payloads for the same file.
- **FR-010**: The SDK MUST provide an optional persistent file ID cache backed by disk storage, configured via an `AgentConfig` field (e.g., `cache_dir: str | None`).
- **FR-011**: Persistent cache entries MUST be scoped by provider identifier, normalized base URL, and an optional user-provided `cache_namespace` via per-namespace storage files (one JSONL file per `{provider}/{base_url_hash}/{namespace}`, e.g., `{cache_dir}/openai-chat-completions/{base_url_hash}/{cache_namespace}/cache.jsonl`). The base URL is normalized (lowercase, trailing slash stripped, default OpenAI endpoint if unset) and hashed to avoid storing raw URLs in directory names. The `cache_namespace` allows users to disambiguate different API keys, accounts, or projects sharing the same `cache_dir`. If `cache_namespace` is `None`, a default namespace (e.g., `"default"`) is used. Within each namespace-scoped file, entries are keyed by content hash. API keys MUST NOT be stored in the cache or used in directory paths. This scoping ensures that two agents using the same `cache_dir` but different base URLs, provider identifiers, or credential namespaces do not reuse each other's persistent entries.
- **FR-012**: Persistent cache MUST support a configurable maximum size (default: 1000 entries), with an LRU eviction policy when the limit is exceeded.
- **FR-012a**: The in-memory session cache (`UploadSession._cache`) MUST support a configurable maximum size via a separate `session_cache_max_entries` field (default: 500 entries), with an LRU eviction policy when the limit is exceeded. This applies to both data-backed and URL-backed entries stored in the session cache, preventing unbounded memory growth even when the persistent disk cache is not enabled.
- **FR-013**: Persistent cache initialization failures (permissions, disk full, corruption) MUST degrade gracefully to in-memory-only caching with a warning log.
- **FR-014**: URL downloads MUST enforce a configurable timeout (default: 30 seconds) and raise `ValueError` on failure before making a provider request.
- **FR-014a**: URL downloads MUST only accept `http://` and `https://` schemes. Non-HTTP(S) schemes (e.g., `file://`, `ftp://`) MUST raise `ValueError` before making any network request. Redirects MUST be bounded (default: maximum 5 redirects).
- **FR-014b**: URL downloads MUST reject network targets that resolve to loopback, link-local, private, multicast, or unspecified IP ranges for both IPv4 and IPv6 before making any network request. This includes literal IP URLs (e.g., `http://127.0.0.1/`, `http://[::1]/`) and hostnames that resolve to prohibited addresses (e.g., `localhost`). Redirect targets MUST be re-validated against the same policy on every hop. The implementation MUST raise `ValueError` with a message describing the rejected address for auditing. The implementation MUST prevent DNS rebinding / time-of-check-time-of-use (TOCTOU) attacks by ensuring the HTTP transport connects to the validated address set and does not perform a second unvalidated DNS resolution. The accepted strategy is to use a custom resolver or transport that connects to the validated addresses explicitly (e.g., resolve the hostname once to obtain validated addresses, pass those addresses to the transport, and reject the connection if the connected peer address is not in the validated set). If this SDK intentionally trusts all URL inputs from callers, the trust boundary MUST be documented explicitly and SSRF network filtering deferred with rationale.
- **FR-015**: All existing Phase 1–4 tests MUST continue to pass without modification.
- **FR-016**: Unit tests MUST cover: Chat Completions upload and cache reuse, non-image URL download/upload, URL SSRF protection (localhost, 127.0.0.1, ::1, private IPs, link-local, cloud metadata endpoint, public-to-private redirects), streaming upload parity, persistent cache hit/miss/eviction/corruption, cache key content-based deduplication, concurrent upload deduplication, and graceful degradation of persistent cache.
- **FR-017**: Integration tests MUST verify: sending a non-image file through Chat Completions end-to-end, sending a non-image URL attachment through both providers, and persistent cache reuse across simulated restarts.

### Key Entities

- **`FileUploadCache`** (new): A content-addressable cache mapping SHA-256(content + MIME) → provider `file_id`. Supports both in-memory and optional disk-backed storage with LRU eviction.
- **`StreamingFileAttachment`** (new or modified `FileAttachment`): An attachment variant created by `from_path(stream=True)` that provides a chunked data reader instead of holding a full base64 string.
- **`UploadSession`** (new): Manages per-client upload state, including the in-memory cache, persistent cache adapter, and concurrent-upload deduplication (preventing duplicate uploads for the same in-flight cache-miss key).
- **`PersistentCacheStore`** (new, optional): A disk-backed LRU cache for `file_id` persistence across sessions. Uses a simple, human-readable storage format with durability guarantees.

---

## Success Criteria

- [x] **Chat Completions non-image files work**: A PDF or audio file attached via `from_path()` can be sent through the Chat Completions provider and the model responds (requires `/v1/files` — OpenAI-specific).
- [x] **Responses non-image files inline**: A PDF or other non-image file attached via `from_path()` is sent through the Responses provider as inline `input_file` + `file_data` — no `/v1/files` needed. Works with any OpenAI-compatible server.
- [x] **Text files inline (both providers)**: `.txt`, `.md`, `.csv`, `.json` and other text-based files are decoded and sent as inline text content parts — no upload or `/v1/files` needed on any provider.
- [x] **Chat Completions cache reuse works**: Attaching the same non-image file twice in one Chat Completions session uploads once and reuses the cached `file_id`.
- [x] **Chat Completions pre-existing `file_id` works**: A `FileAttachment(file_id="file_abc", ...)` is used directly without upload.
- [x] **Non-image URL attachments work**: A `FileAttachment.from_url(...)` is downloaded and used by both providers.
- [x] **Streaming upload does not buffer full file**: Uploading a file larger than available memory via the streaming path succeeds without OOM.
- [x] **Streaming parity holds**: A file uploaded via the streaming path produces the same request payload as the non-streaming path.
- [x] **Content-based cache deduplication works**: Two attachments with identical content but different `filename` values share one cache entry.
- [x] **Persistent cache survives restart**: A cached `file_id` written in one process is reused in a subsequent process with the same `cache_dir`.
- [x] **LRU eviction works**: When the cache exceeds the size limit, least-recently-used entries are evicted and most recently used entries are preserved.
- [x] **Persistent cache degrades gracefully**: Corrupt entries, permission errors, and disk-full conditions do not crash the provider; a warning is logged.
- [x] **URL download timeout enforced**: A URL that does not respond within the configured timeout raises `ValueError`.
- [x] **URL download scheme validation**: A non-HTTP(S) scheme URL (e.g., `file://`) raises `ValueError` before any network request.
- [x] **URL download SSRF protection**: A URL targeting `localhost`, `127.0.0.1`, `::1`, private IP ranges, link-local addresses, or cloud metadata endpoints raises `ValueError` before any network connection. Redirects from public to private targets are also blocked.
- [x] **URL-backed persistent cache exclusion**: A URL-backed attachment is re-downloaded on a new session with persistent cache enabled; the persistent cache does not store URL-backed entries.
- [x] **Backward compatibility holds**: All existing Phase 1–4 unit and integration tests continue to pass unchanged (495 tests passing).
- [x] **Provider `file_id` attachments pass through**: Existing `file_id`-carrying attachments work unchanged in both providers.

---

## Testing Plan

### Unit Tests

- Chat Completions upload for non-image data-backed attachments.
- Chat Completions upload cache hit reuse (same file twice, one upload call).
- Chat Completions upload for different files (two separate upload calls).
- Chat Completions pre-existing `file_id` bypass (no upload call).
- Chat Completions: non-image URL download → upload → cache.
- Responses: non-image URL download → inline `input_file.file_data` (no upload/cache).
- Content-based cache key deduplication (same content, different `filename` → one cache entry).
- URL-based cache key differentiation (different URLs, same content → separate entries).
- URL-backed attachments excluded from persistent cache (process restart → re-download).
- Streaming upload parity test (stream vs. non-stream produce identical upload payloads).
- Streaming upload chunk correctness (variable file sizes and chunk boundaries).
- Persistent cache: write → restart → read (survives process boundary).
- Persistent cache: LRU eviction when exceeding max entries.
- Persistent cache: corruption recovery (malformed cache file → warning, re-upload, rewrite).
- Persistent cache: disk-full behavior (graceful degradation, warning).
- Persistent cache: permission error (graceful degradation, warning).
- Concurrent upload deduplication (two simultaneous translations for same cache-miss key → one upload).
- URL download scheme validation (non-HTTP(S) scheme → ValueError, no network request made).
- URL download timeout enforcement (mock slow server → ValueError).
- URL download HTTP error handling (404, 500 → ValueError).
- Backward compatibility regression suite: all existing string-only and attachment tests pass.

### Integration Tests

- Send a non-image file (e.g., a small text file or PDF) through Chat Completions end-to-end and verify model response.
- Send a non-image URL attachment through Chat Completions end-to-end.
- Send a non-image URL attachment through Responses provider end-to-end.
- Persistent cache reuse across restarts: create a `FileAttachment`, upload through Responses provider, restart the client with the same `cache_dir`, attach the same file, and verify no upload request is made.
- Streaming upload of a moderately large file (>10 MB) through both providers.
- Send a pre-existing `file_id` attachment through Chat Completions end-to-end: create a `FileAttachment(file_id="file-test123", mime_type="application/pdf")`, pass to the agent, and verify no upload call is made.

### Manual Tests

- Verify Chat Completions provider sends a PDF and receives a model response referencing the file.
- Verify URL attachment with a real public file (e.g., a sample PDF from a known URL).
- Verify persistent cache directory is created and populated with entry files.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec & Design | Complete | |
| Chat Completions upload + cache | Implemented | Uses /v1/files (API limitation) |
| Responses inline file_data | Implemented | No /v1/files — sends file_data inline |
| Text file inline decoding | Implemented | Both providers decode text MIME to inline text |
| Streaming file upload | Implemented | StreamingFileAttachment + IO[bytes] upload |
| Non-image URL support | Implemented | Download + inline (Responses) or upload (CC) |
| Persistent cache | Implemented | JSONL disk cache with LRU eviction |
| LRU eviction | Implemented | In-memory + persistent both use LRU |
| Cache key dedup | Implemented | Content hash excludes filename |
| Unit tests | 495 passing | Unit + acceptance tests |
| Integration tests | Provided | Inline tests pass locally; /v1/files tests require OpenAI |

---

## Open Questions

1. **Streaming attachment API surface**
   - **Owner**: @chris
   - **Target**: 2026-05-24
   - **Status**: Resolved
   - **Proposed Answer**: Add a `StreamingFileAttachment` subclass or a separate `FileAttachment.from_path(stream=True)` path that yields a chunked reader. The `FileAttachment.data` field will be `None` for streaming attachments; the upload layer reads chunks directly from the file.
   - See: design.md

2. **Persistent cache storage format**
   - **Owner**: @chris
   - **Target**: 2026-05-24
   - **Status**: Resolved
   - **Proposed Answer**: Use a JSON lines file (`cache.jsonl`) for simplicity, with one entry per line. For production-grade durability, consider sqlite later. JSONL is human-readable, append-friendly, and trivially portable.
   - See: design.md

3. **Cache dir configuration path**
   - **Owner**: @chris
   - **Target**: 2026-05-24
   - **Status**: Resolved
   - **Proposed Answer**: Add `cache_dir: str | None = None` to `AgentConfig`. When set, the persistent cache is enabled. Default is `None` (in-memory only). The SDK respects `TINYCUA_CACHE_DIR` as a fallback env var.
   - See: design.md

4. **Non-image URL MIME type detection**
   - **Owner**: @chris
   - **Target**: 2026-05-24
   - **Status**: Resolved
   - **Proposed Answer**: Trust the caller-provided `mime_type` on `FileAttachment.from_url()`. For auto-detection, use the `Content-Type` response header after download (falls back to `application/octet-stream`). Do not add a separate `from_url` overload that auto-detects without downloading — keep `from_url()` as a simple constructor and add download-time detection in the provider layer.
   - See: design.md

---

## Review Checklist

- [x] Key entities and functional contracts are defined without code-level implementation details; algorithm references (e.g., SHA-256) and config field names (e.g., `cache_dir`) are specified as functional contracts, not implementation choices
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
