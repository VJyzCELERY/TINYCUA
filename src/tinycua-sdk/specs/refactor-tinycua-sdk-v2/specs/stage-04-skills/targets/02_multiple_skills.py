"""Target 4.2: Verify multiple skills inject instructions in registration order."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


async def main():
    skill_a = Skill(name="s1", description="First", instructions="Instruction A.")
    skill_b = Skill(name="s2", description="Second", instructions="Instruction B.")

    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
        skills=[skill_a, skill_b],
    )

    response = await a.run("Hello.", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
