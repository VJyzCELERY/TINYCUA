"""Target 8.1: Verify subclassing BaseLoop and passing to Agent uses the custom loop."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop


class MyLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream="off"):
        return "custom result"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        loop=MyLoop(),
    )

    response = await a.run("Hello")
    assert response == "custom result"
    print(f"Response: {response}")


asyncio.run(main())
