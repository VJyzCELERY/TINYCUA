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

#### Supported File/Image Sources

| Source | Image (`image/*`) | Non-image | Notes |
|--------|--------------------|-----------|-------|
| **data** (base64) | `input_image` — inline data URL, `detail="auto"` | `input_file` — auto-uploaded | Non-image data uploads are cached per client session; image data is sent inline and is not uploaded. |
| **url** | `input_image` — URL reference, `detail="auto"` | ❌ Rejected (`ValueError`) | Non-image URL download deferred to Phase 5 |
| **file_id** | `input_image` — file_id, `detail="auto"` | `input_file` — file_id reference | No upload needed |

The image `detail` parameter defaults to `"auto"` for all
image input types, matching the OpenAI Responses API default.
