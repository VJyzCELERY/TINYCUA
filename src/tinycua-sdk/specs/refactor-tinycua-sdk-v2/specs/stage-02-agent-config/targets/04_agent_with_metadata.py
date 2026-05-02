"""Target 2.4: Create an agent with consumer-defined metadata."""

from tinycua_sdk import Agent


a = Agent(
    name="tagged_assistant",
    instructions="Help the user.",
    metadata={
        "team": "platform",
        "cost_center": "eng-123",
        "version": "2.1.0",
    },
)

assert a.metadata["team"] == "platform"
assert a.metadata["cost_center"] == "eng-123"
print("PASS")
