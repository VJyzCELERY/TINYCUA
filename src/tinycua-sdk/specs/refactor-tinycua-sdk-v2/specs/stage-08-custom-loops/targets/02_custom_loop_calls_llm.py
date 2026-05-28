"""Target 8.2: Verify custom loop can call agent._call_llm()."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop


class LLMLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream="off"):
        response = await agent._call_llm(messages)
        return response.get("content", "") or "[no content]"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        loop=LLMLoop(),
    )

    response = await a.run("Say hi.", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
