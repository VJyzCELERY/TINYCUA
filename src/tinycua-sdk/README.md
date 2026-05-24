# tinycua-sdk

Developer SDK for TINYCUA.

Historical SDK docs and specs have been removed. Replacement cookbook-style docs
will be added separately.

## Quick Start

### Agent Convenience API — File Attachments

The `Agent.run()` method accepts file attachments via the optional
`file_attachments` parameter and supports multimodal `ContentPart` queries.
`FileAttachment` and `ContentPart` are importable from the top-level
`tinycua_sdk` namespace.

```python
from tinycua_sdk import Agent, FileAttachment, ContentPart

agent = Agent(
    name="vision-assistant",
    instructions="You are a helpful assistant.",
)

# Attach a file to a text query
attachment = FileAttachment.from_path("screenshot.png")
response = await agent.run(
    "Describe this image in detail.",
    file_attachments=[attachment],
)

# Use ContentPart for explicit multimodal input
parts = [
    ContentPart(type="text", text="Compare these photos:"),
    ContentPart(
        type="file",
        file=FileAttachment.from_path("photo1.jpg"),
    ),
    ContentPart(
        type="file",
        file=FileAttachment.from_path("photo2.jpg"),
    ),
]
response = await agent.run(parts)

# Streaming is also supported
stream = await agent.run(
    "Describe this",
    file_attachments=[attachment],
    stream=True,
)
async for event in stream:
    print(event)
```

Message shapes produced internally:
- `str` query + attachments → `{"role": "user", "content": str, "attachments": [FileAttachment]}`  
- `list[ContentPart]` query → `{"role": "user", "content": [ContentPart]}`  
- `list[ContentPart]` query + attachments → merged `{"role": "user", "content": merged_parts}`

### OpenAI Responses Provider — File & Image Attachments

The `openai-responses` provider supports canonical `FileAttachment` objects
via two input shapes:

#### 1. String content + attachments list

```python
from tinycua_sdk.models.attachment import FileAttachment
from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient

attachment = FileAttachment(
    data="iVBORw0KGgo...",  # base64-encoded image bytes
    mime_type="image/png",
    filename="screenshot.png",
)

msg = {
    "role": "user",
    "content": "What do you see in this image?",
    "attachments": [attachment],
}
```

#### 2. ContentPart list

```python
from tinycua_sdk.models.attachment import ContentPart, FileAttachment

parts = [
    ContentPart(type="text", text="Analyze these files:"),
    ContentPart(
        type="file",
        file=FileAttachment(
            file_id="file-abc123",
            mime_type="application/pdf",
        ),
    ),
    ContentPart(
        type="file",
        file=FileAttachment(
            url="https://example.com/photo.jpg",
            mime_type="image/jpeg",
        ),
    ),
]

msg = {"role": "user", "content": parts}
```

#### Supported File/Image Sources (OpenAI Responses Provider)

| Source | Image (`image/*`) | Non-image | Notes |
|--------|--------------------|-----------|-------|
| **data** (base64) | `input_image` — inline data URL, `detail="auto"` | `input_file` — inline `file_data` | Non-image data is sent inline via base64 `file_data` (no upload). Chat Completions uploads non-image data to `/v1/files`. |
| **url** | `input_image` — URL reference, `detail="auto"` | `input_file` — inline `file_data` | Non-image URL content is downloaded and sent inline via `file_data` (no upload). Full SSRF protection. |
| **file_id** | `input_image` — file_id, `detail="auto"` | `input_file` — file_id reference | No upload needed. |
| **local path** (streaming) | — | Uploaded via `/v1/files` | `StreamingFileAttachment` reads files in chunks with no full-file buffering. |

The image `detail` parameter defaults to `"auto"` for all
image input types, matching the OpenAI Responses API default.

### Phase 5 — File ID Cache, Streaming Upload, Non-Image URL Support

#### StreamingFileAttachment

For large files, use `FileAttachment.from_path(path, stream=True)` to create a
`StreamingFileAttachment` that reads content on demand in chunks without loading
the entire file into memory:

```python
from tinycua_sdk.models.attachment import FileAttachment, StreamingFileAttachment

# Streaming attachment (no full-file buffering)
attachment = FileAttachment.from_path("large_video.mp4", stream=True)
assert isinstance(attachment, StreamingFileAttachment)

# Iterate over base64-encoded chunks
for chunk in attachment.iter_base64_chunks():
    print(len(chunk))

# Compute SHA-256 without loading the full file
content_hash = attachment.hash_content()
```

#### Persistent Upload Cache

The `Agent` (or `UploadSession`) supports a disk-backed persistent cache that
survives process restarts. Configure it via `AgentConfig`:

```python
from tinycua_sdk import Agent
from tinycua_sdk.agent.llm_model import LanguageModel

agent = Agent(
    name="file-assistant",
    instructions="You are a helpful assistant.",
    llm_model=LanguageModel(model="qwen/qwen-9b"),
    cache_dir="./cache",                # Root directory for persistent cache
    cache_namespace="my-app",           # Isolate cache between accounts/projects
    cache_max_entries=1000,             # Max persistent cache entries
    session_cache_max_entries=500,      # Max in-memory entries (per session)
    upload_timeout=30.0,                # Timeout for URL downloads (seconds)
)
```

The persistent cache is content-addressed (SHA-256 of file content + MIME type),
scoped by provider, base URL, and namespace. Entries are written durably to
`{cache_dir}/{provider}/{base_url_hash}/{namespace}/cache.jsonl`.

#### Non-Image URL Attachments

Non-image URL attachments are now fully supported. Content is downloaded with
SSRF protection (DNS rebinding prevention, IP pinning, redirect re-validation,
blocked private/loopback networks) and sent inline via `file_data`:

```python
from tinycua_sdk.models.attachment import FileAttachment

url_attachment = FileAttachment(
    url="https://example.com/document.pdf",
    mime_type="application/pdf",
    filename="document.pdf",
)
```

#### Provider Behavior Split

- **Chat Completions (`openai-chat-completions`)**: Non-image files and URLs
  are uploaded to `/v1/files` and referenced as `{"type": "file", "file": {"file_id": ...}}` content parts.
- **Responses (`openai-responses`)**: Non-image data and URL content are sent
  inline via `file_data` without uploading to `/v1/files`, enabling local
  servers (LM Studio, Ollama) that lack a files endpoint.
