"""04 - Agent with Skills

Shows how to attach skills to an agent.
Skills inject their instructions into the agent's system context.
"""

import asyncio

from tinycua_sdk import Agent, LanguageModel, Skill


async def main() -> None:
    # -----------------------------------------------------------------------
    # 1. Create skills
    # -----------------------------------------------------------------------
    coding_skill = Skill(
        name="python_expert",
        description="Write idiomatic Python code.",
        instructions=(
            "When writing Python code, follow PEP 8, use type hints, "
            "prefer dataclasses over raw dicts, and always include docstrings."
        ),
    )

    testing_skill = Skill(
        name="testing_guru",
        description="Write comprehensive tests.",
        instructions=(
            "Always write pytest test cases for any code you generate. "
            "Cover happy paths, edge cases, and error conditions."
        ),
    )

    # -----------------------------------------------------------------------
    # 2. Create an agent with skills
    # -----------------------------------------------------------------------
    agent = Agent(
        name="senior_engineer",
        instructions="You are a senior software engineer.",
        llm_model=LanguageModel(
            provider="openai-compatible",
            base_url="http://localhost:1234/v1",
        ),
        skills=[coding_skill, testing_skill],
    )

    # When the agent runs, both skill instruction blocks are appended to
    # the system prompt (in registration order):
    #
    #   system: You are a senior software engineer.
    #   system: [python_expert instructions]
    #   system: [testing_guru instructions]

    response = await agent.run("Write a function that validates an email address.")
    print("Response:", response)

    # -----------------------------------------------------------------------
    # 3. Add skills dynamically
    # -----------------------------------------------------------------------
    docs_skill = Skill(
        name="documentarian",
        description="Write clear documentation.",
        instructions="Use Google-style docstrings and add a usage example.",
    )
    agent.add_skills(docs_skill)

    response = await agent.run("Now document that email function.")
    print("After adding skill:", response)


if __name__ == "__main__":
    asyncio.run(main())
