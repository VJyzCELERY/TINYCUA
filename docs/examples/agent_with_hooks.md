# Agent with Hooks Example

```python
"""Agent with hooks example."""

import logging
from tinycua_sdk import Agent
from tinycua_sdk.middleware import Hook

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define hooks
@Hook(name="log_pre_run", event="pre_run")
def log_pre_run(agent, user_input):
    """Log before running."""
    logger.info(f"Agent '{agent.name}' running with input: {user_input[:50]}...")
    return {"continue": True}


@Hook(name="log_post_run", event="post_run")
def log_post_run(agent, user_input, response):
    """Log after running."""
    logger.info(f"Agent '{agent.name}' completed. Response: {response[:50]}...")
    return {"continue": True}


@Hook(name="log_error", event="on_error")
def log_error(agent, user_input, error):
    """Log errors."""
    logger.error(f"Agent '{agent.name}' error: {error}")
    return {"continue": True}


def main():
    # Create agent with hooks
    agent = Agent(
        name="logged-agent",
        instructions="You are a helpful assistant.",
        model="gpt-4o-mini",
        hooks=[log_pre_run, log_post_run, log_error],
    )

    # Run the agent
    response = agent.run("Hello!")
    print(f"Agent: {response}")


if __name__ == "__main__":
    main()
```
