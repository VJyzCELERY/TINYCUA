# Streaming File Uploads

**Prerequisites**: [File Attachments](../core-concepts/file-attachments.md) —
you know how to attach files to agent queries.

## Overview

`FileAttachment.from_path()` with `stream=False` (the default) reads the entire
file into memory and base64-encodes it. That works for images and small
documents but breaks down with multi-GB files. `StreamingFileAttachment` solves
this by reading files in chunks on demand, never loading more than a few KiB
into RAM at once.

This page covers creating streaming attachments, iterating over base64 and raw
byte chunks, computing integrity hashes without full buffering, and knowing
when to choose streaming over memory-backed uploads.

## Creating a Streaming Attachment

Pass `stream=True` to `FileAttachment.from_path()`:

```python
from tinycua_sdk import FileAttachment, StreamingFileAttachment

attachment = FileAttachment.from_path("large_report.pdf", stream=True)

print(type(attachment))       # <class 'StreamingFileAttachment'>
print(attachment.data)        # None — no in-memory content
print(attachment.mime_type)   # application/pdf
print(attachment.filename)    # large_report.pdf
print(attachment.file_path)   # /absolute/path/to/large_report.pdf
```

A `StreamingFileAttachment` is a subclass of `FileAttachment`. The key
difference: `data` is always `None` — no bytes are ever loaded into a single
buffer. The file path is resolved to an absolute path at construction time so
later changes to the working directory don't affect reads.

You can also construct one directly for advanced use:

```python
from tinycua_sdk import StreamingFileAttachment

attachment = StreamingFileAttachment(
    data=None,
    mime_type="video/mp4",
    filename="demo.mp4",
)
```

However, you must set `_file_path` yourself if constructed this way.
`FileAttachment.from_path(stream=True)` is the recommended path.

## Reading Chunks

Once you have a streaming attachment, iterate over its content in one of two
forms:

### Base64 Chunks

Each chunk is independently base64-encoded. Concatenating all chunks produces
the same result as encoding the full file at once:

```python
from tinycua_sdk import FileAttachment

attachment = FileAttachment.from_path("report.csv", stream=True)

encoded_parts: list[str] = []
for chunk in attachment.iter_base64_chunks():
    encoded_parts.append(chunk)

# The concatenation of all chunks equals the full base64 encoding
full_encoded = "".join(encoded_parts)
```

This is the method providers use internally when sending file content to an API
that requires base64 input.

### Raw Bytes

For direct uploads to APIs that accept binary (e.g., `client.files.create()`),
use raw chunks:

```python
from tinycua_sdk import FileAttachment

attachment = FileAttachment.from_path("backup.tar.gz", stream=True)

total_bytes = 0
for chunk in attachment.iter_raw_chunks():
    total_bytes += len(chunk)

print(f"Total bytes read: {total_bytes}")
```

Each chunk is at most `_CHUNK_SIZE` (3,072 bytes), chosen to be divisible by 3
for clean base64 alignment.

## Integrity Verification with `hash_content()`

Compute a SHA-256 digest of the full file without ever loading it entirely into
memory. The method reads the file in chunks and streams through a `hashlib`
accumulator:

```python
from tinycua_sdk import FileAttachment

attachment = FileAttachment.from_path("dataset.zip", stream=True)

file_hash = attachment.hash_content()
print(file_hash)  # e.g. a3b2c1d4e5f6789...

# Verify it matches a known hash
expected = "a3b2c1d4e5f6789012345678901234567890123456789012345678901234"
if file_hash == expected:
    print("Integrity verified")
```

This is particularly useful when the upload cache uses content-addressed
deduplication (see [Upload Cache and Persistence](./upload-cache-and-persistence.md)).

## When to Use Streaming vs. Memory-Backed

| Scenario | Use |
|----------|-----|
| Small images (< 10 MB) | `FileAttachment.from_path(path)` — simple, fast |
| Large documents (10 MB – 500 MB) | `FileAttachment.from_path(path, stream=True)` |
| Multi-GB files (video, archives) | `FileAttachment.from_path(path, stream=True)` — mandatory |
| URL-referenced files | `FileAttachment.from_url(url, mime_type)` — no download until needed |
| Byte buffers already in memory | `FileAttachment.from_bytes(data, mime_type)` |

## Local and Remote Patterns

Streaming attachments work identically regardless of provider. The attachment
object is provider-agnostic — the SDK's internal upload layer handles chunked
reading when it's time to send data to the API.

Local (LM Studio) — construction only:

```python
import os

from tinycua_sdk import Agent, FileAttachment, LanguageModel

attachment = FileAttachment.from_path("large_document.pdf", stream=True)

model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

agent = Agent(
    name="file-reader",
    instructions="You read and summarize attached files.",
    llm_model=model,
)
```

Remote (OpenAI) — construction only:

```python
import os

from tinycua_sdk import Agent, FileAttachment, LanguageModel

attachment = FileAttachment.from_path("large_document.pdf", stream=True)

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="file-reader",
    instructions="You read and summarize attached files.",
    llm_model=model,
)
```

## Common Pitfalls

**Accessing `.data` on a streaming attachment**. `StreamingFileAttachment.data`
is always `None`. If your code reads `.data` directly, it breaks for streaming
attachments. Always use `iter_base64_chunks()` or `iter_raw_chunks()` instead,
or check `isinstance(attachment, StreamingFileAttachment)` before reading
`.data`.

**Re-iterating chunks after exhaustion**. Both `iter_raw_chunks()` and
`iter_base64_chunks()` are generators backed by file I/O. Once exhausted, you
must recreate the attachment to re-read. Cache the hash via `hash_content()` if
you need deterministic identification across reads.

**Forgetting `stream=True` on large files**. Calling
`FileAttachment.from_path("8gb_video.mp4")` without `stream=True` reads the
entire file into RAM. Your process will likely OOM. Always use `stream=True`
for multi-GB files.

## Next Steps

- **[Upload Cache and Persistence](./upload-cache-and-persistence.md)** —
  Cache uploaded file references across sessions with content-addressed
  deduplication.
- **[Tool Results with Files](./tool-results-with-files.md)** — Return file
  attachments from tool calls.
