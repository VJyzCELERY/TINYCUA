# Upload Cache and Persistence

**Prerequisites**: [Streaming File Uploads](./streaming-file-uploads.md) —
you understand streaming vs. memory-backed attachments.

## Overview

Every time an agent sends a file to a provider API, the SDK uploads it and
receives a `file_id` in return. Without caching, the same file uploaded twice
results in two uploads (and two storage charges). The SDK's upload cache solves
this with a two-tier system: an **in-memory session cache** for fast lookups
and an optional **persistent disk cache** that survives process restarts.

On top of caching, the SDK uses an `InFlightTracker` to deduplicate *concurrent*
uploads — if two tasks try to upload the same file at the same time, only one
upload happens and both tasks receive the same result.

## Configuring the Cache

Pass cache parameters to `Agent` at construction:

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="cache-aware-agent",
    instructions="You process files efficiently.",
    llm_model=model,
    cache_dir="./.tinycua-cache",   # enable persistent cache
    cache_max_entries=2000,          # max entries on disk
    session_cache_max_entries=500,   # max in-memory entries
    cache_namespace="project-alpha", # isolate per project
    upload_timeout=60.0,             # timeout for URL downloads
)
```

Local (local LLM server) setup:

```python
import os

from tinycua_sdk import Agent, LanguageModel

model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

agent = Agent(
    name="local-cache-agent",
    instructions="You process files efficiently.",
    llm_model=model,
    cache_dir="./.tinycua-cache",
    cache_max_entries=1000,
    cache_namespace="local-dev",
)
```

### Parameter Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `cache_dir` | `None` | Root directory for persistent storage. Set to `None` to disable persistence (in-memory only). Falls back to `TINYCUA_CACHE_DIR` env var. |
| `cache_max_entries` | `1000` | Max entries on disk. When exceeded, least-recently-used entries are evicted. |
| `session_cache_max_entries` | `500` | Max entries in the in-memory LRU cache. Eviction removes from memory but not disk. |
| `cache_namespace` | `None` | Account/project namespace. Isolates caches so two projects don't share entries. Defaults to `"default"`. |
| `upload_timeout` | `30.0` | Timeout in seconds for URL-based file downloads. Must be positive. |

The SDK also reads `TINYCUA_CACHE_DIR` from the environment as a fallback for
`cache_dir`. This is useful in CI or containerized environments:

```bash
export TINYCUA_CACHE_DIR=/var/cache/tinycua
```

## How Content-Addressed Deduplication Works

The cache key is derived from a SHA-256 hash of the file's content combined
with its MIME type. This means:

- **Same file, same path across runs** → cache hit (no re-upload).
- **Same file, different path** → cache hit (content is identical).
- **Different file, same name** → cache miss (content differs).
- **Same file, different MIME type** → cache miss (the MIME influences the key).

No API keys, file paths, or filenames are stored in the cache.

## Cache Layout on Disk

When `cache_dir` is set, the persistent store creates a directory hierarchy:

```
{cache_dir}/
└── {provider}/
    └── {base_url_hash}/
        └── {namespace}/
            └── cache.jsonl
```

For example:

```
./.tinycua-cache/
└── openai-responses/
    └── a3b2c1d4e5f6.../
        └── project-alpha/
            └── cache.jsonl
```

- **`provider`** — e.g., `"openai-responses"`, `"openai-chat-completions"`,
  `"openai-compatible"`.
- **`base_url_hash`** — SHA-256 hex of the normalized base URL (trailing
  slash stripped). This isolates caches across different proxy or regional
  endpoints.
- **`namespace`** — the `cache_namespace` value. Defaults to `"default"`.

Each entry in `cache.jsonl` is one JSON object per line, containing the cache
key, `file_id`, MIME type, and access timestamps. The file is written
atomically via a temporary file to prevent corruption.

## Key Internal Classes

### `PersistentCacheStore`

Manages the disk-backed JSONL store. Responsibilities:

- Loads existing entries on construction.
- Writes new entries atomically.
- Evicts least-recently-accessed entries when `cache_max_entries` is exceeded.
- Validates that `provider`, `base_url`, and `namespace` are safe single path
  components (prevents directory traversal).
- Skips entries with mismatched provider fields (a `file_id` from
  `openai-responses` is unusable by `openai-chat-completions`).
- Falls back to in-memory-only on filesystem errors (permission denied, disk
  full).

### `InFlightTracker`

Prevents redundant concurrent uploads using `asyncio.Future`. When two tasks
request the same file simultaneously:

1. The first task begins uploading and stores a `Future`.
2. The second task finds the pending `Future` and `await`s it.
3. Both tasks receive the same `file_id` with only one HTTP upload.

Completed futures are removed from the tracker so that LRU cache evictions and
retries work correctly.

## When to Use Persistent Caching

| Scenario | Recommendation |
|----------|---------------|
| One-off scripts | `cache_dir=None` — memory cache is sufficient |
| Long-running servers | Set `cache_dir` — cache survives restarts |
| Multiple projects sharing an agent binary | Different `cache_namespace` per project |
| CI/CD pipelines | Set `TINYCUA_CACHE_DIR` to a shared volume |
| Sensitive multi-tenant setups | Use a unique `cache_dir` or `cache_namespace` per tenant |

## Disabling Caching Entirely

Set `session_cache_max_entries=0` and leave `cache_dir=None`:

```python
agent = Agent(
    name="no-cache-agent",
    instructions="...",
    llm_model=model,
    session_cache_max_entries=0,  # disable in-memory caching
    # cache_dir=None (default) — no persistence
)
```

With caching disabled, every file upload hits the provider API. This is useful
for testing or when file content changes frequently.

## Common Pitfalls

**Namespace collisions**. If two projects use the same `cache_dir` and
`cache_namespace`, they share cache entries. While sharing *can* improve hit
rates, it also means one project's evictions affect the other. Use distinct
namespaces for isolation.

**Persistent cache is not multi-process safe**. The JSONL store uses
last-writer-wins semantics. If two processes write to the same cache file
concurrently, one process's entries may be lost. Use per-process `cache_dir`
paths or rely on the in-memory session cache for dedup within a process.

**Forgetting to set `cache_dir` for long-lived agents**. Without a persistent
cache, every restart loses all previously uploaded file IDs. For server
processes that handle the same files repeatedly, this adds unnecessary latency
and API cost.

## Next Steps

- **[Tool Results with Files](./tool-results-with-files.md)** — Return file
  attachments from tool calls and understand how providers handle them.
- **[Streaming File Uploads](./streaming-file-uploads.md)** — Upload large
  files without buffering.