"""Custom ReAct loop example.

Demonstrates: Extending BaseLoop to implement the ReAct pattern.
"""

import asyncio

from tinycua_sdk import Agent, LLMModel, BaseLoop, tool


class ReActLoop(BaseLoop):
    """ReAct (Reasoning + Acting) loop implementation.

    This is a consumer-defined loop that extends BaseLoop.
    The SDK only provides BaseLoop; this is built on top.
    """

    async def run(self, agent, messages, tools):
        for i in range(self.max_iterations):
            # 1. Reasoning step
            reasoning_msgs = messages + [
                {"role": "assistant", "content": "Let me think step by step..."}
            ]

            # 2. Action step: call LLM with tools
            tool_schemas = [t.to_config() for t in tools] if tools else None
            response = await agent._call_llm(reasoning_msgs, tools=tool_schemas)

            # 3. Check if done
            tool_calls = self._extract_tool_calls(response)
            if not tool_calls:
                return response

            # Execute tools and append results
            for call in tool_calls:
                result = self._execute_tool_call(call, tools)
                messages.append({"role": "tool", "content": str(result)})

        return response

    def _extract_tool_calls(self, response):
        """Extract tool calls from LLM response.

        Simplified: production code parses structured response format.
        """
        return []

    def _execute_tool_call(self, call, tools):
        """Execute a single tool call.

        Simplified: production code looks up tool by name and invokes with args.
        """
        return "Tool result"


@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"


async def main():
    agent = Agent(
        llm_model=LLMModel(),
        instructions="Use search to find information.",
        loop=ReActLoop(max_iterations=3),
    )
    agent.add_tools(search)
    response = await agent.run("What is quantum computing?")
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
