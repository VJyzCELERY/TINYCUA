# Basic Agent Example

```python
"""Basic agent example."""

from tinycua_sdk import Agent

def main():
    # Create an agent with basic configuration
    agent = Agent(
        name="hello-agent",
        instructions="You are a friendly assistant that greets users.",
        model="gpt-4o-mini",
    )

    # Run the agent
    response = agent.run("Hello! What's your name?")
    print(f"Agent: {response}")


if __name__ == "__main__":
    main()
```
