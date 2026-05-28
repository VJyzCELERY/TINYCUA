"""Custom ReAct loop example.

Demonstrates: Extending BaseLoop to implement the ReAct pattern.
"""

import asyncio
import json

from tinycua_sdk import Agent, LanguageModel, BaseLoop, tool
from tinycua_sdk.agent.executor import ToolExecutor


class ReActLoop(BaseLoop):
    """ReAct (Reasoning + Acting) loop implementation.

    This is a consumer-defined loop that extends BaseLoop.
    The SDK only provides BaseLoop; this is built on top.
    """

    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        if stream:
            raise NotImplementedError("ReActLoop does not support streaming yet")

        for i in range(self.max_iterations):
            # 1. Reasoning step
            reasoning_msgs = messages + [
                {"role": "assistant", "content": "Let me think step by step..."}
            ]

            # 2. Action step: call LLM with tools
            response = await agent._call_llm(reasoning_msgs, tools=tools)

            # 3. Check if done
            tool_calls = response.get("tool_calls", [])
            if not tool_calls:
                return response.get("content", "")

            # Execute tools and append results
            for tc in tool_calls:
                tool_name = tc["name"]
                arguments = json.loads(tc["arguments"])
                for t in tools:
                    if t.name == tool_name:
                        result = await ToolExecutor.execute(t, arguments, agent)
                        call_id = tc.get("call_id", tc["id"])
                        messages.append({
                            "type": "function_call",
                            "call_id": call_id,
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        })
                        messages.append({
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": str(result),
                        })
                        break

        return "[max iterations reached]"


@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"


async def main():
    agent = Agent(
        llm_model=LanguageModel(
            provider="openai-compatible",
            base_url="http://127.0.0.1:1234/v1",
            model_name="qwen/qwen3.5-9b",
        ),
        instructions="Use search to find information.",
        loop=ReActLoop(max_iterations=3),
    )
    agent.add_tools(search)
    response = await agent.run("What is quantum computing?")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
