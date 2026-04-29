"""Integration tests for Tool execution."""

import pytest
from tinycua_sdk import Agent, LLMModel, tool


@tool
def search(query: str) -> str:
    """Search for something."""
    return f"Results for: {query}"


@tool
def summarize(text: str) -> str:
    """Summarize text."""
    return f"Summary: {text}"


class TestToolExecution:
    """Integration tests for tool execution."""

    @pytest.mark.asyncio
    async def test_tool_invoked_during_run(self, mock_llm_with_tool_calls):
        """Tool is called during agent run (mocked LLM returns tool call JSON)."""
        agent = Agent(llm_model=LLMModel(), tools=[search])
        response = await agent.run("Search for quantum")
        assert isinstance(response, str)
        assert "quantum" in response.lower()

    @pytest.mark.asyncio
    async def test_multiple_tools(self, mock_llm_client):
        """Multiple tools available."""
        agent = Agent(llm_model=LLMModel(), tools=[search, summarize])
        assert len(agent.tools) == 2
        response = await agent.run("Do something")
        assert response == "Mocked response"

    def test_tool_with_defaults(self):
        """Tool with default parameters."""

        @tool
        def greet(name: str = "World") -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        result = greet.invoke()
        assert result == "Hello, World!"

    @pytest.mark.asyncio
    async def test_no_tools(self, mock_llm_client):
        """Agent without tools still runs."""
        agent = Agent(llm_model=LLMModel())
        response = await agent.run("Hello")
        assert response == "Mocked response"

    def test_tool_direct_invoke(self):
        """Direct Tool.invoke()."""
        result = search.invoke(query="test")
        assert result == "Results for: test"

    def test_tool_schema_for_api(self):
        """Schema generation for API calls."""
        schema = search.to_config()
        assert schema["name"] == "search"
        assert "query" in schema["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_tool_error_handling(self, mock_llm_client):
        """Tool exceptions handled gracefully."""

        @tool
        def failing_tool():
            """A tool that fails."""
            raise RuntimeError("Tool failed")

        agent = Agent(llm_model=LLMModel(), tools=[failing_tool])
        response = await agent.run("Use failing tool")
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_add_tools_then_run(self, mock_llm_client):
        """Add tools after construction."""
        agent = Agent(llm_model=LLMModel())
        agent.add_tools(search)
        assert len(agent.tools) == 1
        response = await agent.run("Search")
        assert response == "Mocked response"

    @pytest.mark.asyncio
    async def test_add_multiple_tools(self, mock_llm_client):
        """Add list of tools."""
        agent = Agent(llm_model=LLMModel())
        agent.add_tools([search, summarize])
        assert len(agent.tools) == 2
        response = await agent.run("Do something")
        assert response == "Mocked response"
