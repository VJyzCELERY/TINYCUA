"""Integration tests for Phase 5: file attachments through agent.run().

Content-type support matrix by server type:
┌──────────────────────────┬─────────────────────┬──────────────────┐
│ Content type             │ LM Studio (local)   │ OpenAI (remote)   │
├──────────────────────────┼─────────────────────┼──────────────────┤
│ input_text / text        │ ✅ works            │ ✅ works          │
│ input_image / image_url  │ ✅ works (vision)   │ ✅ works          │
│ input_file + file_data   │ ❌ 400 unsupported  │ ✅ works          │
│ /v1/files upload         │ ❌ no endpoint      │ ✅ works          │
│ file_id reference        │ ❌ no endpoint      │ ✅ works          │
└──────────────────────────┴─────────────────────┴──────────────────┘

Tests are gated accordingly:
- Inline text + image tests: run everywhere (no skip)
- input_file tests: converted to format-only unit checks
- /v1/files upload + file_id tests: skip on localhost

Configure via .env.test (see .env.test.example for template).
"""

import os
import pathlib

import pytest

from tinycua_sdk import Agent, ContentPart, FileAttachment, LanguageModel


# ── Helpers ──────────────────────────────────────────────────────────────────


_IMAGE_PATH = pathlib.Path(__file__).parent.parent / "fixtures" / "test_image.png"
_PDF_PATH = pathlib.Path(__file__).parent.parent / "fixtures" / "test.pdf"
_TEXT_PATH = pathlib.Path(__file__).parent.parent / "fixtures" / "test.txt"

# File upload tests only work against real OpenAI (not localhost).
# Local LLM servers don't have POST /v1/files.
_requires_files_endpoint = pytest.mark.skipif(
    "localhost" in os.environ.get("LLM_BASE_URL", "")
    or "localhost" in os.environ.get("OPENAI_CHAT_COMPLETIONS_BASE_URL", ""),
    reason="File upload needs real OpenAI /v1/files endpoint (not local server).",
)


# ── Inline image (data URL) — both providers ─────────────────────────────────


@pytest.mark.integration
class TestInlineImageBothProviders:
    """Image attachments via inline data URL through agent.run()."""

    @pytest.mark.asyncio
    async def test_chat_completions_image_inline(self):
        """Chat Completions: image data URL → model response."""
        if not _IMAGE_PATH.exists():
            pytest.skip("test_image.png fixture not found")
        attachment = FileAttachment.from_path(str(_IMAGE_PATH))
        agent = Agent(llm_model=LanguageModel(provider="openai-chat-completions"))
        result = await agent.run(
            "Describe this image in one sentence.",
            file_attachments=[attachment],
        )
        assert isinstance(result, str)
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_responses_image_inline(self):
        """Responses: image data URL → model response."""
        if not _IMAGE_PATH.exists():
            pytest.skip("test_image.png fixture not found")
        attachment = FileAttachment.from_path(str(_IMAGE_PATH))
        agent = Agent(llm_model=LanguageModel(provider="openai-responses"))
        result = await agent.run(
            "Describe this image in one sentence.",
            file_attachments=[attachment],
        )
        assert isinstance(result, str)
        assert len(result) > 10


# ── ContentPart list — both providers ────────────────────────────────────────


@pytest.mark.integration
class TestContentPartBothProviders:
    """ContentPart list as query through agent.run()."""

    @pytest.mark.asyncio
    async def test_chat_completions_parts(self):
        """Chat Completions: list[ContentPart] with text + image."""
        if not _IMAGE_PATH.exists():
            pytest.skip("test_image.png fixture not found")
        img = FileAttachment.from_path(str(_IMAGE_PATH))
        parts = [
            ContentPart(type="text", text="Describe this image in one sentence."),
            ContentPart(type="file", file=img),
        ]
        agent = Agent(llm_model=LanguageModel(provider="openai-chat-completions"))
        result = await agent.run(parts)
        assert isinstance(result, str)
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_responses_parts(self):
        """Responses: list[ContentPart] with text + image."""
        if not _IMAGE_PATH.exists():
            pytest.skip("test_image.png fixture not found")
        img = FileAttachment.from_path(str(_IMAGE_PATH))
        parts = [
            ContentPart(type="text", text="Describe this image in one sentence."),
            ContentPart(type="file", file=img),
        ]
        agent = Agent(llm_model=LanguageModel(provider="openai-responses"))
        result = await agent.run(parts)
        assert isinstance(result, str)
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_chat_completions_text_only_parts(self):
        """Chat Completions: text-only ContentPart list."""
        parts = [ContentPart(type="text", text="Say hello world in one word.")]
        agent = Agent(llm_model=LanguageModel(provider="openai-chat-completions"))
        result = await agent.run(parts)
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    @pytest.mark.asyncio
    async def test_responses_text_only_parts(self):
        """Responses: text-only ContentPart list."""
        parts = [ContentPart(type="text", text="Say hello world in one word.")]
        agent = Agent(llm_model=LanguageModel(provider="openai-responses"))
        result = await agent.run(parts)
        assert isinstance(result, str)
        assert len(result.strip()) > 0


# ── ContentPart + file_attachments merged — both providers ───────────────────


@pytest.mark.integration
class TestContentPartWithAttachmentsBothProviders:
    """ContentPart query merged with file_attachments parameter."""

    @pytest.mark.asyncio
    async def test_chat_completions_merged(self):
        """Chat Completions: ContentPart list + file_attachments merged."""
        if not _IMAGE_PATH.exists():
            pytest.skip("test_image.png fixture not found")
        img = FileAttachment.from_path(str(_IMAGE_PATH))
        parts = [ContentPart(type="text", text="Describe this image concisely.")]
        agent = Agent(llm_model=LanguageModel(provider="openai-chat-completions"))
        result = await agent.run(parts, file_attachments=[img])
        assert isinstance(result, str)
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_responses_merged(self):
        """Responses: ContentPart list + file_attachments merged."""
        if not _IMAGE_PATH.exists():
            pytest.skip("test_image.png fixture not found")
        img = FileAttachment.from_path(str(_IMAGE_PATH))
        parts = [ContentPart(type="text", text="Describe this image concisely.")]
        agent = Agent(llm_model=LanguageModel(provider="openai-responses"))
        result = await agent.run(parts, file_attachments=[img])
        assert isinstance(result, str)
        assert len(result) > 10


# ── Text file inline (no upload needed) — both providers ─────────────────────


@pytest.mark.integration
class TestTextFileInlineBothProviders:
    """Text files sent inline as text content — no /v1/files needed."""

    @pytest.mark.asyncio
    async def test_chat_completions_text_file_inline(self):
        """Chat Completions: text/plain file → decoded → sent as text part."""
        if not _TEXT_PATH.exists():
            pytest.skip("test.txt fixture not found")

        attachment = FileAttachment.from_path(str(_TEXT_PATH), mime_type="text/plain")
        agent = Agent(llm_model=LanguageModel(provider="openai-chat-completions"))
        result = await agent.run(
            "What does this file say? Summarize it.",
            file_attachments=[attachment],
        )
        assert isinstance(result, str)
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_responses_text_file_inline(self):
        """Responses: text/plain file → decoded → sent as input_text."""
        if not _TEXT_PATH.exists():
            pytest.skip("test.txt fixture not found")

        attachment = FileAttachment.from_path(str(_TEXT_PATH), mime_type="text/plain")
        agent = Agent(llm_model=LanguageModel(provider="openai-responses"))
        result = await agent.run(
            "What does this file say? Summarize it.",
            file_attachments=[attachment],
        )
        assert isinstance(result, str)
        assert len(result) > 10


# ── PDF inline via file_data (Responses only, no /v1/files) ──────────────────


@pytest.mark.integration
class TestPdfInlineResponses:
    """PDF sent inline via input_file + file_data (OpenAI-only feature).

    NOTE: LM Studio and most local servers do NOT support ``input_file``
    as a content type in the Responses API. These tests are expected to
    fail with a 400 error on local servers. They are included to validate
    the SDK's correct output format — the SDK emits:
      {"type": "input_file", "filename": "test.pdf", "file_data": "<base64>"}
    For local servers, extract PDF text client-side and send as input_text.
    """

    @pytest.mark.asyncio
    async def test_responses_pdf_inline_file_data_format(self):
        """Verify SDK emits correct input_file + file_data format."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )
        import base64 as _base64

        pdf_data = _base64.b64encode(b"fake pdf").decode("ascii")
        attachment = FileAttachment(
            data=pdf_data, mime_type="application/pdf", filename="test.pdf",
        )
        result = await _translate_responses_attachment(attachment)
        assert result["type"] == "input_file"
        assert result["filename"] == "test.pdf"
        assert result["file_data"] == f"data:application/pdf;base64,{pdf_data}"


# ── PDF upload via /v1/files (requires real OpenAI) — both providers ─────────


@pytest.mark.integration
class TestPdfUploadBothProviders:
    """Non-image PDF upload through both providers (needs /v1/files)."""

    @_requires_files_endpoint
    @pytest.mark.asyncio
    async def test_chat_completions_pdf_upload(self):
        """Chat Completions: PDF upload → model response."""
        attachment = FileAttachment.from_path(
            str(_PDF_PATH), mime_type="application/pdf",
        )
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-chat-completions", model_name="gpt-4o",
            ),
        )
        result = await agent.run(
            "Summarize this document.", file_attachments=[attachment],
        )
        assert isinstance(result, str)
        assert result

    @_requires_files_endpoint
    @pytest.mark.asyncio
    async def test_responses_pdf_upload(self):
        """Responses: PDF upload → model response."""
        attachment = FileAttachment.from_path(
            str(_PDF_PATH), mime_type="application/pdf",
        )
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-responses", model_name="gpt-4o",
            ),
        )
        result = await agent.run(
            "Summarize this document.", file_attachments=[attachment],
        )
        assert isinstance(result, str)
        assert result

    @_requires_files_endpoint
    @pytest.mark.asyncio
    async def test_same_file_uploaded_once_chat_completions(self):
        """Chat Completions: same PDF twice → one upload (cache dedup)."""
        attachment = FileAttachment.from_path(
            str(_PDF_PATH), mime_type="application/pdf",
        )
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-chat-completions", model_name="gpt-4o",
            ),
        )
        await agent.run("First run", file_attachments=[attachment])
        await agent.run("Second run", file_attachments=[attachment])

        upload_session = agent._llm_client._upload_session  # type: ignore[attr-defined]
        assert upload_session is not None
        assert upload_session.cache_size >= 1

    @_requires_files_endpoint
    @pytest.mark.asyncio
    async def test_streaming_pdf_upload_responses(self):
        """Responses: same PDF twice (streaming) — both runs succeed.

        Uses ``stream=True`` so the attachment goes through the upload
        path.  Non-streaming Responses paths send data-backed files
        inline via ``file_data`` with no /v1/files upload.
        """
        attachment = FileAttachment.from_path(
            str(_PDF_PATH), mime_type="application/pdf", stream=True,
        )
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-responses", model_name="gpt-4o",
            ),
        )
        result1 = await agent.run(
            "Summarize this document.", file_attachments=[attachment],
        )
        result2 = await agent.run(
            "Summarize again.", file_attachments=[attachment],
        )
        assert isinstance(result1, str) and result1
        assert isinstance(result2, str) and result2


# ── file_id bypass — both providers (translation-level unit tests) ────────────


@pytest.mark.integration
class TestFileIdBypassBothProviders:
    """file_id-only attachment passthrough at translation layer.

    Verifies that a file_id-only attachment (no data, no URL) is
    translated into the correct provider content-part format without
    requiring an upload.  These tests operate at the translation layer,
    not against a live API, so they do not need a real /v1/files endpoint.
    """

    @pytest.mark.asyncio
    async def test_chat_completions_file_id_bypass(self):
        """Chat Completions: file_id-only attachment → input_file + file_id."""
        from tinycua_sdk.providers.open_ai_chat_completions import (
            _translate_chat_attachment,
        )

        attachment = FileAttachment(
            file_id="file-pre-existing-id", mime_type="application/pdf",
        )
        result = await _translate_chat_attachment(attachment)
        assert result == {"type": "file", "file": {"file_id": "file-pre-existing-id"}}

    @pytest.mark.asyncio
    async def test_responses_file_id_bypass(self):
        """Responses: file_id-only attachment → input_file + file_id."""
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        attachment = FileAttachment(
            file_id="file-pre-existing-id", mime_type="application/pdf",
        )
        result = await _translate_responses_attachment(attachment)
        assert result == {"type": "input_file", "file_id": "file-pre-existing-id"}


# ── Persistent cache across restarts (requires real OpenAI) ──────────────────


@pytest.mark.integration
class TestPersistentCacheBothProviders:
    """Persistent cache survives agent restart."""

    @_requires_files_endpoint
    @pytest.mark.asyncio
    async def test_cache_survives_chat_completions(self, tmp_path):
        """Chat Completions: cache persists across agent instances."""
        attachment = FileAttachment.from_path(
            str(_PDF_PATH), mime_type="application/pdf",
        )
        cache_dir = str(tmp_path / "cache-cc")

        agent1 = Agent(
            llm_model=LanguageModel(
                provider="openai-chat-completions", model_name="gpt-4o",
            ),
            cache_dir=cache_dir,
        )
        await agent1.run("Upload file", file_attachments=[attachment])
        await agent1.close()

        agent2 = Agent(
            llm_model=LanguageModel(
                provider="openai-chat-completions", model_name="gpt-4o",
            ),
            cache_dir=cache_dir,
        )
        result = await agent2.run(
            "Use cached file", file_attachments=[attachment],
        )
        assert isinstance(result, str)
        assert result

        # Verify cache file exists
        import hashlib
        base_url = "https://api.openai.com/v1"
        base_url_hash = hashlib.sha256(base_url.encode()).hexdigest()
        cache_file = (
            pathlib.Path(cache_dir) / "openai-chat-completions"
            / base_url_hash / "default" / "cache.jsonl"
        )
        assert cache_file.exists()
        await agent2.close()

    @_requires_files_endpoint
    @pytest.mark.asyncio
    async def test_streaming_cache_responses(self, tmp_path):
        """Responses: streaming PDF across agent instances — both succeed.

        Uses ``stream=True`` so the attachment goes through the upload
        path.  Non-streaming Responses paths send data-backed files
        inline via ``file_data``.
        """
        attachment = FileAttachment.from_path(
            str(_PDF_PATH), mime_type="application/pdf", stream=True,
        )
        cache_dir = str(tmp_path / "cache-resp")

        agent1 = Agent(
            llm_model=LanguageModel(
                provider="openai-responses", model_name="gpt-4o",
            ),
            cache_dir=cache_dir,
        )
        result1 = await agent1.run(
            "Summarize this document.", file_attachments=[attachment],
        )
        assert isinstance(result1, str)
        assert result1
        await agent1.close()

        agent2 = Agent(
            llm_model=LanguageModel(
                provider="openai-responses", model_name="gpt-4o",
            ),
            cache_dir=cache_dir,
        )
        result2 = await agent2.run(
            "Summarize again.", file_attachments=[attachment],
        )
        assert isinstance(result2, str)
        assert result2
        await agent2.close()


# ── URL attachment coverage (FR-017) ─────────────────────────────────────────


@pytest.mark.integration
class TestUrlAttachmentTranslation:
    """Verify non-image URL attachments produce correct provider format.

    These are format-level tests that verify the SDK translation
    produces the expected content-part structure WITHOUT making real
    HTTP requests.  They ensure URL attachments go through the
    correct code path for each provider.
    """

    @pytest.mark.asyncio
    async def test_responses_url_attachment_inline_file_data(self):
        """Responses: non-image URL attachment → inline file_data (no /v1/files)."""
        from unittest.mock import AsyncMock, patch

        from tinycua_sdk.models.attachment import FileAttachment
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        # Mock _download_url_content to avoid real HTTP requests
        fake_content = b"fake-pdf-content"
        with patch(
            "tinycua_sdk.providers.upload._download_url_content",
            AsyncMock(return_value=fake_content),
        ):
            attachment = FileAttachment.from_url(
                "https://example.com/doc.pdf",
                mime_type="application/pdf",
                filename="doc.pdf",
            )
            result = await _translate_responses_attachment(attachment)

        assert result["type"] == "input_file"
        assert "file_id" not in result, (
            "Responses URL attachments should send inline file_data, "
            "not require /v1/files"
        )
        assert result["filename"] == "doc.pdf"
        assert "file_data" in result
        assert result["file_data"].startswith("data:application/pdf;base64,")

    @pytest.mark.asyncio
    async def test_chat_completions_url_attachment_uses_file_id(self):
        """Chat Completions: non-image URL → download+upload → file_id reference."""
        from unittest.mock import AsyncMock

        from tinycua_sdk.models.attachment import FileAttachment
        from tinycua_sdk.providers.open_ai_chat_completions import (
            _translate_chat_attachment,
        )

        mock_upload = AsyncMock(return_value="file-from-url-123")
        attachment = FileAttachment.from_url(
            "https://example.com/doc.pdf",
            mime_type="application/pdf",
            filename="doc.pdf",
        )
        result = await _translate_chat_attachment(
            attachment, _upload_fn=mock_upload,
        )

        assert result == {"type": "file", "file": {"file_id": "file-from-url-123"}}
        mock_upload.assert_called_once()


@pytest.mark.integration
class TestUrlAttachmentIntegration:
    """Full-path URL attachment tests (gated on external API availability)."""

    @_requires_files_endpoint
    @pytest.mark.asyncio
    async def test_chat_completions_url_pdf_upload(self):
        """Chat Completions: URL PDF → download + upload → model response.

        Downloads a small public PDF and sends it through Chat Completions
        via /v1/files upload.  Requires real OpenAI endpoint.
        """
        attachment = FileAttachment.from_url(
            "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            mime_type="application/pdf",
            filename="dummy.pdf",
        )
        agent = Agent(
            llm_model=LanguageModel(
                provider="openai-chat-completions", model_name="gpt-4o-mini",
            ),
        )
        result = await agent.run(
            "What does this document contain? Answer in one sentence.",
            file_attachments=[attachment],
        )
        assert isinstance(result, str)
        assert len(result) > 10

    @pytest.mark.asyncio
    async def test_responses_url_pdf_inline_integration(self):
        """Responses: URL PDF → downloaded → sent inline via file_data.

        This test verifies the inline file_data code path for Responses
        URL attachments by using a mock download function.  Real HTTP
        download tests require an internet-accessible URL and are covered
        by the Chat Completions test above.
        """
        from unittest.mock import AsyncMock, patch

        from tinycua_sdk.models.attachment import FileAttachment
        from tinycua_sdk.providers.open_ai_responses import (
            _translate_responses_attachment,
        )

        with patch(
            "tinycua_sdk.providers.upload._download_url_content",
            AsyncMock(return_value=b"%PDF-1.4 fake content"),
        ):
            attachment = FileAttachment.from_url(
                "https://example.com/report.pdf",
                mime_type="application/pdf",
                filename="report.pdf",
            )
            result = await _translate_responses_attachment(attachment)

        assert result == {
            "type": "input_file",
            "filename": "report.pdf",
            "file_data": (
                "data:application/pdf;base64,"
                + "JVBERi0xLjQgZmFrZSBjb250ZW50"
            ),
        }
