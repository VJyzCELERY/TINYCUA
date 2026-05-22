"""Integration tests for OpenAI Responses file attachment translation."""

import base64
import os

import pytest

from tinycua_sdk.agent.events import UserMessage
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.models.attachment import ContentPart, FileAttachment
from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("OPENAI_RESPONSES_MODEL") and not os.getenv("LLM_MODEL"),
        reason="Neither OPENAI_RESPONSES_MODEL nor LLM_MODEL set; "
        "skipping Responses integration tests",
    ),
]


@pytest.mark.asyncio
async def test_responses_image_attachment_returns_non_empty_response():
    """Sending an image attachment through the Responses provider yields a
    non-empty assistant response from a vision-capable model."""
    from tests.integration.conftest import resolve_integration_llm_config

    config = resolve_integration_llm_config("openai-responses")
    model = LanguageModel(
        provider="openai-responses",
        model_name=os.getenv("OPENAI_RESPONSES_MODEL", config.model),
        base_url=config.base_url,
        api_key=config.api_key,
    )

    # Also set environment variables so _get_client() works if it
    # resolves lazily (e.g. when base_url is None in a new session)
    old_responses_base = os.environ.get("OPENAI_RESPONSES_BASE_URL")
    old_responses_api_key = os.environ.get("OPENAI_RESPONSES_API_KEY")
    os.environ["OPENAI_RESPONSES_BASE_URL"] = config.base_url
    os.environ["OPENAI_RESPONSES_API_KEY"] = config.api_key

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
        # Restore env vars (in case they were set by a parent fixture)
        _restore_env("OPENAI_RESPONSES_BASE_URL", old_responses_base)
        _restore_env("OPENAI_RESPONSES_API_KEY", old_responses_api_key)


@pytest.mark.asyncio
async def test_responses_content_part_image_returns_non_empty_response():
    """Sending a ContentPart image through the Responses provider yields a
    non-empty assistant response."""
    from tests.integration.conftest import resolve_integration_llm_config

    config = resolve_integration_llm_config("openai-responses")
    model = LanguageModel(
        provider="openai-responses",
        model_name=os.getenv("OPENAI_RESPONSES_MODEL", config.model),
        base_url=config.base_url,
        api_key=config.api_key,
    )

    old_responses_base = os.environ.get("OPENAI_RESPONSES_BASE_URL")
    old_responses_api_key = os.environ.get("OPENAI_RESPONSES_API_KEY")
    os.environ["OPENAI_RESPONSES_BASE_URL"] = config.base_url
    os.environ["OPENAI_RESPONSES_API_KEY"] = config.api_key

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
        _restore_env("OPENAI_RESPONSES_BASE_URL", old_responses_base)
        _restore_env("OPENAI_RESPONSES_API_KEY", old_responses_api_key)


def _restore_env(key: str, old_val: str | None) -> None:
    """Restore an env var to its previous value or delete it."""
    if old_val is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = old_val
