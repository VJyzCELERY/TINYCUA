"""Target 2.1: Create a minimal Agent with no arguments."""

from tinycua_sdk import Agent


a = Agent()

assert a.name == "assistant"
assert a.instructions == ""
assert a.llm_model.model_name == "gpt-4o-mini"
assert len(a.tools) == 0
assert len(a.skills) == 0
print("PASS")
