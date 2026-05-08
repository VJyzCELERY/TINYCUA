"""Target 4.4: Verify agent with both tools and skills works."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill, tool


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


@tool
def web_search(query: str) -> str:
    """Search the web for current information."""
    return f"[Search results for: {query}]"


research_skill = Skill(
    name="web_research",
    description="Research topics on the web.",
    instructions=(
        "Always verify facts with web_search before answering. "
        "Cite the sources you used."
    ),
)


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
        tools=[web_search],
        skills=[research_skill],
        instructions="You are a research assistant.",
    )

    response = await a.run("What is the latest version of FastAPI?", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
