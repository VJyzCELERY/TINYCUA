"""01 - Custom Agent Loop

Shows how to subclass BaseLoop to implement custom agent behaviour.

BaseLoop provides:
  - __init__(self, max_iterations=5)  — iteration safety limit
  - self.max_iterations                — accessible in subclasses
  - self.is_cancelled (via agent)     — cancellation check

BaseLoop.run() is the extension point:
    async def run(self, agent, messages, tools) -> str

The custom loop has full control over:
  - How the LLM is called
  - How tool calls are parsed and executed
  - How many iterations happen
  - When to stop
"""

import asyncio
from typing import Any

from tinycua_sdk import Agent, LanguageModel, Tool, tool
from tinycua_sdk.agent.loop import BaseLoop


# ---------------------------------------------------------------------------
# 1. A "ReAct" loop that explicitly reasons before acting
# ---------------------------------------------------------------------------
class ReActLoop(BaseLoop):
    """ReAct-style loop: the model must reason (Think:) before acting (Act:).

    Inherits max_iterations from BaseLoop. Custom parameters (e.g., format_hint)
    are stored as instance attributes after calling super().__init__().
    """

    def __init__(
        self,
        max_iterations: int = 5,
        format_hint: str = "ReAct",
    ):
        super().__init__(max_iterations=max_iterations)
        self.format_hint = format_hint

    async def run(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        tools: list[Tool],
    ) -> str:
        # Inject ReAct formatting instructions on first turn only
        hint = self.format_hint
        if not any(
            m.get("role") == "system" and f"{hint} format" in m.get("content", "")
            for m in messages
        ):
            messages.insert(0, {
                "role": "system",
                "content": (
                    f"You must follow {hint} format. "
                    "First reason with 'Think: ...' then act with 'Act: ...'."
                ),
            })

        for iteration in range(self.max_iterations):
            if agent.is_cancelled:
                return "[cancelled]"

            response = await agent._call_llm(
                messages,
                tools=[t.to_config() for t in tools] if tools else None,
            )

            # Parse ReAct format from the response text
            if "Act:" in response:
                think_part, act_part = response.split("Act:", 1)
                action = act_part.strip()

                # If the action is a tool call (JSON), execute it
                if action.startswith("{"):
                    # Parse tool call and execute
                    import json
                    call = json.loads(action)
                    tool_name = call["name"]
                    arguments = call.get("arguments", {})

                    # Find the tool and execute
                    for t in tools:
                        if t.name == tool_name:
                            result = t.invoke(**arguments)
                            messages.append({
                                "role": "assistant",
                                "content": response,
                            })
                            messages.append({
                                "role": "tool",
                                "content": str(result),
                                "name": tool_name,
                            })
                            break
                    else:
                        return f"Unknown tool: {tool_name}"
                else:
                    # Final text answer
                    return action
            else:
                # No action needed — return the response as-is
                return response

        return "[max iterations reached]"


# ---------------------------------------------------------------------------
# 2. A "Step-by-Step" loop that forces the model to plan first
# ---------------------------------------------------------------------------
class PlanThenExecuteLoop(BaseLoop):
    """Two-phase loop: planning phase, then execution phase.

    Demonstrates a custom loop with its own parameter (plan_temperature)
    while still inheriting max_iterations from BaseLoop.
    """

    def __init__(
        self,
        max_iterations: int = 5,
        plan_temperature: float = 0.3,
    ):
        super().__init__(max_iterations=max_iterations)
        self.plan_temperature = plan_temperature

    async def run(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        tools: list[Tool],
    ) -> str:
        # Phase 1 — Ask the model for a plan
        plan_messages = messages + [{
            "role": "system",
            "content": "First, outline a step-by-step plan. Do not execute yet.",
        }]
        # Use a lower temperature for planning (more deterministic)
        original_temp = agent.llm_model.temperature
        agent.llm_model = agent.llm_model.model_copy(
            update={"temperature": self.plan_temperature}
        )
        plan = await agent._call_llm(plan_messages)
        # Restore original temperature
        agent.llm_model = agent.llm_model.model_copy(
            update={"temperature": original_temp}
        )

        # Phase 2 — Execute the plan
        exec_messages = messages + [
            {"role": "assistant", "content": plan},
            {
                "role": "system",
                "content": "Now execute the plan above step by step.",
            },
        ]

        # Run the standard loop but with the plan as context
        for _ in range(self.max_iterations):
            if agent.is_cancelled:
                return "[cancelled]"

            response = await agent._call_llm(
                exec_messages,
                tools=[t.to_config() for t in tools] if tools else None,
            )

            # Simple tool parsing (in reality you'd parse OpenAI tool_calls format)
            exec_messages.append({"role": "assistant", "content": response})

            # If no tool calls detected, we're done
            if not self._has_tool_call(response):
                return response

            # Otherwise, the base class logic would handle tool execution
            # For this example we return the raw response
            return response

        return "[max iterations reached]"

    def _has_tool_call(self, text: str) -> bool:
        return "function" in text.lower() or "tool" in text.lower()


# ---------------------------------------------------------------------------
# 3. Usage
# ---------------------------------------------------------------------------
@tool
def weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny in {city}."


async def main() -> None:
    # Agent with the custom ReAct loop
    react_agent = Agent(
        name="react_assistant",
        instructions="You are a reasoning assistant.",
        llm_model=LanguageModel(
            provider="openai-compatible",
            model_name="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        ),
        tools=[weather],
        loop=ReActLoop(max_iterations=5, format_hint="ReAct"),
    )

    response = await react_agent.run("What is the weather in Tokyo?")
    print("ReAct response:", response)

    # Agent with the plan-then-execute loop
    plan_agent = Agent(
        name="planner",
        instructions="You are a methodical planner.",
        llm_model=LanguageModel(model_name="qwen/qwen3.5-9b"),
        loop=PlanThenExecuteLoop(max_iterations=3, plan_temperature=0.2),
    )

    response = await plan_agent.run("How do I bake sourdough bread?")
    print("Plan response:", response)


if __name__ == "__main__":
    asyncio.run(main())
