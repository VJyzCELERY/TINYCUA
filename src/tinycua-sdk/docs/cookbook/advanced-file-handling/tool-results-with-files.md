# Tool Results with Files

**Prerequisites**: [Creating Tools](../agent-extensions/creating-tools.md) and
[Streaming File Uploads](./streaming-file-uploads.md) — you can define tools
and understand streaming vs. memory-backed attachments.

## Overview

Tools in the TINYCUA SDK can return more than plain strings. When a tool
generates or retrieves file content — an image from a chart library, a PDF
report, a CSV export — it can return a dict with both `content` (the text
summary) and `attachments` (the files). The SDK normalizes these tool results
and passes them to the provider, which may re-inject them into the conversation
as synthetic user messages (Chat Completions) or follow-up user messages
(Responses).

This page covers the three result shapes, how `ContentPart` fits into
structured tool output, provider-specific behavior, and the normalization
rules.

## The Three Return Shapes

### Shape 1: Multipart Content List

Return a dict with `"content"` as a `list[ContentPart]`. This is the most
explicit form and gives full control over ordering and types:

```python
from tinycua_sdk import FileAttachment, ContentPart, tool


@tool
def generate_report(topic: str) -> dict:
    """Generate a report on the given topic.

    Args:
        topic: The report topic.

    """
    text_part = ContentPart(
        type="text",
        text=f"Here is the report on {topic}. Summary in the attachment.",
    )
    file_part = ContentPart(
        type="file",
        file=FileAttachment.from_bytes(
            b"Report: Q1 sales up 12%.\nExpenses flat.",
            mime_type="text/plain",
            filename="report.txt",
        ),
    )
    return {"content": [text_part, file_part]}
```

The agent receives both the text explanation and the attached file.

You can also use `ContentPart` for image results:

```python
from tinycua_sdk import FileAttachment, ContentPart, tool


@tool
def create_chart(chart_type: str) -> dict:
    """Generate a chart image.

    Args:
        chart_type: The type of chart to create.

    """
    # In practice, this would use matplotlib or similar
    image_bytes = b"\x89PNG\r\n\x1a\n..."  # placeholder
    text_part = ContentPart(
        type="text",
        text=f"Generated a {chart_type} chart.",
    )
    image_part = ContentPart(
        type="file",
        file=FileAttachment.from_bytes(
            image_bytes,
            mime_type="image/png",
            filename="chart.png",
        ),
    )
    return {"content": [text_part, image_part]}
```

### Shape 2: String Content with Attachments

Return a dict with a string `"content"` and an `"attachments"` list. This is
simpler when all attachments follow a single text summary:

```python
from tinycua_sdk import FileAttachment, tool


@tool
def export_data(format: str) -> dict:
    """Export data in the requested format.

    Args:
        format: Output format (csv, json, or xml).

    """
    if format == "csv":
        data = b"name,score\nAlice,95\nBob,87"
        mime = "text/csv"
        filename = "export.csv"
    elif format == "json":
        data = b'[{"name":"Alice","score":95}]'
        mime = "application/json"
        filename = "export.json"
    else:
        data = b"<data><item>Alice</item></data>"
        mime = "application/xml"
        filename = "export.xml"

    return {
        "content": f"Data exported as {format}.",
        "attachments": [
            FileAttachment.from_bytes(data, mime_type=mime, filename=filename)
        ],
    }
```

> **Important**: For Shape 2 to be recognized as structured output, the dict
> must either have `"role": "tool_result"` or include `"attachments"`. Without
> either marker, the SDK falls back to `str(tool_result)` (legacy mode).

### Shape 3: Legacy String Return

The simplest form — just return a string. This has always worked and continues
to be the default for text-only tools:

```python
from tinycua_sdk import tool


@tool
def get_status() -> str:
    """Return the system status."""
    return "All systems operational."
```

No structured content, no attachments. The string becomes the `content` field
of the tool result message.

## Tool Result Normalization

When a tool's `invoke()` method returns, the SDK's execution loop passes the
return value through `normalize_tool_result()`. This function applies rules in
priority order:

| Priority | Condition | Action |
|----------|-----------|--------|
| 1 | `dict` with `content: list[ContentPart]` (non-empty) | Preserved as-is. Validated that every item is a `ContentPart` or coercible dict. |
| 2 | `dict` with `content: str` and `"role": "tool_result"` or `"attachments"` present | Content and attachments preserved as structured output. |
| 3 | `dict` with `"role": "tool_result"` (canonical pre-formed) | `call_id` overridden with loop-owned value. |
| 4 | Everything else | Falls back to `str(tool_result)`. |

This means most return values "just work," but understanding the rules helps
you avoid silent data loss when returning structured content.

## Provider Behavior

### Chat Completions (`openai-chat-completions`)

When a tool result includes files or images, the Chat Completions provider
takes the file/image parts and re-injects them as **synthetic user messages**.
Each file becomes a user message with an inline base64 data URL or uploaded
file reference. This works around the Chat Completions API's limitation that
tool results are text-only — the model sees the files as if the user had just
sent them.

Text parts from the tool result are joined and attached to the tool result
message itself.

### Responses (`openai-responses`)

The Responses provider handles structured tool results by appending **follow-up
user messages** after the tool result. File and image `ContentPart` objects
become content blocks in the follow-up user message. Text parts become content
blocks in the same message.

This means the model sees the tool result as two consecutive messages: the
`function_call_output` (text content) and a user message (the files).

### Local Compatible (`openai-compatible`)

Behavior depends on the local server's implementation. Local LLM servers and similar
servers typically follow Chat Completions conventions.

## Complete Example: All Shapes

Here is a single toolset demonstrating all three return shapes:

```python
from tinycua_sdk import FileAttachment, ContentPart, tool


@tool
def text_only(question: str) -> str:
    """Answer a question with text only. (Shape 3)"""
    return f"The answer to '{question}' is 42."


@tool
def text_with_files(format: str) -> dict:
    """Return text plus files. (Shape 2)

    Args:
        format: Output format (csv or json).

    """
    data = b"name,score\nAlice,95\nBob,87"
    return {
        "content": f"Data exported as {format}.",
        "attachments": [
            FileAttachment.from_bytes(
                data, mime_type="text/csv", filename="export.csv"
            )
        ],
    }


@tool
def multipart_report(topic: str) -> dict:
    """Return a structured multipart report. (Shape 1)

    Args:
        topic: The report topic.

    """
    return {
        "content": [
            ContentPart(type="text", text=f"Report on {topic}:"),
            ContentPart(
                type="file",
                file=FileAttachment.from_bytes(
                    b"Chart data here...",
                    mime_type="image/png",
                    filename="chart.png",
                ),
            ),
            ContentPart(type="text", text="End of report."),
        ],
    }
```

## Common Pitfalls

**Forgetting the `"attachments"` key (Shape 2)**. A dict like
`{"content": "Hello", "files": [...]}` without `"attachments"` and without
`"role": "tool_result"` will be stringified via `str()`. The files are lost.
Always use the key `"attachments"`.

**Empty content lists**. A dict with `{"content": []}` raises `ValueError`.
Structured multipart output requires at least one `ContentPart`. If you have no
content to share, return a plain string instead.

**Provider-dependent behavior**. The two providers handle file-bearing tool
results differently (synthetic messages vs. follow-up user messages). This is
transparent to your tool code but may affect token usage and conversation
length. Prefer the Responses provider (`openai-responses`) when tool results
frequently carry files — its native `function_call_output` support maps more
naturally.

## Next Steps

- **[Chat Completions Provider](../provider-deep-dives/chat-completions-provider.md)** —
  Deep dive into how Chat Completions handles tool results and synthetic
  messages.
- **[Responses Provider](../provider-deep-dives/responses-provider.md)** —
  Understand how Responses handles stateful conversations and follow-up user
  messages.
