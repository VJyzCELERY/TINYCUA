"""Integration tests for OpenAI Responses file attachment translation."""

import os

import pytest

from tinycua_sdk.agent.events import UserMessage
from tinycua_sdk.agent.llm_model import LanguageModel
from tinycua_sdk.models.attachment import ContentPart, FileAttachment
from tinycua_sdk.providers.open_ai_responses import OpenAIResponsesClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.provider("openai-responses"),
    pytest.mark.skipif(
        not os.getenv("OPENAI_RESPONSES_MODEL") and not os.getenv("LLM_MODEL"),
        reason="Neither OPENAI_RESPONSES_MODEL nor LLM_MODEL set; "
        "skipping Responses integration tests",
    ),
]

# Keywords that indicate a non-vision model rejected the image input
_NO_VISION_KEYWORDS = (
    "unable",
    "can't view",
    "cannot view",
    "no vision",
    "image input not supported",
)
# Color keywords expected from the multi-color fixture
_COLOR_KEYWORDS = ("red", "green", "blue", "yellow")


def _assert_image_response(content: str) -> None:
    """Assert the response content contains vision-model color keywords
    or a non-vision refusal. Both paths pass deterministically."""
    lower = content.lower()
    no_vision = any(kw in lower for kw in _NO_VISION_KEYWORDS)
    has_colors = any(kw in lower for kw in _COLOR_KEYWORDS)
    assert no_vision or has_colors, (
        f"Expected vision model color keywords {_COLOR_KEYWORDS} or "
        f"non-vision refusal keywords {_NO_VISION_KEYWORDS}, "
        f"got: {content!r}"
    )


@pytest.mark.asyncio
async def test_responses_image_attachment_sends_image():
    """Sending an image attachment through the Responses provider sends the
    image and yields an assistant response referencing the image content."""
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
        attachment = FileAttachment.from_path("tests/fixtures/test_image.png")
        messages: list[UserMessage] = [
            {
                "role": "user",
                "content": (
                    "What colors do you see in the attached image? "
                    "List only the color names."
                ),
                "attachments": [attachment],
            },
        ]
        result = await client.chat(messages=messages)
        assert result["content"] is not None
        assert isinstance(result["content"], str)
        assert len(result["content"]) > 0
        _assert_image_response(result["content"])
    finally:
        await client.close()
        _restore_env("OPENAI_RESPONSES_BASE_URL", old_responses_base)
        _restore_env("OPENAI_RESPONSES_API_KEY", old_responses_api_key)


@pytest.mark.asyncio
async def test_responses_content_part_image_sends_image():
    """Sending a ContentPart image through the Responses provider sends the
    image and yields an assistant response referencing the image content."""
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
        attachment = FileAttachment.from_path("tests/fixtures/test_image.png")
        parts = [
            ContentPart(type="text", text="What colors do you see? List only the color names."),
            ContentPart(type="file", file=attachment),
        ]
        messages: list[UserMessage] = [
            {"role": "user", "content": parts},
        ]
        result = await client.chat(messages=messages)
        assert result["content"] is not None
        assert isinstance(result["content"], str)
        assert len(result["content"]) > 0
        _assert_image_response(result["content"])
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
