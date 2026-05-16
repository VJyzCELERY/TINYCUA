"""Target 4.3: Verify skills added after creation work on next run."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, Skill


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    docs_skill = Skill(
        name="documentarian",
        description="Write clear documentation.",
        instructions="Use Google-style docstrings and add a usage example.",
    )
    a.add_skills(docs_skill)

    response = await a.run("Now document that function.", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
