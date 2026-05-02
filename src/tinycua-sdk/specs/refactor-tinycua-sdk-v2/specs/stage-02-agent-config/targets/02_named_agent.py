"""Target 2.2: Create a named agent with custom instructions and model."""

from tinycua_sdk import Agent, LanguageModel


a = Agent(
    name="greeter",
    instructions="You are a friendly greeter.",
    llm_model=LanguageModel(
        provider="openai-compatible",
        model_name="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
        api_key="dummy",
    ),
)

assert a.name == "greeter"
assert a.instructions == "You are a friendly greeter."
assert a.llm_model.model_name == "qwen/qwen3.5-9b"
print("PASS")
