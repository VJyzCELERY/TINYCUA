"""02 - Agent Creation

Shows how to create an Agent with different levels of configuration.
An Agent is stateless and fully runnable once configured.
"""

from tinycua_sdk import Agent, LanguageModel

# ---------------------------------------------------------------------------
# 1. Absolute minimal agent (still requires a LanguageModel)
# ---------------------------------------------------------------------------
agent = Agent(
    llm_model=LanguageModel(),
)

# ---------------------------------------------------------------------------
# 2. Agent with a custom name and instructions
# ---------------------------------------------------------------------------
greeter = Agent(
    name="greeter",
    instructions="You are a friendly greeter. Always say hello in the user's language.",
    llm_model=LanguageModel(
        provider="openai-compatible",
        base_url="http://localhost:1234/v1",
    ),
)

# ---------------------------------------------------------------------------
# 3. Agent with a specific language model
# ---------------------------------------------------------------------------
coder = Agent(
    name="coder",
    instructions=(
        "You are an expert Python programmer. "
        "Write clean, typed, well-documented code."
    ),
    llm_model=LanguageModel(
        provider="openai-compatible",
        model_name="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
        temperature=0.2,
        max_tokens=4096,
    ),
)

# ---------------------------------------------------------------------------
# 4. Agent with behavioral policy
# ---------------------------------------------------------------------------
researcher = Agent(
    name="researcher",
    instructions="You are a careful research assistant. Cite your sources.",
    llm_model=LanguageModel(temperature=0.3),
    policy={
        "max_tool_calls": 15,
        "parallel_tool_calls": True,
    },
)

# ---------------------------------------------------------------------------
# 5. Agent with metadata (consumer-defined extensibility)
# ---------------------------------------------------------------------------
tagged_agent = Agent(
    name="tagged_assistant",
    instructions="Help the user.",
    llm_model=LanguageModel(
        provider="openai-compatible",
        model_name="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
        api_key="dummy",
    ),
    metadata={
        "team": "platform",
        "cost_center": "eng-123",
        "version": "2.1.0",
    },
)

if __name__ == "__main__":
    print("Agents created:")
    for a in (agent, greeter, coder, researcher, tagged_agent):
        print(f"  - {a.name}: model={a.llm_model.model_name}")
