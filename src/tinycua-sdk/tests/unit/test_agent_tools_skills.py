"""Integration tests for agent with tools and skills (INT-05).

Converts targets: 04_combined_tools_and_skills
"""

import pytest

from tinycua_sdk import Agent, LanguageModel, Skill, tool


class TestInt05AgentWithToolsAndSkills:
    """Test suite for combined tools + skills usage."""

    @pytest.mark.asyncio
    async def test_int_01_combined_tools_and_skills(self, mock_llm_with_tool_calls):
        """Target 4.4: Agent with instructions, tools, and skills."""

        @tool
        def search(query: str) -> str:
            return f"[Search results for: {query}]"

        research_skill = Skill(
            name="web_research",
            description="Research topics on the web.",
            instructions=(
                "Always verify facts with web_search before answering. "
                "Cite the sources you used."
            ),
        )

        agent = Agent(
            llm_model=LanguageModel(),
            tools=[search],
            skills=[research_skill],
            instructions="You are a research assistant.",
        )

        response = await agent.run(
            "What is the latest version of FastAPI?", stream=False
        )
        assert isinstance(response, str)
        assert len(response) > 0

        first_call_kwargs = mock_llm_with_tool_calls.call_args_list[0][1]
        messages = first_call_kwargs["json"]["messages"]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert "You are a research assistant." in system_msg["content"]
        assert "[web_research]" in system_msg["content"]
        assert "verify facts" in system_msg["content"]

        assert mock_llm_with_tool_calls.call_count >= 2

        second_call_kwargs = mock_llm_with_tool_calls.call_args_list[1][1]
        second_messages = second_call_kwargs["json"]["messages"]
        tool_msgs = [m for m in second_messages if m["role"] == "tool"]
        assert len(tool_msgs) >= 1
        assert "[Search results for: quantum]" in tool_msgs[0]["content"]
