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
  - [x] Verify `pyproject.toml` `[tool.pytest.ini_options]` includes `basetemp = "tmp/pytest"`
  - [x] Verify `./tmp/` directory exists (create if missing)
- [x] Create fake-client acceptance test file `tests/acceptance/test_cache_acceptance.py` with instrumented fake OpenAI client (mock transport) wired through UploadSession <!-- id: 0a -->
  - [x] `test_upload_through_repeated_chat_completions_attachments` — same file attached across repeated Chat Completions calls, verify exactly one upload occurs
  - [x] `test_persistent_cache_no_reupload_second_session` — persistent cache populated in first session; second session uses cached file_id with zero uploads
  - [x] `test_file_id_bypass_chat_completions` — pre-existing file_id attachment passes through without re-upload (FR-003)
  - [x] `test_non_image_url_through_chat_completions` — non-image URL download + upload through Chat Completions provider (fake HTTP response)
  - [x] `test_non_image_url_through_responses` — non-image URL download + inline `file_data` encoding through Responses provider (no upload endpoint / cache)
- [x] Run fake-client acceptance tests — expect GREEN (failures) since no implementation yet <!-- id: 0b -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/acceptance/test_cache_acceptance.py -v`
- [x] **After spike completion**: Add `test_streaming_path_no_full_buffer` to the acceptance suite with precise memory-behavior assertions determined by the spike results <!-- id: 0c -->
  - [x] `test_streaming_path_no_full_buffer` — streaming attachment upload does not buffer full file in memory (verify via instrumented client/memory tracking)
  - [x] Run streaming acceptance test — expect RED (failure) since no implementation yet

- [x] Create integration test file `tests/integration/test_cache_streaming_integration.py` with all 8 scenarios defined in implementation-plan.md <!-- id: 0 -->
  - [x] `test_send_pdf_through_chat_completions` — Chat Completions + PDF end-to-end
  - [x] `test_same_file_uploaded_once_chat_completions` — cache dedup
  - [x] `test_url_attachment_through_chat_completions` — non-image URL through Chat Completions
  - [x] `test_url_attachment_through_responses` — non-image URL through Responses
  - [x] `test_cache_survives_restart` — persistent cache across simulated restart
  - [x] `test_large_file_streaming_upload` — 10+ MB streaming upload through Chat Completions
  - [x] `test_large_file_streaming_upload_responses` — 10+ MB streaming upload through Responses
  - [x] `test_file_id_bypass_chat_completions` — pre-existing file_id attachment through Chat Completions without re-upload (FR-003)
- [x] Create test fixture files: `tests/fixtures/test.pdf`, `tests/fixtures/test.txt` <!-- id: 1 -->
- [x] Create integration test file (failures) since no implementation yet <!-- id: 2 -->
- [x] Create unit test file `tests/unit/test_upload_cache.py` with skeleton test cases (all fail) <!-- id: 3 -->
  - [x] `TestUploadSession` — cache hit/miss, content dedup, concurrent dedup, URL key, in-memory LRU eviction, URL-backed entries included in in-memory eviction
  - [x] `TestPersistentCacheStore` — write-read, LRU eviction, corruption, disk-full, permissions
  - [x] `TestStreamingFileAttachment` — chunk iter correctness, parity, edge cases
  - [x] `TestDownloadUrlContent` — timeout, HTTP errors, valid download

---

## Implementation Phase

### Phase 1 — UploadSession Extraction (Refactor)

- [x] Create `tinycua_sdk/providers/upload.py` module <!-- id: 4 -->
  - [x] Define `UploadResult` dataclass
  - [x] Define `InFlightTracker` with `asyncio.Event`-based deduplication
  - [x] Define `UploadSession` class with `ensure_file_id()` method
  - [x] Implement in-memory cache with LRU eviction (configurable via `session_cache_max_entries`, default 500): evict entry with oldest `last_accessed` timestamp when limit exceeded
  - [x] Implement content-based cache key: `SHA-256(content + MIME)` (hash raw file bytes, decoding base64 `data` to bytes before hashing; no filename)
  - [x] Implement URL-based cache key: `SHA-256({url}|{mime})`
  - [x] Port upload logic from `OpenAIResponsesClient._ensure_uploaded_file_id()`
  - [x] Add concurrent upload deduplication via `InFlightTracker`
- [x] Refactor `OpenAIResponsesClient` to use `UploadSession` <!-- id: 5 -->
  - [x] Remove `self._file_id_cache` dict
  - [x] Remove `self._ensure_uploaded_file_id()` method
  - [x] Accept `UploadSession` in `__init__()` (optional, creates default if not provided)
  - [x] Wire `self._upload_session.ensure_file_id` as `_upload_fn`
  - [x] Update `_make_upload_cache_key()` to remove filename from hash
- [x] Update `tests/unit/test_llm_client.py` for UploadSession refactor <!-- id: 6a -->
  - [x] Replace mock of `_file_id_cache` with mock of `UploadSession`
  - [x] Update cache key expectations (no filename in hash)
- [x] Verify existing Phase 3 Responses tests pass after refactor <!-- id: 6 -->
  - [x] Run: `cd src/tinycua-sdk && uv run pytest tests/unit/test_llm_client.py -v`

### Phase 2 — Chat Completions Upload + Cache

> **TDD Gate**: Provider translation tests are written BEFORE implementation so that
> implementation is driven by provider-native content-shape coverage.

- [x] Add RED tests in `tests/unit/test_openai_chat_client.py` for Chat Completions translation <!-- id: 6b -->
  - [x] Test `file_id` passthrough in `_translate_chat_attachment()` — file_id-only attachment maps to `{"type": "file", "file": {"file_id": "..."}}`
  - [x] Test non-image `data` upload via `_upload_fn` — non-image content triggers upload and returns file content part
  - [x] Test image MIME inline behavior unchanged — existing image data_url passthrough still works
  - [x] Test `_translate_chat_attachment()` async behavior — function is awaitable and returns correct content part
  - [x] Test `_translate_chat_messages()` async — full translation chain is awaitable
- [x] Run RED provider translation tests — expect failures (no implementation yet) <!-- id: 6c -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py -v -k "file_id or upload_fn or async_translate"`

- [x] Wire `UploadSession` into `OpenAIChatCompletionsClient` <!-- id: 7 -->
  - [x] Accept `UploadSession` in `__init__()` (optional, creates default if not provided)
- [x] Modify `_translate_chat_attachment()` for non-image + file_id support <!-- id: 8 -->
  - [x] Remove `ValueError` for non-image MIME types
  - [x] Remove `ValueError` for `file_id`-only attachments
  - [x] Add `_upload_fn` parameter
  - [x] Make function `async`
  - [x] Add mapping: `file_id` → `{"type": "file", "file": {"file_id": "..."}}`
  - [x] Add mapping: non-image `data` → upload → `{"type": "file", "file": {"file_id": "<cached>"}}`
  - [x] Add mapping: non-image `url` → stub: raise `ValueError` with clear message directing to Phase 4 (URL download support)
  - [x] Keep existing image MIME inline behavior unchanged
- [x] Make Chat Completions translation chain async <!-- id: 9 -->
  - [x] `_translate_chat_content_part()` → async
  - [x] `_translate_chat_user_message()` → async
  - [x] `_translate_chat_messages()` → async
  - [x] Update `_build_chat_payload()` to `await _translate_chat_messages()`
  - [x] Update `_chat_sync()` to `await` async translation
  - [x] Update `_chat_stream()` to `await` async translation
- [x] Update existing Chat Completions unit tests for async changes <!-- id: 10 -->
  - [x] Add `@pytest.mark.asyncio` to affected test functions
  - [x] Add `await` to `_translate_chat_attachment()` calls in tests
  - [x] Verify existing tests pass with new async signatures

### Phase 3 — Streaming Upload

> **Prerequisite**: Complete the Pre-Implementation Spike (above) to confirm the
> upload mechanism accepted by the OpenAI SDK and update memory-behavior acceptance
> criteria before implementing streaming code.

- [x] Add unit tests for streaming attachment <!-- id: 14 -->
  - [x] Test `iter_base64_chunks()` produces byte-identical output to non-streaming path
  - [x] Test `iter_raw_chunks()` produces correct raw bytes
  - [x] Test `hash_content()` matches SHA-256 of the full file
  - [x] Test chunk boundary correctness (variable file sizes, exact multiples of chunk size)
  - [x] Test empty file (0-byte) streaming
  - [x] Test very large file (generate temp file, verify memory usage bounded)
  - [x] Test `stream=True` backward-compat migration: accessing `attachment.data` on `StreamingFileAttachment` raises `ValueError` with clear message, and `stream=False` (default) still returns standard `FileAttachment` with populated `data`
- [x] Create `StreamingFileAttachment` subclass in `attachment.py` <!-- id: 11 -->
  - [x] Define class extending `FileAttachment` with `data: None`
  - [x] Add `_file_path: pathlib.Path` field
  - [x] Add `_CHUNK_SIZE: ClassVar[int] = 3 * 1024`
  - [x] Implement `iter_base64_chunks() -> Iterator[str]` — incremental base64 encoding
  - [x] Implement `iter_raw_chunks() -> Iterator[bytes]` — raw bytes chunk reader
   - [x] Implement `hash_content() -> str` — SHA-256 of full content as raw bytes for cache key (decodes base64 `data` to bytes before hashing to ensure canonical key across stream/non-stream attachments)
  - [x] Override model validator to allow `data=None` for streaming attachments
- [x] Update `FileAttachment.from_path(stream=True)` <!-- id: 12 -->
  - [x] Return `StreamingFileAttachment` when `stream=True`
  - [x] Preserve backward compat: `stream=False` still returns standard `FileAttachment`
- [x] Update `UploadSession.ensure_file_id()` for streaming upload <!-- id: 13 -->
  - [x] Detect `StreamingFileAttachment` via `isinstance` check
  - [x] Use the upload mechanism selected by task id `00` (async generator, sync file object, file path, or spooled fallback) and assert the corresponding memory behavior
  - [x] For in-memory attachments: preserve existing `BytesIO` path (or refactor to not buffer full file)
  - [x] Ensure streaming upload does not buffer full file in memory

### Phase 4 — Non-Image URL Support

- [x] Add unit tests for URL download <!-- id: 17 -->
  - [x] Test successful download (mock httpx response)
  - [x] Test timeout enforcement (mock slow response > timeout)
  - [x] Test HTTP 404 → `ValueError`
  - [x] Test HTTP 500 → `ValueError`
  - [x] Test connection error → `ValueError`
  - [x] Test invalid URL → `ValueError`
  - [x] Test non-HTTP(S) scheme → `ValueError`
  - [x] Test `localhost` → `ValueError` (SSRF)
  - [x] Test `127.0.0.1` → `ValueError` (SSRF)
  - [x] Test `::1` → `ValueError` (SSRF)
  - [x] Test `10.0.0.1` → `ValueError` (SSRF, private IPv4)
  - [x] Test `192.168.0.1` → `ValueError` (SSRF, private IPv4)
  - [x] Test `172.16.0.1` → `ValueError` (SSRF, private IPv4)
  - [x] Test `169.254.169.254` → `ValueError` (SSRF, cloud metadata endpoint)
  - [x] Test public-to-private redirect → `ValueError` (SSRF, redirect target validation)
  - [x] Test DNS rebinding / TOCTOU protection: mock resolver returns public addresses then private; custom transport rejects connection to non-validated address → `ValueError`
  - [x] Test URL cache key includes URL (different URLs, same content → different keys)
- [x] Implement `_download_url_content()` in `upload.py` <!-- id: 15 -->
  - [x] Use `httpx` async client for HTTP GET
  - [x] Enforce configurable timeout (`upload_timeout`)
  - [x] Limit redirects (max 5)
  - [x] Raise `ValueError` with URL and context on failure
  - [x] Handle: timeout, HTTP 4xx/5xx, DNS failure, connection error, invalid URL
  - [x] Restrict to HTTP(S) schemes only
  - [x] Validate resolved IP address against prohibited ranges: loopback, link-local, private, multicast, unspecified (v4+v6)
  - [x] Reject literal private/local IP URLs before request
  - [x] Re-validate redirect targets against the same IP-policy
  - [x] Prevent DNS rebinding / TOCTOU: use custom transport that connects to validated addresses explicitly; after connection, verify peer address is in the validated set and reject if not

> **TDD Gate**: URL translation tests are written BEFORE integration so that
> the translation layer has coverage for URL download + upload paths.

- [x] Add RED tests for URL translation paths <!-- id: 15a -->
  - [x] Chat Completions: test non-image URL attachment → download + upload → file content part (fake downloader/upload function) in `tests/unit/test_openai_chat_client.py`
  - [x] Responses: test non-image URL attachment → download + inline `file_data` encoding → Responses content part in `tests/unit/test_llm_client.py`
  - [x] Test URL content cache key includes URL (same content, different URLs → different cache keys)
- [x] Run RED URL translation tests — expect failures (no integration yet) <!-- id: 15b -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py tests/unit/test_llm_client.py -v -k "url upload"`

- [x] Integrate URL download into translation layer <!-- id: 16 -->
  - [x] Chat Completions: update `_translate_chat_attachment()` — replace the Phase 2 URL stub with actual download + upload using `_download_url_content()` → then upload via `UploadSession`
  - [x] Chat Completions: add mapping: non-image `url` → download + upload → `{"type": "file", "file": {"file_id": "<cached>"}}`
  - [x] Responses: `_translate_responses_attachment()` calls `_download_url_content()` for non-image URL → then encode inline as `input_file.file_data` (remove existing `ValueError`)
  - [x] Cache URL-backed results with URL-inclusive key (in-memory only; not persisted — see FR-006)

### Phase 5 — Persistent Cache

- [x] Add unit tests for persistent cache <!-- id: 22 -->
  - [x] Test write → read cycle (survives process boundary via new store instance)
  - [x] Test LRU eviction: add max_entries + 1, verify oldest evicted
  - [x] Test LRU promotion: get an entry promotes it to most recent
  - [x] Test corruption recovery: malformed JSONL line → skipped, valid entries preserved
  - [x] Test empty cache file (first run)
  - [x] Test disk-full: mock `OSError` on write → warning logged, in-memory continues
  - [x] Test permission denied: mock `PermissionError` on init → warning logged, in-memory continues
  - [x] Test multiple providers: entries scoped by provider identifier
  - [x] Test base_url scoping: two stores with different base_urls in same cache_dir use separate namespace directories and do not share entries
  - [x] Test cache_namespace scoping: two stores with different cache_namespace values in same cache_dir use separate directories
- [x] Implement `PersistentCacheStore` in `upload.py` <!-- id: 18 -->
  - [x] JSONL storage format: one entry per line
   - [x] Entry format: `{"key": "...", "file_id": "...", "mime_type": "...", "provider": "openai-chat-completions", "created_at": 1234567890.0, "last_accessed": 1234567890.0}`
  - [x] Namespace scoping: directory structure `{cache_dir}/{provider}/{base_url_hash}/{cache_namespace}/cache.jsonl` where `base_url_hash` is SHA-256 of normalized base URL and `cache_namespace` defaults to `"default"` when `None`
  - [x] Scoping prevents agents with different base URLs or credential namespaces in the same `cache_dir` from reusing each other's cache entries
  - [x] Store `base_url_hash` and `cache_namespace` in the `PersistentCacheStore` instance for cross-verification
  - [x] API keys MUST NOT be stored in any cache entry or directory path
  - [x] Atomic writes: write to temp file, rename to target path
  - [x] Corruption recovery: skip malformed lines, log warning, keep valid entries
  - [x] `get(key)` — read entry from in-memory dict (loaded from disk on init); updates `last_accessed` to promote to most-recently-used, then re-persists the reordered file
  - [x] `put(key, result)` — insert/update with current `last_accessed`; evicts entry with oldest `last_accessed` if over `max_entries`, then persists
  - [x] `clear()` — remove all entries for current provider
  - [x] Graceful degradation:
    - [x] File not found → empty cache (first run)
    - [x] Corrupt line → skip, warn, keep valid entries
    - [x] Disk full → warn, continue in-memory only
    - [x] Permission denied → warn, continue in-memory only
- [x] Wire `PersistentCacheStore` into `UploadSession` <!-- id: 19 -->
  - [x] Accept optional `provider`, `base_url`, `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` parameters in `UploadSession.__init__()`
  - [x] Create `PersistentCacheStore` (scoped by provider + base_url hash + cache_namespace) when `cache_dir` is set
  - [x] Use `session_cache_max_entries` as the in-memory cache size limit
  - [x] On cache miss: check persistent store before uploading
  - [x] On upload: write to persistent store after successful upload
  - [x] On cache hit in persistent store: promote to in-memory cache
- [x] Add `cache_dir` / `cache_max_entries` / `session_cache_max_entries` / `cache_namespace` / `upload_timeout` to `AgentConfig` <!-- id: 20 -->
  - [x] Add fields with defaults
  - [x] Support `TINYCUA_CACHE_DIR` env var as fallback for `cache_dir`
  - [x] Update `to_config()` serialization
  - [x] Update `from_config()` deserialization
  - [x] Wire `Agent.__init__()` to accept and forward `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` to `AgentConfig` <!-- id: 20a -->
- [x] Wire `AgentConfig` → `AgentExecutor` → `UploadSession` → provider <!-- id: 21 -->
  - [x] `AgentExecutor._get_llm_client()` builds `UploadSession` from config
  - [x] Store `UploadSession` on executor for cleanup in `close()`
  - [x] Update `ProviderRegistry` factory to accept optional `UploadSession`
  - [x] Update provider factory signatures
  - [x] Pass `UploadSession` to `OpenAIChatCompletionsClient` and `OpenAIResponsesClient`

### Phase 6 — Provider Factory Wiring + Cleanup

- [x] Update `ProviderRegistry` for `UploadSession` passthrough <!-- id: 23 -->
  - [x] Modify `ProviderFactory` type alias to accept optional `UploadSession`
  - [x] Update `create_client()` to accept and forward `UploadSession` parameter
  - [x] Update default factory functions for both providers
- [x] Update `AgentExecutor.close()` to clean up `UploadSession` <!-- id: 24 -->
  - [x] Close persistent cache store if open
  - [x] Clear in-memory cache
  - [x] Cancel in-flight uploads if any
- [x] Run full existing test suite to verify no regressions <!-- id: 25 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/ -v`
  - [x] `cd src/tinycua-sdk && uv run pytest tests/integration/ -v` (network-dependent tests skipped or run)
  - [x] Verify all Phase 1–4 tests pass unchanged

---

## Testing Phase

- [x] Run fake-client acceptance tests — expect GREEN (all pass) <!-- id: 25a -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/acceptance/test_cache_acceptance.py -v`
- [x] Run integration tests — expect GREEN (all pass) <!-- id: 26 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/integration/test_cache_streaming_integration.py -v`
- [x] Run unit tests for `UploadSession` and `PersistentCacheStore` <!-- id: 27 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/test_upload_cache.py -v`
- [x] Run unit tests for provider translation changes <!-- id: 28 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py -v`
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/test_llm_client.py -v`
  - [x] `cd src/tinycua-sdk && uv run pytest tests/unit/test_openai_chat_client.py -v`
- [x] Run full test suite — 508 passing <!-- id: 29 -->
  - [x] `cd src/tinycua-sdk && uv run pytest -v`

---

## Verification Phase

- [~] Manual smoke test: Chat Completions + PDF attachment, verify model response — Deferred: manual, needs real provider key <!-- id: 30 -->
- [~] Manual smoke test: URL attachment with real public PDF — Deferred: manual, needs real provider key <!-- id: 31 -->
- [~] Manual smoke test: persistent cache directory populated with `cache.jsonl` — Deferred: manual <!-- id: 32 -->
- [~] Manual smoke test: persistent cache reuse across restarts (two separate script runs) — Deferred: manual <!-- id: 33 -->
- [~] Memory profiling: verify streaming upload of 500 MB file stays under 100 MB peak memory — Deferred: manual profiling <!-- id: 34 -->
- [~] Performance check: 1000-entry LRU eviction completes in < 1 ms — Deferred: manual profiling <!-- id: 35 -->
- [x] Verify `_make_upload_cache_key` no longer includes filename (check code, not test) <!-- id: 36 -->

---

## Documentation Phase

- [x] Update `src/tinycua-sdk/README.md` with new `AgentConfig` fields (`cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout`) — Already documented in README <!-- id: 37 -->
- [~] Update `src/tinycua-sdk/docs/` if consumer-facing API docs exist — Deferred: docs/ not yet created for this feature <!-- id: 38 -->
- [~] Update `src/tinycua-sdk/CHANGELOG.md` with Phase 5 changes — Deferred: update before release <!-- id: 39 -->

---

## Review and Merge

- [x] Self-review: verify all 17 functional requirements (FR-001 through FR-017) are met — Verified in review cycle; all FRs covered <!-- id: 40 -->
- [x] Run `/review-report` to generate code review before PR <!-- id: 41 -->
- [x] Address review findings — Review findings addressed in cycle 37 <!-- id: 42 -->
- [x] Create pull request (use `gh.py`) <!-- id: 43 -->
- [x] Address review feedback — Review feedback incorporated <!-- id: 44 -->
- [~] Merge to main branch <!-- id: 45 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-23*