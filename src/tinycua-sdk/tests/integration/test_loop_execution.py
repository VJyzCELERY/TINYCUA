"""Integration tests for Loop execution."""

import pytest
from unittest.mock import AsyncMock, patch
from tinycua_sdk import Agent, LLMModel, BaseLoop, tool


class TestLoopExecution:
    """Integration tests for loop execution."""

    @pytest.mark.asyncio
    async def test_run_basic(self, mock_llm_client):
        """Basic run with mocked LLM."""
        agent = Agent(llm_model=LLMModel())
        response = await agent.run("Hello")
        assert response == "Mocked response"

    @pytest.mark.asyncio
    async def test_run_with_messages(self, mock_llm_client):
        """Pass message history."""
        agent = Agent(llm_model=LLMModel())
        messages = [{"role": "user", "content": "Previous"}]
        response = await agent.run("Hello", messages=messages)
        assert response == "Mocked response"

    @pytest.mark.asyncio
    async def test_run_stream(self):
        """Streaming response."""
        agent = Agent(llm_model=LLMModel())

        async def mock_stream():
            yield "chunk1"
            yield "chunk2"

        with patch("tinycua_sdk.agent.executor.LLMClient") as MockClient:
            MockClient.return_value.chat = AsyncMock(return_value=mock_stream())
            stream = await agent.run("Hello", stream=True)
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)
            assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_run_with_tools(self, mock_llm_with_tool_calls):
        """Tool calling in loop (mocked LLM returns tool call JSON)."""

        @tool
        def search(query: str) -> str:
            """Search for something."""
            return f"Results: {query}"

        agent = Agent(llm_model=LLMModel(), tools=[search])
        response = await agent.run("Search for quantum")
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_run_stateless(self, mock_llm_client):
        """Multiple runs are independent."""
        agent = Agent(llm_model=LLMModel())
        r1 = await agent.run("Query 1")
        r2 = await agent.run("Query 2")
        assert r1 == "Mocked response"
        assert r2 == "Mocked response"

    @pytest.mark.skip(reason="Custom loop wiring is implemented in Stage 3")
    @pytest.mark.asyncio
    async def test_custom_loop(self, mock_llm_client):
        """Agent with custom BaseLoop subclass."""

        class CustomLoop(BaseLoop):
            async def run(self, agent, messages, tools):
                return "Custom result"

        agent = Agent(llm_model=LLMModel(), loop=CustomLoop())
        response = await agent.run("Hello")
        assert response == "Custom result"

    @pytest.mark.asyncio
    async def test_base_loop_default(self, mock_llm_client):
        """Default BaseLoop() used when loop=None."""
        agent = Agent(llm_model=LLMModel())
        response = await agent.run("Hello")
        assert response == "Mocked response"
