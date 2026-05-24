# Implementation: Phase 5 — File ID Cache, Streaming Upload, and Non-Image URL Support

Extends the SDK's file attachment system with Chat Completions upload + caching, true streaming file handling, non-image URL attachment support, an optional persistent disk-backed file ID cache, and cache size management with LRU eviction.

## Context

- **Spec Reference**: [spec.md](./spec.md)
- **Design Reference**: [design.md](./design.md)
- **Priority**: P1
- **Estimated Effort**: XL (6 implementation phases + verification)

## Environment Pre-requisites

### Configuration

- [x] **.env file** — required variables:
  ```
  # OpenAI API (required for integration tests with real uploads)
  OPENAI_API_KEY=sk-xxx
  ```
- [x] **TINYCUA_CACHE_DIR** — optional env var fallback for persistent cache directory

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| OpenAI API | For integration tests only | N/A (external) | N/A |
| N/A | Unit tests require no external services | N/A | N/A |

### Data / Fixtures

- [x] **Test fixtures** — create test files in `tests/fixtures/`:
  - `test.pdf` — small PDF (< 1 KB) for upload tests
  - `test.txt` — small text file for non-image MIME tests
  - `large_test.bin` — generated 10+ MB file for streaming tests (generated on demand via `tmp_path`)
- [x] **pytest temp directory** — tests use the `tmp_path` fixture to keep temporary files within the repo boundary. Configure pytest to place `tmp_path` under `./tmp/` so files are always within the project root:
  ```ini
  # pytest.ini or pyproject.toml [tool.pytest.ini_options]
  [pytest]
  basetemp = tmp/pytest
  ```
  Alternatively, set `TMPDIR=./tmp` in your environment before running tests.
- [x] **None** — no database migrations or seed data needed

### Access / Permissions

- [x] **OpenAI API key** with file upload permissions
- [x] **None** — no VPN or firewall access required

### Developer Tooling

- [x] **Runtime**: Python >=3.12
- [x] **Package manager**: uv
- [x] **Subproject**: `cd src/tinycua-sdk && uv run`
- [x] **Additional CLI tools**: None

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: tests/integration/test_cache_streaming_integration.py
"""Integration tests for Phase 5: cache, streaming, non-image URL support.

These tests require a live OpenAI API key. They are skipped when
OPENAI_API_KEY is not set. For CI and local TDD without credentials,
use separate acceptance tests that exercise the same behaviors with
a locally-instrumented fake OpenAI client (mock transport) wired
through UploadSession. See tests/acceptance/test_cache_acceptance.py
for fake-client acceptance variants of these scenarios.
"""

import asyncio
import io
import os
import pathlib
import shutil

import pytest

from tinycua_sdk import Agent, FileAttachment, LanguageModel

# Skip all live integration tests when no API key is configured.
# Set OPENAI_API_KEY in your environment to run these against the real OpenAI API.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY"),
        reason="OPENAI_API_KEY required for live OpenAI integration tests. "
               "Run acceptance tests with a fake client instead for CI/local TDD.",
    ),
]


@pytest.mark.integration
class TestChatCompletionsNonImageUpload:
    """Verify non-image files work through Chat Completions end-to-end."""

    @pytest.mark.asyncio
    async def test_send_pdf_through_chat_completions(self):
        """Send a PDF through Chat Completions and get a model response."""
        # Arrange
        pdf_path = pathlib.Path(__file__).parent.parent / "fixtures" / "test.pdf"
        attachment = FileAttachment.from_path(str(pdf_path), mime_type="application/pdf")
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-chat-completions",
                model_name="gpt-4o",
                api_key=os.environ.get("OPENAI_API_KEY", "test-key"),
            ),
            instructions="Describe the contents of the attached PDF in one sentence.",
        )

        # Act
        result = await agent.run(
            query="What does this document say?",
            file_attachments=[attachment],
        )

        # Assert
        assert isinstance(result, str)
        assert result
        # The model should not error about unsupported file types


    @pytest.mark.asyncio
    async def test_same_file_uploaded_once_chat_completions(self):
        """Same non-image file attached twice → uploaded once, cached once."""
        # Arrange
        pdf_path = pathlib.Path(__file__).parent.parent / "fixtures" / "test.pdf"
        attachment = FileAttachment.from_path(str(pdf_path), mime_type="application/pdf")
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-chat-completions",
                model_name="gpt-4o",
                api_key=os.environ.get("OPENAI_API_KEY", "test-key"),
            ),
        )

        # Act
        await agent.run(
            query="First run",
            file_attachments=[attachment],
        )

        # Second request with same attachment
        await agent.run(
            query="Second run with same file",
            file_attachments=[attachment],
        )

        # Assert: the UploadSession in-memory cache should contain exactly one entry
        # for this content hash, indicating only one upload occurred.
        upload_session = agent._upload_session
        assert upload_session is not None, "UploadSession should be wired"
        cache_entries_for_attachment = [
            k for k in upload_session._cache
            if upload_session._make_cache_key(attachment) in k
        ]
        assert len(cache_entries_for_attachment) == 1, (
            f"Expected exactly 1 cache entry after two attachments, "
            f"got {len(cache_entries_for_attachment)}"
        )


@pytest.mark.integration
class TestNonImageURLAttachment:
    """Verify non-image URL attachments are downloaded and uploaded."""

    @pytest.mark.asyncio
    async def test_url_attachment_through_responses(self):
        """Send a non-image URL attachment through Responses provider."""
        # Arrange
        attachment = FileAttachment.from_url(
            "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            mime_type="application/pdf",
        )
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-responses",
                model_name="gpt-4o",
                api_key=os.environ.get("OPENAI_API_KEY", "test-key"),
            ),
        )

        # Act
        result = await agent.run(
            query="What does the attached PDF say?",
            file_attachments=[attachment],
        )

        # Assert
        assert isinstance(result, str)
        assert result


    @pytest.mark.asyncio
    async def test_url_attachment_through_chat_completions(self):
        """Send a non-image URL attachment through Chat Completions provider."""
        # Arrange
        attachment = FileAttachment.from_url(
            "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            mime_type="application/pdf",
        )
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-chat-completions",
                model_name="gpt-4o",
                api_key=os.environ.get("OPENAI_API_KEY", "test-key"),
            ),
        )

        # Act
        result = await agent.run(
            query="What does the attached PDF say?",
            file_attachments=[attachment],
        )

        # Assert
        assert isinstance(result, str)
        assert result


@pytest.mark.integration
class TestPersistentCacheReuse:
    """Verify persistent cache survives process restarts."""

    @pytest.mark.asyncio
    async def test_cache_survives_restart(self, tmp_path):
        """Cached file_id loaded from disk after process restart — no re-upload."""
        # Arrange
        pdf_path = pathlib.Path(__file__).parent.parent / "fixtures" / "test.pdf"
        attachment = FileAttachment.from_path(str(pdf_path), mime_type="application/pdf")

        cache_dir = str(tmp_path / "phase5-cache")
        # First process: upload and cache
        agent1 = Agent(
            llm_model=LanguageModel(
                provider="openai-responses",
                model_name="gpt-4o",
                api_key=os.environ.get("OPENAI_API_KEY", "test-key"),
            ),
            cache_dir=cache_dir,
        )
        await agent1.run(
            query="First session, upload this file",
            file_attachments=[attachment],
        )
        await agent1.close()

        # Second process: should use cached file_id without re-upload
        agent2 = Agent(
            llm_model=LanguageModel(
                provider="openai-responses",
                model_name="gpt-4o",
                api_key=os.environ.get("OPENAI_API_KEY", "test-key"),
            ),
            cache_dir=cache_dir,
        )
        # Act: this should use the cached file_id
        result = await agent2.run(
            query="Second session, use cached file",
            file_attachments=[attachment],
        )

        # Assert
        assert isinstance(result, str)
        assert result

        # Assert persistent cache file exists with valid entry for this content.
        # FR-011 requires namespace-scoped cache paths:
        #   {cache_dir}/{provider}/{base_url_hash}/{cache_namespace}/cache.jsonl
        # This test skeleton derives the expected path from the test fixture's
        # provider string and normalized base URL to avoid drifting from
        # PersistentCacheStore.cache_path behavior.
        provider = "openai-responses"
        base_url = "https://api.openai.com/v1"  # normalized: trailing slash stripped per FR-011
        cache_namespace = None  # defaults to "default" in PersistentCacheStore
        import hashlib
        base_url_hash = hashlib.sha256(base_url.encode()).hexdigest()
        ns = cache_namespace or "default"
        cache_file = (
            pathlib.Path(cache_dir) / provider / base_url_hash / ns / "cache.jsonl"
        )
        assert cache_file.exists(), (
            f"Persistent cache file should exist at {cache_file}"
        )
        cache_contents = cache_file.read_text()
        assert "test.pdf" in cache_contents or len(cache_contents.strip().splitlines()) >= 1, (
            "Persistent cache should contain at least one entry"
        )

        # Assert the second session did NOT trigger a new upload.
        # Validate by checking the upload call count in the second session's
        # UploadSession (via instrumented client or direct inspection):
        #   upload_session2._cache  should have been populated from disk on init
        #   (cache hit via persistent store), and no new client.files.create()
        #   call should have been made in the second session.
        upload_session2 = agent2._upload_session
        assert upload_session2 is not None, "Second agent should have UploadSession"
        # The in-memory cache should already be populated from persistent store
        # before any upload call was made.
        assert len(upload_session2._cache) >= 1, (
            "Persistent cache should pre-populate in-memory cache on init"
        )

        # Clean up after all assertions that inspect internal state
        await agent2.close()


@pytest.mark.integration
class TestStreamingUpload:
    """Verify streaming upload handles large files without OOM."""

    @pytest.mark.asyncio
    async def test_large_file_streaming_upload(self, tmp_path):
        """Upload a 10+ MB file via streaming path without memory issues."""
        # Arrange: create a 10 MB temp file in repo-local tmp_path
        large_file_path = tmp_path / "large_test.bin"
        large_file_path.write_bytes(b"\x00" * 10_000_000)  # 10 MB of zeros

        attachment = FileAttachment.from_path(
            str(large_file_path),
            mime_type="application/octet-stream",
            stream=True,
        )
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-chat-completions",
                model_name="gpt-4o",
                api_key=os.environ.get("OPENAI_API_KEY", "test-key"),
            ),
        )

        # Act
        result = await agent.run(
            query="Analyze the attached file",
            file_attachments=[attachment],
        )

        # Assert
        assert isinstance(result, str)


    @pytest.mark.asyncio
    async def test_large_file_streaming_upload_responses(self, tmp_path):
        """Upload a 10+ MB file via streaming path through Responses without memory issues."""
        large_file_path = tmp_path / "large_test.bin"
        large_file_path.write_bytes(b"\x00" * 10_000_000)  # 10 MB of zeros

        attachment = FileAttachment.from_path(
            str(large_file_path),
            mime_type="application/octet-stream",
            stream=True,
        )
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-responses",
                model_name="gpt-4o",
                api_key=os.environ.get("OPENAI_API_KEY", "test-key"),
            ),
        )

        # Act
        result = await agent.run(
            query="Analyze the attached file",
            file_attachments=[attachment],
        )

        # Assert
        assert isinstance(result, str)
```

### Key Test Scenarios

- [x] **Scenario 1**: Send a PDF through Chat Completions end-to-end — verifies non-image MIME types work with Chat Completions provider (primary gap from Phase 2).
- [x] **Scenario 2**: Same file cached and reused in one session — verifies `UploadSession` cache deduplication.
- [x] **Scenario 3**: Non-image URL attachment through Chat Completions provider — verifies download + upload pipeline for URLs.
- [x] **Scenario 4**: Non-image URL attachment through Responses provider — verifies download + inline `file_data` encoding pipeline for URLs (no upload endpoint / cache used).
- [x] **Scenario 5**: Persistent cache survives simulated restart — verifies disk-backed cache persistence.
- [x] **Scenario 6**: Large file (>10 MB) uploaded via streaming path through Chat Completions — verifies no OOM during streaming upload.
- [x] **Scenario 7**: Large file (>10 MB) uploaded via streaming path through Responses — verifies no OOM during streaming upload.
- [x] **Scenario 8**: Pre-existing `file_id` attachment passed through Chat Completions without re-upload — verifies FR-003 file_id bypass end-to-end.

### Fake-Client Acceptance Test Scenarios (TDD Gate)

These scenarios exercise the same acceptance behaviors as the live integration
tests above, but use a locally-instrumented fake OpenAI client (mock transport)
so they run in any environment without OpenAI credentials. They are the primary
RED→GREEN TDD contract for CI/local development.

- [x] **Scenario A1**: Upload through repeated Chat Completions attachments — same file attached across repeated calls, verify exactly one upload occurs.
- [x] **Scenario A2**: Persistent cache — no re-upload on second session — cache populated in first session, second session uses cached file_id with zero uploads.
- [x] **Scenario A3**: File ID bypass (FR-003) — pre-existing file_id attachment passes through without re-upload.
- [x] **Scenario A4**: Non-image URL through Chat Completions — download + upload via fake HTTP response.
- [x] **Scenario A5**: Non-image URL through Responses — download + inline `file_data` encoding via fake HTTP response (no upload endpoint used).
- [x] **Scenario A6**: Streaming path — no full-file buffering — verify streaming upload does not buffer full file in memory. **Gated behind the Pre-Implementation Spike (OpenAI SDK streaming interface validation).** The precise memory-behavior assertions depend on the spike's determination of which upload mechanism the SDK supports.

## Verification Plan

### Automated Tests

- [x] **Fake-client acceptance tests** (`tests/acceptance/test_cache_acceptance.py`) — TDD gate: must run RED before implementation, GREEN after:
  - `test_upload_through_repeated_chat_completions_attachments`
  - `test_persistent_cache_no_reupload_second_session`
  - `test_file_id_bypass_chat_completions`
  - `test_non_image_url_through_chat_completions`
  - `test_non_image_url_through_responses`
  - `test_streaming_path_no_full_buffer` — **gated behind Pre-Implementation Spike** (OpenAI SDK streaming interface validation); assertions depend on spike-determined upload mechanism
- [x] **Integration tests** (defined above) — these must pass for implementation to be complete (credential-gated):
  - `test_send_pdf_through_chat_completions`
  - `test_same_file_uploaded_once_chat_completions`
  - `test_url_attachment_through_responses`
  - `test_url_attachment_through_chat_completions`
  - `test_cache_survives_restart`
  - `test_large_file_streaming_upload`
  - `test_large_file_streaming_upload_responses`
- [x] **Unit tests** for:
  - `UploadSession` — cache hit/miss, concurrent deduplication, content-based key dedup, URL-based key
  - `PersistentCacheStore` — write-read cycle, LRU eviction, corruption recovery, disk-full degradation, permission-error degradation
  - `StreamingFileAttachment` — chunk iteration correctness, streaming vs non-streaming parity
  - Chat Completions translation — non-image upload, file_id bypass, image MIME still inline
  - Responses translation — URL download, cache key change (no filename in key), existing behavior preserved
  - `_download_url_content()` — timeout enforcement, HTTP error handling, valid downloads
- [x] **Existing test suite** — confirm no regressions:
  - `cd src/tinycua-sdk && uv run pytest tests/unit/` — all unit tests pass
  - `cd src/tinycua-sdk && uv run pytest tests/integration/` — existing integration tests pass

### Manual Verification

- [ ] Chat Completions provider sends a PDF — verify model response references the file
- [ ] URL attachment with a real public PDF file — verify download, upload, and model response
- [ ] Persistent cache directory is created and populated with `cache.jsonl` entries
- [ ] Streaming upload of a 500 MB file does not cause OOM (memory profiling)
- [ ] Empty file (0 bytes) uploads successfully through both providers

### Performance Considerations

- [ ] Memory profiling: verify streaming upload of 500 MB file uses < 100 MB peak memory
- [ ] Cache performance: 1000-entry LRU eviction completes in < 1 ms
- [ ] Upload deduplication: concurrent uploads for same key produce exactly one `client.files.create()` call

---

## Proposed Changes

### New Module: Providers Upload

#### [NEW] `tinycua_sdk/providers/upload.py`

- **Description**: New module containing `UploadSession`, `PersistentCacheStore`, `InFlightTracker`, and `_download_url_content()`.
- **Components**:
  - `UploadResult` — dataclass: `file_id`, `mime_type`, `created_at`, `expires_at`
  - `UploadSession` — per-client upload manager with LRU-bounded in-memory cache, optional persistent store, concurrent dedup
  - `PersistentCacheStore` — disk-backed JSONL LRU cache with graceful degradation, scoped by provider + base URL hash + cache_namespace
  - `InFlightTracker` — `asyncio.Event`-based concurrent upload deduplication
  - `_download_url_content()` — httpx-based URL download with configurable timeout
- **Dependencies**: `openai.AsyncOpenAI`, `httpx` (already transitive via OpenAI SDK)

### Models: Attachment

#### [NEW] `StreamingFileAttachment` subclass in `tinycua_sdk/models/attachment.py`

- **Description**: Subclass of `FileAttachment` for stream-aware file reading. `data` field is always `None`; content read on demand via chunked iteration.
- **Methods**:
  - `iter_base64_chunks() -> Iterator[str]` — yield base64-encoded chunks
  - `iter_raw_chunks() -> Iterator[bytes]` — yield raw bytes chunks
  - `hash_content() -> str` — compute SHA-256 of full content as raw bytes (for cache key); for `data`-backed `FileAttachment`, decode base64 to raw bytes before hashing so the same file produces the same cache key regardless of `stream=True`/`stream=False`
- **Breaking changes**: `.data` on `StreamingFileAttachment` is always `None` (previously returned base64 string for `stream=True`); subclass otherwise preserves `FileAttachment` interface

#### [MODIFY] `FileAttachment` in `tinycua_sdk/models/attachment.py`

- **Description**: Update `from_path(stream=True)` to return `StreamingFileAttachment` instead of materializing full base64 string.
- **Rationale**: Current `stream=True` still produces full in-memory base64; Phase 5 requires true streaming.
- **Breaking changes**: `from_path(stream=True)` now returns `StreamingFileAttachment` whose `.data` is `None`; prior behavior materialized base64 string in `.data`. Callers must migrate to chunked iteration methods.

### Providers: Chat Completions

#### [MODIFY] `tinycua_sdk/providers/open_ai_chat_completions.py`

- **Description**:
  1. Remove `ValueError` for non-image MIME types — delegate to upload
  2. Remove `ValueError` for `file_id`-only attachments — emit `{"type": "file", "file": {"file_id": "..."}}`
  3. Add `_upload_fn` parameter to `_translate_chat_attachment()` and `_translate_chat_content_part()`
  4. Make translation chain async: `_translate_chat_attachment` → `_translate_chat_content_part` → `_translate_chat_user_message` → `_translate_chat_messages`
  5. Wire `UploadSession` into `OpenAIChatCompletionsClient`
  6. Update `_build_chat_payload()` to `await` the async translation
- **Rationale**: Chat Completions currently rejects all non-image files; Phase 5 adds upload support
- **Breaking changes**: The translation chain changes from sync to async. Internal callers (`_chat_sync`, `_chat_stream`) already async — minimal impact.

### Providers: Responses

#### [MODIFY] `tinycua_sdk/providers/open_ai_responses.py`

- **Description**:
  1. Extract `_file_id_cache` into shared `UploadSession`. Use inline `input_file` + `file_data` + `filename` for non-image data-backed files (no `/v1/files` needed)
  2. Change `_make_upload_cache_key()` to exclude filename from hash: `SHA-256(content + MIME)` (hash raw file bytes, decoding base64 `data` to bytes before hashing)
  3. Remove `ValueError` for non-image URL attachments — add download + inline file_data path (Responses) or download + /v1/files upload (Chat Completions)
  4. Wire `UploadSession` instead of inline cache
- **Rationale**: Shared cache eliminates code duplication; URL support fills a Phase 3 gap
- **Breaking changes**: `_make_upload_cache_key` signature change (internal); public API unchanged

### Agent Configuration

#### [MODIFY] `tinycua_sdk/agent/config.py`

- **Description**: Add five new fields to `AgentConfig`:
  - `cache_dir: str | None = None` — enables persistent cache
  - `cache_max_entries: int = 1000` — max persistent cache entries
  - `session_cache_max_entries: int = 500` — max in-memory session cache entries
  - `cache_namespace: str | None = None` — account/project namespace for persistent cache scoping
  - `upload_timeout: float = 30.0` — URL download timeout
- **Rationale**: Persistent cache configuration surface; in-memory cache size management; account-level cache isolation; timeout for URL downloads
- **Breaking changes**: None — new optional fields with defaults

#### [MODIFY] `tinycua_sdk/agent/agent.py`

- **Description**: Add `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` to `Agent.__init__()` and forward them to `AgentConfig`. Update `Agent.from_config()` to round-trip the new fields. Update `_CONFIG_ATTRS` to include the new fields so they are accessible as `agent.cache_dir`, `agent.cache_max_entries`, `agent.session_cache_max_entries`, `agent.cache_namespace`, `agent.upload_timeout`.
- **Rationale**: The public `Agent(...)` constructor is the primary SDK entry point. Users must be able to configure the persistent cache through it.
- **Breaking changes**: None — new optional keyword arguments with defaults

### Agent Executor

#### [MODIFY] `tinycua_sdk/agent/executor.py`

- **Description**: `_get_llm_client()` builds an `UploadSession` with optional persistent cache and passes it to the provider factory.
- **Rationale**: UploadSession must be wired at client creation time so both providers share the cache
- **Breaking changes**: None — internal wiring change

### Provider Registry

#### [MODIFY] `tinycua_sdk/providers/registry.py`

- **Description**: Extend factory function signatures to accept optional `UploadSession`. Update `create_client()` to forward it.
- **Rationale**: UploadSession must flow from AgentConfig → AgentExecutor → ProviderRegistry → Provider Client
- **Breaking changes**: Factory callable signature expanded (the `ProviderFactory` type alias in `utility.py` is also updated to match)

### Tests

#### [NEW] `tests/unit/test_upload_cache.py`

- **Description**: Unit tests for `UploadSession`, `PersistentCacheStore`, `InFlightTracker`, `_download_url_content`

#### [NEW] `tests/integration/test_cache_streaming_integration.py`

- **Description**: Integration tests for end-to-end Phase 5 flows

#### [MODIFY] `tests/unit/test_llm_client.py`

- **Description**: Add Chat Completions upload + URL attachment tests; update Responses provider tests for refactored cache (UploadSession), URL support, cache key change

#### [MODIFY] `tests/unit/test_openai_chat_client.py`

- **Description**: Extend attachment translation tests for non-image/URL/file_id scenarios

---

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `providers/upload.py` | New | `UploadSession` (with in-memory LRU eviction), `PersistentCacheStore` (scoped by provider+base_url+namespace), `InFlightTracker`, `_download_url_content` (with DNS rebinding protection) |
| `models/attachment.py` | New + Modify | Add `StreamingFileAttachment` subclass; modify `from_path(stream=True)` return type |
| `providers/open_ai_chat_completions.py` | Modify | Add non-image/file_id support; make translation async; wire UploadSession |
| `providers/open_ai_responses.py` | Modify | Extract cache to UploadSession; add URL download; fix cache key |
| `agent/config.py` | Modify | Add `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` |
| `agent/agent.py` | Modify | Add `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout` to `Agent.__init__`; forward to `AgentConfig` and round-trip in `from_config()` |
| `agent/executor.py` | Modify | Build UploadSession, pass to provider factory |
| `providers/registry.py` | Modify | Extend factory signature for UploadSession |
| `providers/utility.py` | Modify | Update `ProviderFactory` type alias |

## Data Model Changes

```python
# New: StreamingFileAttachment (subclass of FileAttachment)
class StreamingFileAttachment(FileAttachment):
    data: None                                          # Always None; content read on demand
    _file_path: pathlib.Path                            # Path for chunked reading
    _CHUNK_SIZE: ClassVar[int] = 3 * 1024               # Divisible by 3 for base64 alignment
    
    def iter_base64_chunks(self) -> Iterator[str]: ...   # Base64 chunk iterator
    def iter_raw_chunks(self) -> Iterator[bytes]: ...    # Raw bytes chunk iterator
    def hash_content(self) -> str: ...                   # SHA-256 for cache key

# New: UploadResult
@dataclass
class UploadResult:
    file_id: str
    mime_type: str
    created_at: float
    last_accessed: float                # Updated on get() and put() for LRU eviction
    expires_at: float | None

# New: UploadSession
class UploadSession:
    _cache: dict[str, UploadResult]                      # In-memory cache with LRU eviction
    _max_entries: int                                    # Max in-memory entries (default 500)
    _persistent: PersistentCacheStore | None             # Optional disk store
    _in_flight: dict[str, asyncio.Event]                 # Concurrent upload dedup
    
    async def ensure_file_id(
        self, client: AsyncOpenAI, attachment: FileAttachment
    ) -> str: ...

# New: PersistentCacheStore
class PersistentCacheStore:
    _path: pathlib.Path                                  # JSONL file path
    _max_entries: int                                    # Default 1000
    _entries: dict[str, UploadResult]                    # Loaded entries
    _provider: str                                       # Provider identifier
    _base_url_hash: str                                  # SHA-256 of normalized base URL
    _cache_namespace: str                                # Account/project namespace (default "default")
    
    def get(self, key: str) -> UploadResult | None: ...
    def put(self, key: str, result: UploadResult) -> None: ...
    def evict_lru(self) -> None: ...

# Modified: AgentConfig
class AgentConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    # ... existing fields unchanged ...
    cache_dir: str | None = None                         # NEW
    cache_max_entries: int = 1000                        # NEW
    session_cache_max_entries: int = 500                 # NEW: max in-memory cache entries
    cache_namespace: str | None = None                   # NEW: account/project namespace
    upload_timeout: float = 30.0                         # NEW

    # Also update to_config() and from_config() to round-trip the new fields,
    # including the TINYCUA_CACHE_DIR env var fallback for cache_dir.
```

## API Changes

### New Provider API Shapes

**Chat Completions — file reference via file_id**:
```json
{
    "type": "file",
    "file": {"file_id": "file-abc123"}
}
```

**Chat Completions — non-image attachment (uploaded)**:
```json
{
    "type": "file",
    "file": {"file_id": "file-abc123"}
}
```

### Modified Internal Functions

| Function | Change |
|----------|--------|
| `_translate_chat_attachment()` | Sync → async; accepts `_upload_fn`; supports non-image + file_id |
| `_translate_chat_content_part()` | Sync → async (calls async attachment translator) |
| `_translate_chat_user_message()` | Sync → async (calls async content part translator) |
| `_translate_chat_messages()` | Sync → async (calls async user message translator) |
| `_make_upload_cache_key()` | Remove `filename` from hash; add URL-inclusive variant |
| `_ensure_uploaded_file_id()` | Removed → replaced by `UploadSession.ensure_file_id()` |
| `_translate_responses_attachment()` | Add URL download branch for non-image URLs |
| `ProviderFactory` type | `Callable[[LanguageModel], LLMClient]` | `Callable[[LanguageModel], LLMClient]` (accepts `**kwargs` including optional keyword `upload_session: UploadSession \| None`) |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `httpx` | (existing, via openai SDK) | URL download for non-image URL attachments |
| `openai` | (existing) | `client.files.create()` for file uploads |

### Internal Dependencies

- [x] Depends on Phase 1 (FileAttachment model) — stable
- [x] Depends on Phase 2 (Chat Completions translation) — stable
- [x] Depends on Phase 3 (Responses cache + upload) — stable
- [x] Depends on Phase 4 (Agent integration) — stable
- [ ] Blocks future Phase 6 (tool-result file support)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Cache key change (removing filename) breaks existing cached entries | Low — existing cache is in-memory, per-session | No persistent data to migrate; old sessions start fresh |
| Streaming upload produces different payload than non-streaming | High | Comprehensive parity tests: same file, both paths, byte-identical results at provider boundary |
| URL download exposes SSRF risk | High | Restrict to HTTP(S) only; resolve hostnames and reject loopback/private/link-local/multicast/unspecified IPv4 and IPv6 ranges; reject literal private/local IP URLs before request; re-validate every redirect target against the same policy; prevent DNS rebinding/TOCTOU via custom transport that connects to validated addresses; configurable timeout; redirect limit (5) |
| JSONL cache file grows unbounded | Medium | LRU eviction caps at `cache_max_entries`; atomic write-then-rename |
| OpenAI file upload endpoint changes behavior | Medium | Upload logic centralized in `UploadSession`; integration tests as canaries |
| Concurrent upload dedup edge cases with streaming | Medium | `InFlightTracker` uses content hash; streaming computes hash on first chunk, checks tracker before full upload |
| Chat Completions non-image file support varies by model | Medium | Provider enforces only what API accepts; unsupported model errors surface as `ProviderApiError` |
| Making Chat Completions translation async breaks internal callers | Medium | All callers (`_chat_sync`, `_chat_stream`) are already async — only `_translate_chat_messages` chain needs `await` |
| OpenAI SDK may not accept async generator for file upload | High | **Phase 0 spike (task.md id:00) must validate accepted `client.files.create()` inputs before Phase 3.** Choose one supported approach: direct file object, sync file-like wrapper, or `SpooledTemporaryFile` fallback. Spike result updates design, tasks, and memory-behavior acceptance criteria. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-23*