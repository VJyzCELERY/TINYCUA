# tinycua-sdk

Developer SDK for TINYCUA.

Historical SDK docs and specs have been removed. Replacement cookbook-style docs
will be added separately.

## Quick Start

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
