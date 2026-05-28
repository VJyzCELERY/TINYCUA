"""Integration tests for SDK file attachment content models."""

import base64

import pytest
from pydantic import ValidationError

from tinycua_sdk.agent.events import ToolResultMessage, UserMessage
from tinycua_sdk.models import ContentPart, FileAttachment


def test_file_attachment_from_path_flows_into_user_message(tmp_path):
    """A local image attachment can be embedded in a canonical user message."""
    image_path = tmp_path / "photo.jpg"
    image_bytes = b"\xff\xd8\xff\xe0tinycua\xff\xd9"
    image_path.write_bytes(image_bytes)

    attachment = FileAttachment.from_path(image_path)
    content = [
        ContentPart(type="text", text="What is in this image?"),
        ContentPart(type="file", file=attachment),
    ]
    message: UserMessage = {"role": "user", "content": content}

    assert attachment.data == base64.b64encode(image_bytes).decode("ascii")
    assert attachment.mime_type == "image/jpeg"
    assert attachment.filename == "photo.jpg"
    assert message["content"][1].file == attachment


def test_file_attachment_from_bytes_and_url_round_trip_serialization():
    """Bytes and URL helpers produce serializable attachment content parts."""
    byte_attachment = FileAttachment.from_bytes(
        b"hello", mime_type="text/plain", filename="hello.txt"
    )
    url_attachment = FileAttachment.from_url(
        "https://example.com/report.pdf",
        mime_type="application/pdf",
        filename="report.pdf",
    )

    _ = ContentPart(type="file", file=byte_attachment)  # validates FileAttachment in ContentPart
    url_part = ContentPart.model_validate(
        ContentPart(type="file", file=url_attachment).model_dump()
    )

    assert byte_attachment.data == base64.b64encode(b"hello").decode("ascii")
    assert url_part.file is not None
    assert url_part.file.url == "https://example.com/report.pdf"
    assert url_part.file.data is None


def test_tool_result_message_accepts_file_content_parts():
    """Tool results can carry generated file attachments back to the loop."""
    attachment = FileAttachment.from_bytes(
        b"generated", mime_type="application/octet-stream", filename="artifact.bin"
    )
    message: ToolResultMessage = {
        "role": "tool_result",
        "call_id": "call_123",
        "content": [ContentPart(type="file", file=attachment)],
    }

    assert message["content"][0].file.filename == "artifact.bin"


def test_invalid_content_part_and_empty_attachment_are_rejected():
    """Pydantic validation enforces attachment and content-part invariants."""
    with pytest.raises(ValidationError):
        FileAttachment(mime_type="image/png")

    with pytest.raises(ValidationError):
        FileAttachment(
            mime_type="image/png",
            data="base64data",
            url="https://example.com/img.png",
        )

    with pytest.raises(ValidationError):
        ContentPart(type="text")

    with pytest.raises(ValidationError):
        ContentPart(
            type="file",
            text="not allowed for file parts",
            file=FileAttachment.from_url("https://example.com/a.png", "image/png"),
        )


def test_from_path_streaming_matches_non_streaming_output(tmp_path):
    """stream=True uses chunked reading while returning identical base64 data."""
    data_path = tmp_path / "payload.bin"
    payload = (b"0123456789abcdef" * 1024) + b"tail"
    data_path.write_bytes(payload)

    regular = FileAttachment.from_path(data_path, mime_type="application/octet-stream")
    streamed = FileAttachment.from_path(
        data_path, mime_type="application/octet-stream", stream=True
    )

    # StreamingFileAttachment.data is always None by design —
    # use iter_base64_chunks() to get the content.
    assert streamed.data is None
    assert "".join(streamed.iter_base64_chunks()) == regular.data
    assert "".join(streamed.iter_base64_chunks()) == base64.b64encode(payload).decode("ascii")


def test_user_message_string_with_separate_attachments():
    """UserMessage accepts content: str plus an attachments list."""
    attachment = FileAttachment.from_url(
        "https://example.com/file.pdf",
        mime_type="application/pdf",
        filename="file.pdf",
    )
    message: UserMessage = {
        "role": "user",
        "content": "Please summarize this",
        "attachments": [attachment],
    }

    assert message["content"] == "Please summarize this"
    assert len(message["attachments"]) == 1
    assert message["attachments"][0].url == "https://example.com/file.pdf"
    assert message["attachments"][0].filename == "file.pdf"


def test_tool_result_message_string_with_separate_attachments():
    """ToolResultMessage accepts content: str plus an attachments list."""
    attachment = FileAttachment.from_bytes(
        b"generated", mime_type="application/octet-stream", filename="output.bin"
    )
    message: ToolResultMessage = {
        "role": "tool_result",
        "call_id": "call_3",
        "content": "Task completed",
        "attachments": [attachment],
    }

    assert message["content"] == "Task completed"
    assert len(message["attachments"]) == 1
    assert message["attachments"][0].filename == "output.bin"
    assert message["attachments"][0].data is not None
