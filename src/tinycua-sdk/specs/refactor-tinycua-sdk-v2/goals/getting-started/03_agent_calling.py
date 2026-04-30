"""03 - Agent Calling

Shows how to run an agent with a user query and retrieve the final response.
All execution is async — the consumer handles the event loop.
"""

import asyncio

from tinycua_sdk import Agent, LanguageModel


async def main() -> None:
    agent = Agent(
        name="assistant",
        instructions="You are a helpful assistant.",
        llm_model=LanguageModel(
            provider="openai-compatible",
            base_url="http://localhost:1234/v1",
            temperature=0.7,
        ),
    )

    # -----------------------------------------------------------------------
    # 1. Simple text query (stream="off" is the default)
    # -----------------------------------------------------------------------
    response: str = await agent.run("What is the capital of France?")
    print("Response:", response)

    # -----------------------------------------------------------------------
    # 2. Explicit non-streaming call
    # -----------------------------------------------------------------------
    response = await agent.run(
        "Explain quantum computing in one sentence.",
        stream="off",
    )
    print("One-liner:", response)

    # -----------------------------------------------------------------------
    # 3. Query with prior message history
    # -----------------------------------------------------------------------
    history = [
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Nice to meet you, Alice!"},
    ]
    response = await agent.run(
        "What is my name?",
        messages=history,
    )
    print("With history:", response)

    # -----------------------------------------------------------------------
    # 4. Runtime instruction override
    # -----------------------------------------------------------------------
    response = await agent.run(
        "Tell me a joke.",
        instructions="You are a stand-up comedian. Be funny and concise.",
    )
    print("Override:", response)

    # -----------------------------------------------------------------------
    # 5. Cancellation support
    # -----------------------------------------------------------------------
    task = asyncio.create_task(
        agent.run("Write a very long essay about the history of cheese.")
    )
    await asyncio.sleep(0.5)
    agent.cancel()  # Signals the loop to stop after the current iteration
    try:
        response = await task
        print("Cancelled response:", response)
    except asyncio.CancelledError:
        print("Agent run was cancelled.")


if __name__ == "__main__":
    asyncio.run(main())
