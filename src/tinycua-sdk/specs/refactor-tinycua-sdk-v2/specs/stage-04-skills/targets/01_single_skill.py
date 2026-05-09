"""Target 4.1: Verify agent with one skill includes its instructions."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


async def main():
    coding_skill = Skill(
        name="python_expert",
        description="Write idiomatic Python code.",
        instructions=(
            "When writing Python code, follow PEP 8, use type hints, "
            "prefer dataclasses over raw dicts."
        ),
    )

    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
        skills=[coding_skill],
    )

    response = await a.run("Write a hello world function.", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
