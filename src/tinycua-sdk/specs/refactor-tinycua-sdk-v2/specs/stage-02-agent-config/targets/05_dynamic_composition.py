"""Target 2.6: Verify tools and skills can be added after creation."""

from tinycua_sdk import Agent, Skill, tool


@tool
def calc(expr: str) -> str:
    """Evaluate expression."""
    return str(eval(expr))


s = Skill(name="math", description="Math help", instructions="Show work.")

a = Agent()
assert len(a.tools) == 0
assert len(a.skills) == 0

a.add_tools(calc)
a.add_skills(s)

assert len(a.tools) == 1
assert a.tools[0].name == "calc"
assert len(a.skills) == 1
assert a.skills[0].name == "math"

# Test list input
@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


s2 = Skill(name="testing", description="Write tests", instructions="Cover edge cases.")
a.add_tools([add])
a.add_skills([s2])

assert len(a.tools) == 2
assert len(a.skills) == 2
print("PASS")
