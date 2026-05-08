"""Target 8.5: Verify a ReAct-style custom loop works."""

import asyncio
import json
from tinycua_sdk import Agent, LanguageModel, BaseLoop, tool


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


@tool
def weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny in {city}."


class ReActLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream="off"):
        response = await agent._call_llm(messages, tools)
        content = response.get("content", "")

        # If the model produces a tool call in its response, execute it
        if response.get("tool_calls"):
            for tc in response["tool_calls"]:
                tool_name = tc["function"]["name"]
                arguments = json.loads(tc["function"]["arguments"])
                for t in tools:
                    if t.name == tool_name:
                        result = t.invoke(**arguments)
                        messages.append({"role": "assistant", "content": content})
                        messages.append({"role": "tool", "content": str(result), "name": tool_name})
                        break

            # One more LLM call with the tool result
            response2 = await agent._call_llm(messages)
            return response2.get("content", "") or "[no final answer]"

        return content


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME),
        tools=[weather],
        loop=ReActLoop(),
    )

    response = await a.run("What is the weather in Tokyo?", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
