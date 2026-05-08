"""Target 3.5: Verify agent with tools correctly invokes them."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "qwen/qwen3.5-9b"


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression, {"__builtins__": {}}, {}))


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
        tools=[calculator],
        instructions="You have access to a calculator. Use it for math.",
    )

    response = await a.run("What is 135 * 42?", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
