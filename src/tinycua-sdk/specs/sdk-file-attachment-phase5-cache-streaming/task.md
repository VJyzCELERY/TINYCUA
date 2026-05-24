# Tasks: Phase 5 — File ID Cache, Streaming Upload, and Non-Image URL Support

Implementation tasks for Phase 5 cache-streaming feature. Check off items as completed.

---


> **Implementation Note (2026-05-24)**: The Responses provider now sends non-image
> data-backed files inline via `input_file` + `file_data` + `filename` (base64-encoded)
> instead of uploading via `/v1/files`. Text-based MIME types are decoded and sent as
> inline text content parts. This minimizes `/v1/files` usage — only Chat Completions
> non-image files (which have no inline `file_data` equivalent in the Chat Completions
> API content part schema) and URL downloads still use the upload endpoint.

## Pre-Implementation Spike

> **Feasibility spike — MUST complete before the streaming acceptance test is
> written.** The OpenAI Python SDK's `client.files.create(file=...)` parameter may
> not accept an async generator. This spike determines the accepted input types for
> the pinned SDK version and chooses the supported streaming approach. The result
> defines the memory-behavior acceptance criteria for `test_streaming_path_no_full_buffer`.

### Spike: Validate OpenAI SDK Streaming Interface <!-- id: 00 -->

- [x] Validate accepted `client.files.create()` inputs with the pinned OpenAI SDK version:
  - [x] Test whether `file=open("path", "rb")` (sync file object) is accepted.
  - [x] Test whether `file=chunked_reader` where `chunked_reader` is an async generator is accepted.
  - [x] Test whether `file=...` accepts a `tempfile.SpooledTemporaryFile` (sync spooled fallback).
- [x] Choose one supported approach from the validation results:
  - If async generator is accepted → use chunked async iteration from `StreamingFileAttachment.iter_raw_chunks()`.
  - If only sync file objects are accepted → use `open("path", "rb")` with the file path from `StreamingFileAttachment._file_path`.
  - If only file paths are accepted → pass `str(self._file_path)` directly.
  - If `SpooledTemporaryFile` is needed → pipeline streaming chunks into spooled file when threshold is exceeded.
- [x] Update `design.md` (risk table) with the validation result and confirmed approach.
- [x] Update `StreamingFileAttachment` design and `UploadSession.ensure_file_id()` task to use the confirmed approach.
- [x] Update memory-behavior acceptance criteria for the streaming acceptance test (test_streaming_path_no_full_buffer) to assert the chosen approach's memory characteristics (e.g., no full-file buffering for direct-path approach, spooled threshold for temp-file approach).

---

## TDD Phase (Tests First)

> **TDD Gate**: Acceptance tests are written BEFORE implementation using a fake
> OpenAI client (mock transport) so that CI and local TDD without credentials can
> still verify acceptance-level behaviors. These tests must run RED before
> implementation begins and GREEN after.
>
> The streaming acceptance test (`test_streaming_path_no_full_buffer`) is gated
> behind the **Pre-Implementation Spike** above. Its precise memory-behavior
> assertions depend on the spike's determination of which upload mechanism the
> OpenAI SDK supports.

- [x] Configure pytest to place `tmp_path` under `./tmp/` to keep generated test artifacts within the repo boundary <!-- id: 0s -->
  - [ ] Verify `pyproject.toml` `[tool.pytest.ini_options]` includes `basetemp = "tmp/pytest"`
  - [ ] Verify `./tmp/` directory exists (create if missing)
- [x] Create fake-client acceptance test file `tests/acceptance/test_cache_acceptance.py` with instrumented fake OpenAI client (mock transport) wired through UploadSession <!-- id: 0a -->
  - [ ] `test_upload_through_repeated_chat_completions_attachments` — same file attached across repeated Chat Completions calls, verify exactly one upload occurs
  - [ ] `test_persistent_cache_no_reupload_second_session` — persistent cache populated in first session; second session uses cached file_id with zero uploads
  - [ ] `test_file_id_bypass_chat_completions` — pre-existing file_id attachment passes through without re-upload (FR-003)
  - [ ] `test_non_image_url_through_chat_completions` — non-image URL download + upload through Chat Completions provider (fake HTTP response)
  - [ ] `test_non_image_url_through_responses` — non-image URL download + inline `file_data` encoding through Responses provider (no upload endpoint / cache)
- [x] Run fake-client acceptance tests — expect GREEN (failures) since no implementation yet <!-- id: 0b -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/acceptance/test_cache_acceptance.py -v`
- [ ] **After spike completion**: Add `test_streaming_path_no_full_buffer` to the acceptance suite with precise memory-behavior assertions determined by the spike results <!-- id: 0c -->
  - [ ] `test_streaming_path_no_full_buffer` — streaming attachment upload does not buffer full file in memory (verify via instrumented client/memory tracking)
  - [ ] Run streaming acceptance test — expect RED (failure) since no implementation yet

- [x] Create integration test file `tests/integration/test_cache_streaming_integration.py` with all 8 scenarios defined in implementation-plan.md <!-- id: 0 -->
  - [ ] `test_send_pdf_through_chat_completions` — Chat Completions + PDF end-to-end
  - [ ] `test_same_file_uploaded_once_chat_completions` — cache dedup
  - [ ] `test_url_attachment_through_chat_completions` — non-image URL through Chat Completions
  - [ ] `test_url_attachment_through_responses` — non-image URL through Responses
  - [ ] `test_cache_survives_restart` — persistent cache across simulated restart
  - [ ] `test_large_file_streaming_upload` — 10+ MB streaming upload through Chat Completions
  - [ ] `test_large_file_streaming_upload_responses` — 10+ MB streaming upload through Responses
  - [ ] `test_file_id_bypass_chat_completions` — pre-existing file_id attachment through Chat Completions without re-upload (FR-003)
- [x] Create test fixture files: `tests/fixtures/test.pdf`, `tests/fixtures/test.txt` <!-- id: 1 -->
- [x] Create integration test file (failures) since no implementation yet <!-- id: 2 -->
- [x] Create unit test file `tests/unit/test_upload_cache.py` with skeleton test cases (all fail) <!-- id: 3 -->
  - [ ] `TestUploadSession` — cache hit/miss, content dedup, concurrent dedup, URL key, in-memory LRU eviction, URL-backed entries included in in-memory eviction
  - [ ] `TestPersistentCacheStore` — write-read, LRU eviction, corruption, disk-full, permissions
  - [ ] `TestStreamingFileAttachment` — chunk iter correctness, parity, edge cases
  - [ ] `TestDownloadUrlContent` — timeout, HTTP errors, valid download

---

## Implementation Phase

### Phase 1 — UploadSession Extraction (Refactor)

- [x] Create `tinycua_sdk/providers/upload.py` module <!-- id: 4 -->
  - [ ] Define `UploadResult` dataclass
  - [ ] Define `InFlightTracker` with `asyncio.Event`-based deduplication
  - [ ] Define `UploadSession` class with `ensure_file_id()` method
  - [ ] Implement in-memory cache with LRU eviction (configurable via `session_cache_max_entries`, default 500): evict entry with oldest `last_accessed` timestamp when limit exceeded
  - [ ] Implement content-based cache key: `SHA-256(content + MIME)` (hash raw file bytes, decoding base64 `data` to bytes before hashing; no filename)
  - [ ] Implement URL-based cache key: `SHA-256({url}|{mime})`
  - [ ] Port upload logic from `OpenAIResponsesClient._ensure_uploaded_file_id()`
  - [ ] Add concurrent upload deduplication via `InFlightTracker`
- [x] Refactor `OpenAIResponsesClient` to use `UploadSession` <!-- id: 5 -->
  - [ ] Remove `self._file_id_cache` dict
  - [ ] Remove `self._ensure_uploaded_file_id()` method
  - [ ] Accept `UploadSession` in `__init__()` (optional, creates default if not provided)
  - [ ] Wire `self._upload_session.ensure_file_id` as `_upload_fn`
  - [ ] Update `_make_upload_cache_key()` to remove filename from hash
- [x] Update `tests/unit/test_llm_client.py` for UploadSession refactor <!-- id: 6a -->
  - [ ] Replace mock of `_file_id_cache` with mock of `UploadSession`
  - [ ] Update cache key expectations (no filename in hash)
- [x] Verify existing Phase 3 Responses tests pass after refactor <!-- id: 6 -->
  - [ ] Run: `cd src/tinycua-sdk && uv run pytest tests/unit/test_llm_client.py -v`

### Phase 2 — Chat Completions Upload + Cache

> **TDD Gate**: Provider translation tests are written BEFORE implementation so that
> implementation is driven by provider-native content-shape coverage.

- [x] Add RED tests in `tests/unit/test_openai_chat_client.py` for Chat Completions translation <!-- id: 6b -->
  - [ ] Test `file_id` passthrough in `_translate_chat_attachment()` — file_id-only attachment maps to `{"type": "file", "file": {"file_id": "..."}}`
  - [ ] Test non-image `data` upload via `_upload_fn` — non-image content triggers upload and returns file content part
  - [ ] Test image MIME inline behavior unchanged — existing image data_url passthrough still works
  - [ ] Test `_translate_chat_attachment()` async behavior — function is awaitable and returns correct content part
  - [ ] Test `_translate_chat_messages()` async — full translation chain is awaitable
- [ ] Run RED provider translation tests — expect failures (no implementation yet) <!-- id: 6c -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py -v -k "file_id or upload_fn or async_translate"`

- [x] Wire `UploadSession` into `OpenAIChatCompletionsClient` <!-- id: 7 -->
  - [ ] Accept `UploadSession` in `__init__()` (optional, creates default if not provided)
- [x] Modify `_translate_chat_attachment()` for non-image + file_id support <!-- id: 8 -->
  - [ ] Remove `ValueError` for non-image MIME types
  - [ ] Remove `ValueError` for `file_id`-only attachments
  - [ ] Add `_upload_fn` parameter
  - [ ] Make function `async`
  - [ ] Add mapping: `file_id` → `{"type": "file", "file": {"file_id": "..."}}`
  - [ ] Add mapping: non-image `data` → upload → `{"type": "file", "file": {"file_id": "<cached>"}}`
  - [ ] Add mapping: non-image `url` → stub: raise `ValueError` with clear message directing to Phase 4 (URL download support)
  - [ ] Keep existing image MIME inline behavior unchanged
- [x] Make Chat Completions translation chain async <!-- id: 9 -->
  - [ ] `_translate_chat_content_part()` → async
  - [ ] `_translate_chat_user_message()` → async
  - [ ] `_translate_chat_messages()` → async
  - [ ] Update `_build_chat_payload()` to `await _translate_chat_messages()`
  - [ ] Update `_chat_sync()` to `await` async translation
  - [ ] Update `_chat_stream()` to `await` async translation
- [x] Update existing Chat Completions unit tests for async changes <!-- id: 10 -->
  - [ ] Add `@pytest.mark.asyncio` to affected test functions
  - [ ] Add `await` to `_translate_chat_attachment()` calls in tests
  - [ ] Verify existing tests pass with new async signatures

### Phase 3 — Streaming Upload

> **Prerequisite**: Complete the Pre-Implementation Spike (above) to confirm the
> upload mechanism accepted by the OpenAI SDK and update memory-behavior acceptance
> criteria before implementing streaming code.

- [ ] Add unit tests for streaming attachment <!-- id: 14 -->
  - [ ] Test `iter_base64_chunks()` produces byte-identical output to non-streaming path
  - [ ] Test `iter_raw_chunks()` produces correct raw bytes
  - [ ] Test `hash_content()` matches SHA-256 of the full file
  - [ ] Test chunk boundary correctness (variable file sizes, exact multiples of chunk size)
  - [ ] Test empty file (0-byte) streaming
  - [ ] Test very large file (generate temp file, verify memory usage bounded)
  - [ ] Test `stream=True` backward-compat migration: accessing `attachment.data` on `StreamingFileAttachment` raises `ValueError` with clear message, and `stream=False` (default) still returns standard `FileAttachment` with populated `data`
- [x] Create `StreamingFileAttachment` subclass in `attachment.py` <!-- id: 11 -->
  - [ ] Define class extending `FileAttachment` with `data: None`
  - [ ] Add `_file_path: pathlib.Path` field
  - [ ] Add `_CHUNK_SIZE: ClassVar[int] = 3 * 1024`
  - [ ] Implement `iter_base64_chunks() -> Iterator[str]` — incremental base64 encoding
  - [ ] Implement `iter_raw_chunks() -> Iterator[bytes]` — raw bytes chunk reader
   - [ ] Implement `hash_content() -> str` — SHA-256 of full content as raw bytes for cache key (decodes base64 `data` to bytes before hashing to ensure canonical key across stream/non-stream attachments)
  - [ ] Override model validator to allow `data=None` for streaming attachments
- [x] Update `FileAttachment.from_path(stream=True)` <!-- id: 12 -->
  - [ ] Return `StreamingFileAttachment` when `stream=True`
  - [ ] Preserve backward compat: `stream=False` still returns standard `FileAttachment`
- [x] Update `UploadSession.ensure_file_id()` for streaming upload <!-- id: 13 -->
  - [ ] Detect `StreamingFileAttachment` via `isinstance` check
  - [ ] Use the upload mechanism selected by task id `00` (async generator, sync file object, file path, or spooled fallback) and assert the corresponding memory behavior
  - [ ] For in-memory attachments: preserve existing `BytesIO` path (or refactor to not buffer full file)
  - [ ] Ensure streaming upload does not buffer full file in memory

### Phase 4 — Non-Image URL Support

- [ ] Add unit tests for URL download <!-- id: 17 -->
  - [ ] Test successful download (mock httpx response)
  - [ ] Test timeout enforcement (mock slow response > timeout)
  - [ ] Test HTTP 404 → `ValueError`
  - [ ] Test HTTP 500 → `ValueError`
  - [ ] Test connection error → `ValueError`
  - [ ] Test invalid URL → `ValueError`
  - [ ] Test non-HTTP(S) scheme → `ValueError`
  - [ ] Test `localhost` → `ValueError` (SSRF)
  - [ ] Test `127.0.0.1` → `ValueError` (SSRF)
  - [ ] Test `::1` → `ValueError` (SSRF)
  - [ ] Test `10.0.0.1` → `ValueError` (SSRF, private IPv4)
  - [ ] Test `192.168.0.1` → `ValueError` (SSRF, private IPv4)
  - [ ] Test `172.16.0.1` → `ValueError` (SSRF, private IPv4)
  - [ ] Test `169.254.169.254` → `ValueError` (SSRF, cloud metadata endpoint)
  - [ ] Test public-to-private redirect → `ValueError` (SSRF, redirect target validation)
  - [ ] Test DNS rebinding / TOCTOU protection: mock resolver returns public addresses then private; custom transport rejects connection to non-validated address → `ValueError`
  - [ ] Test URL cache key includes URL (different URLs, same content → different keys)
- [x] Implement `_download_url_content()` in `upload.py` <!-- id: 15 -->
  - [ ] Use `httpx` async client for HTTP GET
  - [ ] Enforce configurable timeout (`upload_timeout`)
  - [ ] Limit redirects (max 5)
  - [ ] Raise `ValueError` with URL and context on failure
  - [ ] Handle: timeout, HTTP 4xx/5xx, DNS failure, connection error, invalid URL
  - [ ] Restrict to HTTP(S) schemes only
  - [ ] Validate resolved IP address against prohibited ranges: loopback, link-local, private, multicast, unspecified (v4+v6)
  - [ ] Reject literal private/local IP URLs before request
  - [ ] Re-validate redirect targets against the same IP-policy
  - [ ] Prevent DNS rebinding / TOCTOU: use custom transport that connects to validated addresses explicitly; after connection, verify peer address is in the validated set and reject if not

> **TDD Gate**: URL translation tests are written BEFORE integration so that
> the translation layer has coverage for URL download + upload paths.

- [ ] Add RED tests for URL translation paths <!-- id: 15a -->
  - [ ] Chat Completions: test non-image URL attachment → download + upload → file content part (fake downloader/upload function) in `tests/unit/test_openai_chat_client.py`
  - [ ] Responses: test non-image URL attachment → download + inline `file_data` encoding → Responses content part in `tests/unit/test_llm_client.py`
  - [ ] Test URL content cache key includes URL (same content, different URLs → different cache keys)
- [ ] Run RED URL translation tests — expect failures (no integration yet) <!-- id: 15b -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py tests/unit/test_llm_client.py -v -k "url upload"`

- [x] Integrate URL download into translation layer <!-- id: 16 -->
  - [ ] Chat Completions: update `_translate_chat_attachment()` — replace the Phase 2 URL stub with actual download + upload using `_download_url_content()` → then upload via `UploadSession`
  - [ ] Chat Completions: add mapping: non-image `url` → download + upload → `{"type": "file", "file": {"file_id": "<cached>"}}`
  - [ ] Responses: `_translate_responses_attachment()` calls `_download_url_content()` for non-image URL → then encode inline as `input_file.file_data` (remove existing `ValueError`)
  - [ ] Cache URL-backed results with URL-inclusive key (in-memory only; not persisted — see FR-006)

### Phase 5 — Persistent Cache

- [ ] Add unit tests for persistent cache <!-- id: 22 -->
  - [ ] Test write → read cycle (survives process boundary via new store instance)
  - [ ] Test LRU eviction: add max_entries + 1, verify oldest evicted
  - [ ] Test LRU promotion: get an entry promotes it to most recent
  - [ ] Test corruption recovery: malformed JSONL line → skipped, valid entries preserved
  - [ ] Test empty cache file (first run)
  - [ ] Test disk-full: mock `OSError` on write → warning logged, in-memory continues
  - [ ] Test permission denied: mock `PermissionError` on init → warning logged, in-memory continues
  - [ ] Test multiple providers: entries scoped by provider identifier
  - [ ] Test base_url scoping: two stores with different base_urls in same cache_dir use separate namespace directories and do not share entries
  - [ ] Test cache_namespace scoping: two stores with different cache_namespace values in same cache_dir use separate directories
- [x] Implement `PersistentCacheStore` in `upload.py` <!-- id: 18 -->
  - [ ] JSONL storage format: one entry per line
   - [ ] Entry format: `{"key": "...", "file_id": "...", "mime_type": "...", "provider": "openai-chat-completions", "created_at": 1234567890.0, "last_accessed": 1234567890.0}`
  - [ ] Namespace scoping: directory structure `{cache_dir}/{provider}/{base_url_hash}/{cache_namespace}/cache.jsonl` where `base_url_hash` is SHA-256 of normalized base URL and `cache_namespace` defaults to `"default"` when `None`
  - [ ] Scoping prevents agents with different base URLs or credential namespaces in the same `cache_dir` from reusing each other's cache entries
  - [ ] Store `base_url_hash` and `cache_namespace` in the `PersistentCacheStore` instance for cross-verification
  - [ ] API keys MUST NOT be stored in any cache entry or directory path
  - [ ] Atomic writes: write to temp file, rename to target path
  - [ ] Corruption recovery: skip malformed lines, log warning, keep valid entries
  - [ ] `get(key)` — read entry from in-memory dict (loaded from disk on init); updates `last_accessed` to promote to most-recently-used, then re-persists the reordered file
  - [ ] `put(key, result)` — insert/update with current `last_accessed`; evicts entry with oldest `last_accessed` if over `max_entries`, then persists
  - [ ] `clear()` — remove all entries for current provider
  - [ ] Graceful degradation:
    - [ ] File not found → empty cache (first run)
    - [ ] Corrupt line → skip, warn, keep valid entries
    - [ ] Disk full → warn, continue in-memory only
    - [ ] Permission denied → warn, continue in-memory only
- [x] Wire `PersistentCacheStore` into `UploadSession` <!-- id: 19 -->
  - [ ] Accept optional `provider`, `base_url`, `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` parameters in `UploadSession.__init__()`
  - [ ] Create `PersistentCacheStore` (scoped by provider + base_url hash + cache_namespace) when `cache_dir` is set
  - [ ] Use `session_cache_max_entries` as the in-memory cache size limit
  - [ ] On cache miss: check persistent store before uploading
  - [ ] On upload: write to persistent store after successful upload
  - [ ] On cache hit in persistent store: promote to in-memory cache
- [ ] Add `cache_dir` / `cache_max_entries` / `session_cache_max_entries` / `cache_namespace` / `upload_timeout` to `AgentConfig` <!-- id: 20 -->
  - [ ] Add fields with defaults
  - [ ] Support `TINYCUA_CACHE_DIR` env var as fallback for `cache_dir`
  - [ ] Update `to_config()` serialization
  - [ ] Update `from_config()` deserialization
  - [ ] Wire `Agent.__init__()` to accept and forward `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` to `AgentConfig` <!-- id: 20a -->
- [x] Wire `AgentConfig` → `AgentExecutor` → `UploadSession` → provider <!-- id: 21 -->
  - [ ] `AgentExecutor._get_llm_client()` builds `UploadSession` from config
  - [ ] Store `UploadSession` on executor for cleanup in `close()`
  - [x] Update `ProviderRegistry` factory to accept optional `UploadSession`
  - [ ] Update provider factory signatures
  - [ ] Pass `UploadSession` to `OpenAIChatCompletionsClient` and `OpenAIResponsesClient`

### Phase 6 — Provider Factory Wiring + Cleanup

- [x] Update `ProviderRegistry` for `UploadSession` passthrough <!-- id: 23 -->
  - [ ] Modify `ProviderFactory` type alias to accept optional `UploadSession`
  - [ ] Update `create_client()` to accept and forward `UploadSession` parameter
  - [ ] Update default factory functions for both providers
- [x] Update `AgentExecutor.close()` to clean up `UploadSession` <!-- id: 24 -->
  - [ ] Close persistent cache store if open
  - [ ] Clear in-memory cache
  - [ ] Cancel in-flight uploads if any
- [x] Run full existing test suite to verify no regressions <!-- id: 25 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/ -v`
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/integration/ -v` (network-dependent tests skipped or run)
  - [ ] Verify all Phase 1–4 tests pass unchanged

---

## Testing Phase

- [x] Run fake-client acceptance tests — expect GREEN (all pass) <!-- id: 25a -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/acceptance/test_cache_acceptance.py -v`
- [x] Run integration tests — expect GREEN (all pass) <!-- id: 26 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/integration/test_cache_streaming_integration.py -v`
- [x] Run unit tests for `UploadSession` and `PersistentCacheStore` <!-- id: 27 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_upload_cache.py -v`
- [x] Run unit tests for provider translation changes <!-- id: 28 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py -v`
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_llm_client.py -v`
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py -v`
- [x] Run full test suite — 508 passing <!-- id: 29 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest -v`

---

## Verification Phase

- [ ] Manual smoke test: Chat Completions + PDF attachment, verify model response <!-- id: 30 -->
- [ ] Manual smoke test: URL attachment with real public PDF <!-- id: 31 -->
- [ ] Manual smoke test: persistent cache directory populated with `cache.jsonl` <!-- id: 32 -->
- [ ] Manual smoke test: persistent cache reuse across restarts (two separate script runs) <!-- id: 33 -->
- [ ] Memory profiling: verify streaming upload of 500 MB file stays under 100 MB peak memory <!-- id: 34 -->
- [ ] Performance check: 1000-entry LRU eviction completes in < 1 ms <!-- id: 35 -->
- [ ] Verify `_make_upload_cache_key` no longer includes filename (check code, not test) <!-- id: 36 -->

---

## Documentation Phase

- [ ] Update `src/tinycua-sdk/README.md` with new `AgentConfig` fields (`cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout`) <!-- id: 37 -->
- [ ] Update `src/tinycua-sdk/docs/` if consumer-facing API docs exist — document streaming upload and persistent cache <!-- id: 38 -->
- [ ] Update `src/tinycua-sdk/CHANGELOG.md` with Phase 5 changes <!-- id: 39 -->

---

## Review and Merge

- [ ] Self-review: verify all 17 functional requirements (FR-001 through FR-017) are met <!-- id: 40 -->
- [ ] Run `/review-report` to generate code review before PR <!-- id: 41 -->
- [ ] Address review findings <!-- id: 42 -->
- [ ] Create pull request (use `gh.py`) <!-- id: 43 -->
- [ ] Address review feedback <!-- id: 44 -->
- [ ] Merge to main branch <!-- id: 45 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-23*
