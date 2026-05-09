"""Target 8.3: Verify custom loop respects agent.is_cancelled."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop


class SlowLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        for i in range(100):
            if agent.is_cancelled:
                return "[cancelled]"
            await asyncio.sleep(0.01)
        return "done"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        loop=SlowLoop(),
    )

    task = asyncio.create_task(a.run("Wait"))
    await asyncio.sleep(0.05)
    a.cancel()

    response = await task
    assert response == "[cancelled]"
    print(f"Response: {response}")


asyncio.run(main())
