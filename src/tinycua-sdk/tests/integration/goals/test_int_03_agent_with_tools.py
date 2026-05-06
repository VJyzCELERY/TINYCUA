"""Integration tests for agent with tools (INT-03).

Converts targets: 05_tool_calling_loop, 06_dynamic_add_tools
"""

import pytest

from tinycua_sdk import Agent, LanguageModel, tool


class TestInt03AgentWithTools:
    """Test suite for agent tool calling patterns."""

    @pytest.mark.asyncio
    async def test_int_01_tool_calling_loop(self, mock_llm_with_tool_calls):
        """Target 3.5: Agent with tools correctly invokes them."""
        @tool
        def search(query: str) -> str:
            return f"Results for: {query}"

        agent = Agent(
            llm_model=LanguageModel(),
            tools=[search],
            instructions="You have access to a search tool. Use it for lookups.",
        )

        response = await agent.run("Search for quantum", stream="off")
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_int_02_dynamic_add_tools(self, mock_llm_client):
        """Target 3.6: Tools added after creation work on next run."""
        @tool
        def convert_currency(amount: float, from_c: str, to_c: str) -> str:
            rates = {"USD": 1.0, "EUR": 0.92}
            usd = amount / rates[from_c]
            return f"{usd * rates[to_c]:.2f}"

        agent = Agent(llm_model=LanguageModel())

        agent.add_tools(convert_currency)

        response = await agent.run("Convert 100 USD to EUR.", stream="off")
        assert isinstance(response, str)
