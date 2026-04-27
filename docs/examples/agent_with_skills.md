# Agent with Skills Example

```python
"""Agent with skills example."""

from tinycua_sdk import Agent
from tinycua_sdk.skills import skill

# Define a custom skill
@skill(name="calculator", description="Mathematical operations")
class CalculatorSkill:
    """Skill for performing calculations."""
    
    @staticmethod
    def get_tools():
        from tinycua_sdk.tools import tool
        
        @tool(name="add", description="Add two numbers")
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b
        
        @tool(name="multiply", description="Multiply two numbers")
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b
        
        return [add, multiply]


def main():
    # Create agent with skills
    agent = Agent(
        name="math-agent",
        instructions="You are a math assistant. Use the available tools for calculations.",
        model="gpt-4o-mini",
        skills=[CalculatorSkill()],
    )

    # Run with tool usage
    response = agent.run("What is 5 + 3?")
    print(f"Agent: {response}")


if __name__ == "__main__":
    main()
```
