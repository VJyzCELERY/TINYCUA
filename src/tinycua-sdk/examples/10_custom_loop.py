"""Custom Agent Loop Examples.

This example demonstrates how to create custom agent loops using Runner helper methods.
Pass a DefaultLoop subclass to Agent to customize execution behavior!
"""

import asyncio

from tinycua_sdk import Agent
from tinycua_sdk.agent.loop import DefaultLoop
from tinycua_sdk.tools import tool


# =============================================================================
# Example 1: Logging Loop - basic customization
# =============================================================================


class LoggingLoop(DefaultLoop):
    """Custom loop that logs each step of execution."""

    async def run(self, agent, user_input, **kwargs):
        print(f"[LoggingLoop] Starting: {user_input[:50]}...")

        result = await super().run(agent, user_input, **kwargs)

        print("[LoggingLoop] Completed")
        return result


# =============================================================================
# Example 2: Custom Direct Loop - using Runner helpers
# =============================================================================


class CustomDirectLoop(DefaultLoop):
    """Custom direct loop using Runner helper methods.

    This shows how to build the same behavior as the default
    but using composable helper methods.
    """

    async def run(self, agent, user_input, max_calls=5, **kwargs):
        plan_mode = kwargs.get("plan_mode", False)
        verbose = kwargs.get("verbose", False)

        # Use helper to build messages
        messages = self.runner.build_messages(user_input)

        # Get tool configs
        tool_configs = self.runner.get_tool_configs()

        # Execute tool loop
        for i in range(max_calls):
            if verbose:
                print(f"[CustomDirect] Call {i + 1}")

            # Call LLM
            response = await self.runner.call_llm(messages, tool_configs)

            choice = response.choices[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])

            # Strip thinking
            content = self.runner.strip_thinking(content)

            if not tool_calls:
                # No tool calls - we're done
                messages.append({"role": "assistant", "content": content})
                return content

            # Execute tools
            tool_messages, results = await self.runner.execute_tool_loop(
                tool_calls, plan_mode
            )

            # Add to history
            messages.extend(tool_messages)

            if verbose:
                print(f"[CustomDirect] Tool results: {results}")

        return "Max calls reached"


# =============================================================================
# Example 3: ReAct Loop - using helpers
# =============================================================================


class ReActLoop(DefaultLoop):
    """ReAct pattern: Reason + Act + Observe.

    Uses helper methods to build the ReAct flow.
    """

    async def run(self, agent, user_input, max_iterations=5, **kwargs):
        plan_mode = kwargs.get("plan_mode", False)

        # Build initial messages
        messages = [{"role": "user", "content": user_input}]

        for i in range(max_iterations):
            # Get tool configs
            tools = self.runner.get_tool_configs()

            # Call LLM
            response = await self.runner.call_llm(messages, tools)
            choice = response.choices[0]
            message = choice.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                # Done - return the content
                return message.get("content", "")

            # Execute tools
            tool_msgs, results = await self.runner.execute_tool_loop(
                tool_calls, plan_mode
            )
            messages.extend(tool_msgs)

            print(f"[ReAct] Iteration {i + 1}: {len(tool_calls)} tools called")

        return "Max iterations reached"


# =============================================================================
# Example 4: Plan-Execute Loop - stub for complex planning
# =============================================================================


class PlanExecuteLoop(DefaultLoop):
    """Plan-Execute pattern: Analyze -> Execute -> Summarize."""

    async def run(self, agent, user_input, **kwargs):
        print("[PlanExecute] Analyzing task...")

        # Simple analysis - in production, this would be more sophisticated
        messages = [
            {"role": "user", "content": f"Break this task into steps: {user_input}"}
        ]

        # Get plan from LLM
        response = await self.runner.call_llm(messages, [])
        plan = response.choices[0].message.content

        print(f"[PlanExecute] Plan: {plan[:100]}...")

        # Execute normally using parent
        result = await super().run(agent, user_input, **kwargs)

        return result


# =============================================================================
# Tool for testing
# =============================================================================


@tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


async def demo():
    """Demonstrate custom loops."""
    print("=" * 60)
    print("Custom Agent Loop Examples")
    print("=" * 60)

    tools = [add_numbers, multiply]

    # Example 1: LoggingLoop
    print("\n1. LoggingLoop:")
    agent1 = Agent(
        name="logging-agent",
        instructions="You are a helpful assistant that can do math.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=tools,
        loop=LoggingLoop(),
    )

    result1 = await agent1.run("What is 5 + 3?")
    print(f"Result: {result1}")

    # Example 2: CustomDirectLoop
    print("\n2. CustomDirectLoop:")
    agent2 = Agent(
        name="custom-direct",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=tools,
        loop=CustomDirectLoop(),
    )

    result2 = await agent2.run("What is 10 + 20? Use add_numbers.")
    print(f"Result: {result2}")

    # Example 3: ReActLoop
    print("\n3. ReActLoop:")
    agent3 = Agent(
        name="react-agent",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=tools,
        loop=ReActLoop(),
    )

    result3 = await agent3.run("Calculate 3 * 4 and then add 5")
    print(f"Result: {result3}")

    # Example 4: DefaultLoop (built-in, no custom loop)
    print("\n4. DefaultLoop (built-in):")
    agent4 = Agent(
        name="default-agent",
        instructions="You are a helpful assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=tools,
        # No loop= parameter = use DefaultLoop
    )

    result4 = await agent4.run("What is 7 + 8?")
    print(f"Result: {result4}")

    # Example 5: Plan mode (works with any loop!)
    print("\n5. Plan mode (any loop):")
    agent5 = Agent(
        name="plan-agent",
        instructions="You are a helpful assistant.",
        provider="lmstudio",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234",
        api_key="dummy",
        tools=tools,
    )

    result5 = await agent5.run("What is 1 + 1?", plan_mode=True)
    print(f"Result (plan mode): {result5}")

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())
