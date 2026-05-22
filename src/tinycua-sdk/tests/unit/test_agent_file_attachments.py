"""Unit tests for Agent.run() file attachment convenience API."""

import pytest
from tinycua_sdk import Agent, BaseLoop, ContentPart, FileAttachment, LanguageModel


class TestAgentRunFileAttachments:
    """Test Agent.run() with file_attachments parameter."""

    @pytest.mark.asyncio
    async def test_run_str_query_with_file_attachments(self):
        """Verify str query + file_attachments produces content: str + attachments key."""
        agent = Agent(llm_model=LanguageModel())
        captured: dict = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")

        await agent.run("Describe this", file_attachments=[img])
        user_msg = captured["messages"][-1]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "Describe this"
        assert user_msg["attachments"] == [img]

    @pytest.mark.asyncio
    async def test_run_empty_query_with_file_attachments(self):
        """Verify empty str query + file_attachments produces content: '' + attachments key."""
        agent = Agent(llm_model=LanguageModel())
        captured: dict = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")

        await agent.run("", file_attachments=[img])
        user_msg = captured["messages"][-1]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == ""
        assert user_msg["attachments"] == [img]

    @pytest.mark.asyncio
    async def test_run_str_query_without_file_attachments(self):
        """Verify backward compatibility: str query with no attachments unchanged."""
        agent = Agent(llm_model=LanguageModel())
        captured: dict = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        await agent.run("Hello")
        assert captured["messages"][-1] == {"role": "user", "content": "Hello"}

    @pytest.mark.asyncio
    async def test_run_content_parts_query_without_attachments(self):
        """Verify list[ContentPart] query uses content parts directly."""
        agent = Agent(llm_model=LanguageModel())
        captured: dict = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")
        parts = [
            ContentPart(type="text", text="Look at this"),
            ContentPart(type="file", file=img),
        ]

        await agent.run(parts)
        user_msg = captured["messages"][-1]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == parts
        assert "attachments" not in user_msg

    @pytest.mark.asyncio
    async def test_run_content_parts_query_with_attachments_merges(self):
        """Verify list[ContentPart] query + file_attachments merges into single list."""
        agent = Agent(llm_model=LanguageModel())
        captured: dict = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img1 = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")
        img2 = FileAttachment(data="AQIDBA==", mime_type="image/jpeg")
        parts = [ContentPart(type="text", text="Compare these")]

        await agent.run(parts, file_attachments=[img1, img2])
        user_msg = captured["messages"][-1]
        assert user_msg["role"] == "user"
        assert len(user_msg["content"]) == 3
        assert user_msg["content"][0] == ContentPart(type="text", text="Compare these")
        assert user_msg["content"][1] == ContentPart(type="file", file=img1)
        assert user_msg["content"][2] == ContentPart(type="file", file=img2)
        assert "attachments" not in user_msg

    @pytest.mark.asyncio
    async def test_run_empty_file_attachments_is_noop(self):
        """Verify file_attachments=[] behaves same as None."""
        agent = Agent(llm_model=LanguageModel())
        captured: dict = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        await agent.run("Hello", file_attachments=[])
        assert captured["messages"][-1] == {"role": "user", "content": "Hello"}

    @pytest.mark.asyncio
    async def test_run_invalid_file_attachments_raises_type_error(self):
        """Verify TypeError for non-FileAttachment items in file_attachments."""
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(TypeError, match="file_attachments"):
            await agent.run("Hello", file_attachments=["not_a_file_attachment"])

    @pytest.mark.asyncio
    async def test_run_none_in_file_attachments_raises_type_error(self):
        """Verify TypeError for None items in file_attachments."""
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(TypeError, match="file_attachments"):
            await agent.run("Hello", file_attachments=[None])

    @pytest.mark.asyncio
    async def test_run_invalid_query_type_raises_type_error(self):
        """Verify TypeError when query is neither str nor list[ContentPart]."""
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(TypeError, match="query"):
            await agent.run(42)

    @pytest.mark.asyncio
    async def test_run_content_parts_query_rejects_non_content_part_items(self):
        """Verify TypeError when list[ContentPart] query contains non-ContentPart items."""
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(TypeError, match="ContentPart"):
            await agent.run(["not_a_content_part", "also_invalid"])

    @pytest.mark.asyncio
    async def test_run_empty_content_parts_query_raises_type_error(self):
        """Verify TypeError when query is an empty list[ContentPart]."""
        agent = Agent(llm_model=LanguageModel())
        with pytest.raises(TypeError, match="query"):
            await agent.run([])

    @pytest.mark.asyncio
    async def test_run_stream_with_file_attachments(self):
        """Verify streaming works with file_attachments and attachments reach the request."""
        agent = Agent(llm_model=LanguageModel())
        captured: dict = {}

        async def fake_stream(messages, tools, stream=False):
            # Capture a shallow copy before BaseLoop mutates the messages in-place
            captured["messages"] = list(messages)
            captured["stream"] = stream

            async def _gen():
                yield {"type": "response.output_text.delta", "delta": "Hi", "index": 0}

            return _gen()

        agent._call_llm = fake_stream
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")

        stream_iter = await agent.run("Describe", file_attachments=[img], stream=True)
        events = [e async for e in stream_iter]
        assert any(e["type"] == "response.output_text.delta" for e in events)
        assert captured["stream"] is True
        assert captured["messages"][-1]["content"] == "Describe"
        assert captured["messages"][-1]["attachments"] == [img]

    @pytest.mark.asyncio
    async def test_run_preserves_message_history_with_attachments(self):
        """Verify message history is preserved when using file_attachments."""
        agent = Agent(llm_model=LanguageModel())
        captured: dict = {}

        class CapturingLoop(BaseLoop):
            async def run(self, agent, messages, tools, override_instructions=None, **kwargs):
                captured["messages"] = messages
                return "ok"

        agent.config.loop = CapturingLoop()
        img = FileAttachment(data="iVBORw0KGgo=", mime_type="image/png")
        history = [
            {"role": "user", "content": "Previous"},
            {"role": "assistant", "content": "Previous reply"},
        ]

        await agent.run("New query", messages=history, file_attachments=[img])
        assert captured["messages"][0] == history[0]
        assert captured["messages"][1] == history[1]
        assert captured["messages"][2]["role"] == "user"
        assert captured["messages"][2]["content"] == "New query"
