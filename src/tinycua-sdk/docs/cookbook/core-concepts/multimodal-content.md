# Multimodal Content

**Prerequisites**: [File Attachments](./file-attachments.md)

## Overview

Multimodal content lets you send a mix of text and files as a single agent query. Instead of a plain string prompt, you pass a list of `ContentPart` objects — each one is either a text message or a file attachment.

`ContentPart` gives you fine-grained control over how text and files are interleaved. You can show a series of screenshots with instructions between each one, or ask the model to compare two images positioned at specific points in the prompt.

This page covers building `ContentPart` lists, mixing text and images, provider-level behavior differences, and patterns for both local and remote models.

## ContentPart Types

A `ContentPart` is a union type — it is either text or a file:

```python
import os
from tinycua_sdk import LanguageModel, Agent, ContentPart, FileAttachment

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

text_part = ContentPart(type="text", text="Describe this image in detail.")
image_part = ContentPart(
    type="file",
    file=FileAttachment.from_path("path/to/your/photo.jpg"),
)

agent = Agent(
    name="multimodal-agent",
    instructions="You analyze visual and textual content.",
    llm_model=model,
)
```

The `type` field must be `"text"` or `"file"`. Each part is independent and you control the order they appear in the list.

## Building Multimodal Queries

Pass a `list[ContentPart]` as the `query` argument to `agent.run()`. Here's a simple example followed by a multi-image comparison:

```python
import os
from tinycua_sdk import LanguageModel, Agent, ContentPart, FileAttachment

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

parts = [
    ContentPart(
        type="text",
        text="Compare the two UI mockups below. Which design is cleaner?",
    ),
    ContentPart(type="text", text="Mockup A:"),
    ContentPart(
        type="file",
        file=FileAttachment.from_path("path/to/your/mockup-a.png"),
    ),
    ContentPart(type="text", text="Mockup B:"),
    ContentPart(
        type="file",
        file=FileAttachment.from_path("path/to/your/mockup-b.png"),
    ),
]

agent = Agent(
    name="design-reviewer",
    instructions="You are a UI design critic. Compare designs and give clear feedback.",
    llm_model=model,
)
```

```python
import asyncio

response = asyncio.run(agent.run(parts))
```

Text and file parts can appear in any order. The model processes them sequentially and treats each file relative to the text that precedes it.

`from_bytes` works identically in `ContentPart` lists — useful when file data comes from an API response or database:

```python
image_bytes = open("path/to/your/logo.png", "rb").read()

byte_parts = [
    ContentPart(type="text", text="Describe this logo's design elements."),
    ContentPart(
        type="file",
        file=FileAttachment.from_bytes(
            image_bytes,
            mime_type="image/png",
            filename="logo.png",
        ),
    ),
]
```

## Local Provider Pattern

For a local LLM server, switch to `"openai-compatible"` and supply a `base_url`. Vision-capable local models like LLaVA or Llama 3.2 Vision accept images:

```python
import os
from tinycua_sdk import LanguageModel, Agent, ContentPart, FileAttachment

local_model = LanguageModel(
    provider="openai-compatible",
    model_name="llava-v1.6-34b",
    base_url="http://localhost:1234/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

parts = [
    ContentPart(type="text", text="What objects do you see in this image?"),
    ContentPart(
        type="file",
        file=FileAttachment.from_path("path/to/your/room.jpg"),
    ),
]

agent = Agent(
    name="local-vision-agent",
    instructions="You identify objects and scenes in images.",
    llm_model=local_model,
)
```

```python
import asyncio

response = asyncio.run(agent.run(parts))
```

If your local model does not support vision, file parts are silently ignored or cause a provider error, depending on the model server.

## Provider Behavior Differences

`ContentPart` is translated into the provider's native format internally. The behavior differs by provider:

### openai-responses

- Text parts map to `input_text` objects; file parts map to `input_file` objects with base64 `file_data`
- Files appear inline with text in the `input` array exactly as ordered
- Supports arbitrary interleaving of text and files; supports all file types

### openai-chat-completions

- Text parts become text-type `content` entries; image file parts become `image_url` entries with base64 data URIs
- Non-image files are **not supported** and will raise a `ProviderApiError`
- All content entries are grouped into a single user message

### openai-compatible

- Behaves similarly to `openai-chat-completions` for format translation
- File support depends entirely on the model running locally — test your specific model and server combination

## Query-as-String vs Query-as-Parts

You can use `file_attachments` with a string query **or** `ContentPart` lists. The two approaches are equivalent for simple queries:

```python
import asyncio

# Approach 1: file_attachments parameter
response = asyncio.run(agent.run(
    "Describe this image.",
    file_attachments=[FileAttachment.from_path("path/to/your/image.png")],
))

# Approach 2: ContentPart list
parts = [
    ContentPart(type="text", text="Describe this image."),
    ContentPart(
        type="file",
        file=FileAttachment.from_path("path/to/your/image.png"),
    ),
]
response = asyncio.run(agent.run(parts))
```

Use `file_attachments` for simple "one prompt + files" queries. Use `ContentPart` lists when interleaving explanatory text between multiple files.

## Common Pitfalls

1. **Missing `type` in ContentPart constructor** — Always include `type="text"` or `type="file"`. Omitting it results in a `ValueError`. The `type` field discriminates between the two part kinds.

2. **Using ContentPart with unsupported file types** — When using `openai-chat-completions`, only image MIME types work as file parts. Audio, video, and document files will raise errors. Use `openai-responses` for broader file format support.

3. **Assuming all local models support multimodality** — `openai-compatible` with a text-only local model will fail or silently ignore file parts. Verify your model's capabilities before building multimodal features on local providers.

## Next Steps

Learn how to **create custom tools** that your agent can call in [Creating Tools](../agent-extensions/creating-tools.md).