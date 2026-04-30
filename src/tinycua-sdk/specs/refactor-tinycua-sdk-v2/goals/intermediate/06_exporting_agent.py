"""06 - Exporting Agent

Shows how to serialize an agent configuration to JSON or YAML.
This is useful for versioning, sharing, or deploying agents.
"""

from pathlib import Path

from tinycua_sdk import Agent, LanguageModel, Skill, tool


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    return str(eval(expression, {"__builtins__": {}}, {}))


research_skill = Skill(
    name="math_helper",
    description="Assist with math problems.",
    instructions="Always show your work step by step.",
)

agent = Agent(
    name="math_tutor",
    instructions="You are a patient math tutor.",
    llm_model=LanguageModel(
        provider="openai-compatible",
        model_name="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
        temperature=0.2,
    ),
    tools=[calculator],
    skills=[research_skill],
)

# ---------------------------------------------------------------------------
# 1. Export to a Python dict
# ---------------------------------------------------------------------------
config_dict = agent.to_config()
print("Config keys:", list(config_dict.keys()))

# ---------------------------------------------------------------------------
# 2. Export to JSON (with optional redaction of secrets)
# ---------------------------------------------------------------------------
json_output = agent.to_json(indent=2, redact_sensitive=True)
print("\nJSON snippet:\n", json_output[:300])

Path("exported_agent.json").write_text(agent.to_json())

# ---------------------------------------------------------------------------
# 3. Export to YAML
# ---------------------------------------------------------------------------
Path("exported_agent.yaml").write_text(agent.to_yaml(redact_sensitive=True))

# ---------------------------------------------------------------------------
# 4. Export with metadata for deployment
# ---------------------------------------------------------------------------
deployment_bundle = agent.to_config()
deployment_bundle["metadata"] = {
    "created_by": "alice@example.com",
    "version": "1.0.0",
    "environment": "staging",
}

if __name__ == "__main__":
    print("\nAgent exported to exported_agent.json and exported_agent.yaml")
