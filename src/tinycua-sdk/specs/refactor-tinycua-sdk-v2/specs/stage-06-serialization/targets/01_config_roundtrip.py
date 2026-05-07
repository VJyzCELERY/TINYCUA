"""Target 6.1: Verify to_config/from_dict round-trip preserves all fields."""

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
assert config["llm_model"]["model_name"] == "test-model"
assert config["llm_model"]["temperature"] == 0.2
assert len(config["tools"]) == 1
assert len(config["skills"]) == 1

# Reconstruct from dict (note: loaded tools have no callable)
a2 = Agent.from_dict(config)
assert a2.name == "tutor"
assert a2.llm_model.model_name == "test-model"
assert a2.llm_model.temperature == 0.2
print("PASS")
