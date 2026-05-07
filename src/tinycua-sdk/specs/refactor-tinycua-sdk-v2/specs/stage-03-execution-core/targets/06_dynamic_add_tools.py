"""Target 3.6: Verify tools added after creation work on next run."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool


BASE_URL = "http://localhost:1234/v1"
API_KEY = "dummy"
MODEL_NAME = "unsloth/qwen3.6-35b-a3b"


@tool
def convert_currency(amount: float, from_c: str, to_c: str) -> str:
    """Convert currency."""
    rates = {"USD": 1.0, "EUR": 0.92}
    usd = amount / rates[from_c]
    return f"{usd * rates[to_c]:.2f}"


async def main():
    a = Agent(
        llm_model=LanguageModel(
            base_url=BASE_URL, api_key=API_KEY, model_name=MODEL_NAME,
        ),
    )

    # Add tool after creation
    a.add_tools(convert_currency)

    response = await a.run("Convert 100 USD to EUR.", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
