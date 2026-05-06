"""Target 2.7: Verify to_config() captures all fields."""

from tinycua_sdk import Agent, LanguageModel, Skill, tool


@tool
def calc(expr: str) -> str:
    """Evaluate expression."""
    return str(eval(expr))


s = Skill(name="math", description="Math help", instructions="Show work.")

a = Agent(
    name="tutor",
    instructions="Be patient.",
    llm_model=LanguageModel(model_name="test-model", temperature=0.2),
    tools=[calc],
    skills=[s],
)

config = a.to_config()

assert config["name"] == "tutor"
assert config["instructions"] == "Be patient."
assert config["llm_model"]["model_name"] == "test-model"
assert config["llm_model"]["temperature"] == 0.2
assert len(config["tools"]) == 1
assert config["tools"][0]["function"]["name"] == "calc"
assert len(config["skills"]) == 1
assert config["skills"][0]["name"] == "math"
assert "tool_permissions" in config
assert config["tool_permissions"] == {}
print("PASS")
