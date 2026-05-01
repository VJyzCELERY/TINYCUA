"""03 - Agent with Tools

Shows how to attach tools to an agent so the LLM can invoke them during a run.
"""

import asyncio

from tinycua_sdk import Agent, LanguageModel, tool


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression, {"__builtins__": {}}, {}))


@tool
def get_current_user() -> str:
    """Return the name of the current user."""
    return "Alice"


async def main() -> None:
    agent = Agent(
        name="math_assistant",
        instructions="You have access to a calculator. Use it for math.",
        llm_model=LanguageModel(
            provider="openai-compatible",
            model_name="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        ),
        tools=[calculator, get_current_user],
    )

    # The agent loop will:
    #   1. Call the LLM with the calculator schema
    #   2. If the LLM requests a tool_call, execute it via ToolExecutor
    #   3. Append the result back to the message history
    #   4. Re-call the LLM with updated context
    #   5. Return the final text response

    response = await agent.run("What is 135 * 42?")
    print("Response:", response)

    # -----------------------------------------------------------------------
    # Adding tools dynamically after creation
    # -----------------------------------------------------------------------
    @tool
    def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
        """Convert an amount between currencies."""
        rates = {"USD": 1.0, "EUR": 0.92, "JPY": 150.0}
        usd = amount / rates[from_currency.upper()]
        result = usd * rates[to_currency.upper()]
        return f"{amount} {from_currency.upper()} = {result:.2f} {to_currency.upper()}"

    agent.add_tools(convert_currency)

    response = await agent.run("Convert 100 USD to EUR.")
    print("After adding tool:", response)


if __name__ == "__main__":
    asyncio.run(main())
