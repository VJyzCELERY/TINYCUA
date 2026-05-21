"""Integration tests for OpenAI Responses file attachment translation."""

import base64
import os

import pytest

from tinycua_sdk.agent.events import UserMessage
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.models.attachment import ContentPart, FileAttachment
from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set; skipping Responses integration tests",
)


@pytest.mark.asyncio
async def test_responses_image_attachment_returns_non_empty_response():
    """Sending an image attachment through the Responses provider yields a
    non-empty assistant response from a vision-capable model."""
    model = LanguageModel(
        model_name=os.getenv("OPENAI_RESPONSES_MODEL", "gpt-4o-mini"),
        provider="openai-responses",
    )
    client = OpenAIResponsesClient(model)
    try:
        attachment = FileAttachment.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            ),
            mime_type="image/png",
            filename="test_image.png",
        )
        messages: list[UserMessage] = [
            {
                "role": "user",
                "content": "Describe this image briefly.",
                "attachments": [attachment],
            },
        ]
        result = await client.chat(messages=messages)
        assert result["content"] is not None
        assert len(result["content"]) > 0
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_responses_content_part_image_returns_non_empty_response():
    """Sending a ContentPart image through the Responses provider yields a
    non-empty assistant response."""
    model = LanguageModel(
        model_name=os.getenv("OPENAI_RESPONSES_MODEL", "gpt-4o-mini"),
        provider="openai-responses",
    )
    client = OpenAIResponsesClient(model)
    try:
        attachment = FileAttachment.from_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            ),
            mime_type="image/png",
            filename="test_image.png",
        )
        parts = [
            ContentPart(type="text", text="What do you see?"),
            ContentPart(type="file", file=attachment),
        ]
        messages: list[UserMessage] = [
            {"role": "user", "content": parts},
        ]
        result = await client.chat(messages=messages)
        assert result["content"] is not None
        assert len(result["content"]) > 0
    finally:
        await client.close()
