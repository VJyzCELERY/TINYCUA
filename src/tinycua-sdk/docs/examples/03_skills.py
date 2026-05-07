"""Agent with skills example.

Demonstrates: Skill.load(), add_skills(), skill-based instructions.
"""

import asyncio

from tinycua_sdk import Agent, LLMModel, Skill


async def main():
    skill_md = """
---
name: researcher
category: research
tools:
  - search
---
# Researcher
## Instructions
Research topics thoroughly and cite sources.
"""
    researcher = Skill.load(skill_md)

    agent = Agent(
        llm_model=LLMModel(),
        instructions="Answer questions using research skills.",
    )
    agent.add_skills(researcher)
    response = await agent.run("What is quantum computing?")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
