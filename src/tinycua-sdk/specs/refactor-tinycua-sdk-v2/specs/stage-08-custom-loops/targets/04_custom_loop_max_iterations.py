"""Target 8.4: Verify custom loop respects self.max_iterations."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop


class CountingLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream="off"):
        count = 0
        for _ in range(self.max_iterations):
            count += 1
        return f"ran {count} times"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        loop=CountingLoop(max_iterations=3),
    )

    response = await a.run("Hello")
    assert response == "ran 3 times"
    print(f"Response: {response}")


asyncio.run(main())
