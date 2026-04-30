"""05 - Agent with Tools and Skills

Shows the combined usage of tools AND skills on a single agent.
This is the most common real-world setup.
"""

import asyncio

from tinycua_sdk import Agent, LanguageModel, Skill, tool


# ---- Tools ---------------------------------------------------------------
@tool
def web_search(query: str) -> str:
    """Search the web for current information."""
    return f"[Search results for: {query}]"


@tool
def read_file(path: str) -> str:
    """Read the contents of a file."""
    with open(path, "r") as f:
        return f.read()


# ---- Skills --------------------------------------------------------------
research_skill = Skill(
    name="web_research",
    description="Research topics on the web.",
    instructions=(
        "Always verify facts with web_search before answering. "
        "Cite the sources you used."
    ),
)

code_skill = Skill(
    name="file_navigator",
    description="Navigate and read project files.",
    instructions=(
        "When the user asks about code, read the relevant files first "
        "using read_file before forming an answer."
    ),
)


async def main() -> None:
    agent = Agent(
        name="research_coder",
        instructions="You are a research assistant that can also read code.",
        llm_model=LanguageModel(
            provider="openai-compatible",
            base_url="http://localhost:1234/v1",
            temperature=0.3,
        ),
        tools=[web_search, read_file],
        skills=[research_skill, code_skill],
    )

    # The agent now has:
    #   - 2 tools it can invoke (web_search, read_file)
    #   - 2 skill instruction blocks in its system context
    #
    # The loop will automatically handle tool calls and re-prompting.

    response = await agent.run(
        "What is the latest version of FastAPI? Also show me main.py."
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
