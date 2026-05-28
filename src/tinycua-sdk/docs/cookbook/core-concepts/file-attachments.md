# File Attachments

**Prerequisites**: [Streaming Responses](./streaming-responses.md)

## Overview

`FileAttachment` lets you send files — images, PDFs, audio, text — alongside your agent queries. The SDK handles base64 encoding, MIME type detection, and provider-specific formatting so the LLM can understand your files.

You can create attachments from local file paths, in-memory byte buffers, or remote URLs. Once created, pass them to `agent.run()` via the `file_attachments` parameter. The SDK auto-detects the best attachment format for your chosen provider.

This page covers all three factory methods, the `file_id` reference pattern, local vs remote provider support, and common mistakes with file handling.

## Creating File Attachments

### From a Local File

`FileAttachment.from_path()` reads a local file and auto-detects its MIME type from the extension:

```python
import os
from tinycua_sdk import LanguageModel, Agent, FileAttachment

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

screenshot = FileAttachment.from_path("path/to/your/screenshot.png")

agent = Agent(
    name="image-analyzer",
    instructions="Describe images in detail.",
    llm_model=model,
)
```

The path is resolved relative to the current working directory. Supported extensions include common image formats (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`), documents (`.pdf`, `.txt`), and more.

### From In-Memory Bytes

`FileAttachment.from_bytes()` creates an attachment from raw bytes in memory. You must provide the `mime_type` and optionally a `filename`:

```python
import os
from tinycua_sdk import LanguageModel, Agent, FileAttachment

model = LanguageModel(
    provider="openai-chat-completions",
    model_name="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

text_data = b"Employee handbook: Section 3 covers vacation policy..."
handbook = FileAttachment.from_bytes(
    text_data,
    mime_type="text/plain",
    filename="handbook.txt",
)

agent = Agent(
    name="document-qa",
    instructions="Answer questions about the provided documents.",
    llm_model=model,
)
```

This is useful when data comes from an API response, database blob, or `BytesIO` buffer — no file system access needed.

### From a Remote URL

`FileAttachment.from_url()` references a file hosted at a public URL. The file is downloaded when the agent processes the query:

```python
import os
from tinycua_sdk import LanguageModel, Agent, FileAttachment

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

remote_image = FileAttachment.from_url(
    "https://example.com/photo.jpg",
    mime_type="image/jpeg",
)

agent = Agent(
    name="remote-file-agent",
    instructions="Analyze the provided files.",
    llm_model=model,
)
```

Use `from_url()` for files already hosted behind a public URL — it avoids the bandwidth of downloading locally first. The `mime_type` parameter is required since the SDK can't inspect remote content.

## Passing Attachments to Agent Queries

The continuation block shows how to pass the attachments constructed above into `agent.run()`:

```python
response = agent.run(
    "What does this screenshot show?",
    file_attachments=[screenshot],
)

response = agent.run(
    "How many vacation days does the handbook specify?",
    file_attachments=[handbook],
)

response = agent.run(
    "Describe the subject of this photo.",
    file_attachments=[remote_image],
)
```

You can attach **multiple files** in a single query:

```python
invoice = FileAttachment.from_path("path/to/your/invoice.pdf")
receipt = FileAttachment.from_path("path/to/your/receipt.png")

response = agent.run(
    "Does the receipt match the invoice amounts?",
    file_attachments=[invoice, receipt],
)
```

## The file_id Reference Pattern

When you upload a file through the Responses API, the provider returns a `file_id`. You can reuse this ID in subsequent queries instead of re-uploading the same file:

```python
import os
from tinycua_sdk import LanguageModel, Agent, FileAttachment

file_ref = FileAttachment(
    mime_type="application/pdf",
    file_id="file-abc123",
)

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="file-reuse-agent",
    instructions="Analyze the provided file.",
    llm_model=model,
)
```

```python
response = agent.run(
    "Tell me about this file again.",
    file_attachments=[file_ref],
)
```

Set only `file_id` (leave `data`, `url`, and `filename` empty) to reuse a previously uploaded file. This avoids redundant uploads and reduces latency.

## Local vs Remote Provider Support

| Feature | openai-responses | openai-chat-completions | openai-compatible |
|---|---|---|---|
| Image files (PNG, JPEG, etc.) | Yes | Yes | Depends on local model |
| PDF documents | Yes | No | Depends on local model |
| Audio files | Yes | Limited | Depends on local model |
| File ID reuse | Yes | No | No |
| Multiple files per query | Yes | Limited | Depends on local model |

When targeting `openai-compatible` providers, file attachment support depends entirely on the local model running on your server. Vision-capable models like LLaVA or Llama 3.2 Vision support images; text-only models will ignore file attachments or return errors.

## Common Pitfalls

1. **Using unsupported MIME types** — Each provider accepts a specific set of MIME types. Sending a PDF to `openai-chat-completions` or an unsupported format to a local model will raise a `ProviderApiError`. Check your provider's documentation for supported file formats.

2. **File too large for `from_path()`** — `from_path()` reads the entire file into memory. For large files, use `from_path(path, stream=True)` to get a `StreamingFileAttachment` that uploads in chunks. See [Streaming File Uploads](../advanced-file-handling/streaming-file-uploads.md) for details.

3. **Forgetting `file_attachments` when calling `run()`** — Creating a `FileAttachment` is not enough; you must pass it to `agent.run()` via the `file_attachments=[...]` parameter. A standalone `FileAttachment` object does nothing on its own.

## Next Steps

Learn how to build **multimodal queries** that mix text prompts with images and files in [Multimodal Content](./multimodal-content.md).
