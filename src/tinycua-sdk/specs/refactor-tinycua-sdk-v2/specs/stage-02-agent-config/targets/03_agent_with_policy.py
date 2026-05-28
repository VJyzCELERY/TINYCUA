"""Target 2.3: Create an agent with custom policy settings."""

from tinycua_sdk import Agent, AgentPolicy


a = Agent(
    name="researcher",
    instructions="Cite your sources.",
    policy=AgentPolicy(max_tool_calls=15, parallel_tool_calls=True),
)

assert a.policy.max_tool_calls == 15
assert a.policy.parallel_tool_calls is True
print("PASS")
