# Agent Configuration

**Prerequisites**: [Your First Agent](./your-first-agent.md) — you know how to
create and run a basic agent.

## Overview

The SDK provides two configuration classes:

- **`AgentConfig`** — A mutable Pydantic model mirroring every `Agent` field.
  Build, serialize, and share configurations without instantiating agents.
- **`AgentPolicy`** — Controls runtime behavior: maximum tool calls and parallel
  execution.

This page covers constructing agents from config objects, serializing to JSON
and YAML, and tuning policies.

## AgentConfig

### Building from Config

```python
import os

from tinycua_sdk import Agent, AgentConfig, LanguageModel

config = AgentConfig(
    name="my-agent",
    instructions="You are a helpful coding assistant.",
    llm_model=LanguageModel(
        provider="openai-responses",
        model_name="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key=os.environ.get("OPENAI_API_KEY"),
    ),
)

agent = Agent.from_config(config.to_config())
```

For local development with a local LLM server:

```python
from tinycua_sdk import Agent, AgentConfig, LanguageModel

config = AgentConfig(
    name="local-agent",
    instructions="You are a local coding assistant.",
    llm_model=LanguageModel(
        provider="openai-compatible",
        model_name="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
    ),
)

agent = Agent.from_config(config.to_config())
```

### Extracting Config from an Existing Agent

```python
import os

from tinycua_sdk import Agent, LanguageModel

agent = Agent(
    name="inspectable-agent",
    instructions="You help with data analysis.",
    llm_model=LanguageModel(
        provider="openai-responses",
        model_name="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key=os.environ.get("OPENAI_API_KEY"),
    ),
)

config = agent.to_config()

print(f"Name: {config['name']}")
print(f"Instructions: {config['instructions']}")
print(f"Provider: {config['llm_model']['provider']}")
print(f"Model: {config['llm_model']['model_name']}")

# Modify and recreate
config["instructions"] = "You help with code reviews."
new_agent = Agent.from_config(config)
```

## AgentPolicy

```python
from tinycua_sdk import AgentPolicy

policy = AgentPolicy(
    max_tool_calls=5,
    parallel_tool_calls=False,
)
```

| Field | Type | Default | Description |
|---|---|---|---|
| `max_tool_calls` | `int` | 10 | Maximum tool-call iterations per `run()` |
| `parallel_tool_calls` | `bool` | `True` | Whether multiple tools can execute concurrently |

> **Parallel vs sequential execution**: When `parallel_tool_calls=True` (default),
> the SDK runs all tool calls from a single LLM response at the same time.
> This is faster but can cause race conditions when tool outputs depend on each
> other. Set to `False` to run tools one at a time in order — use this when tool
> B needs the output of tool A.

Attach a policy when constructing:

```python
import os

from tinycua_sdk import Agent, AgentConfig, AgentPolicy, LanguageModel

policy = AgentPolicy(max_tool_calls=3, parallel_tool_calls=False)

config = AgentConfig(
    name="safe-agent",
    instructions="You are a cautious assistant.",
    llm_model=LanguageModel(
        provider="openai-responses",
        model_name="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key=os.environ.get("OPENAI_API_KEY"),
    ),
    policy=policy,
)

agent = Agent.from_config(config.to_config())
```

## JSON Serialization

Serialize an agent to JSON:

```python
import os

from tinycua_sdk import Agent, LanguageModel

agent = Agent(
    name="serializable-agent",
    instructions="You help with data analysis.",
    llm_model=LanguageModel(
        provider="openai-responses",
        model_name="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key=os.environ.get("OPENAI_API_KEY"),
    ),
)

json_str = agent.to_json()

with open("tmp/agent_config.json", "w") as f:
    f.write(json_str)
```

`to_json()` redacts sensitive fields by default. To include API keys:

```python
json_str = agent.to_json(redact_sensitive=False)
```

Load from a JSON file:

```python
from tinycua_sdk import Agent

agent = Agent.from_json_file("path/to/agent_config.json")

print(f"Loaded agent: {agent.name}")
```

## YAML Serialization

```python
import os

from tinycua_sdk import Agent, LanguageModel

agent = Agent(
    name="yaml-agent",
    instructions="You help with data analysis.",
    llm_model=LanguageModel(
        provider="openai-responses",
        model_name="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key=os.environ.get("OPENAI_API_KEY"),
    ),
)

yaml_str = agent.to_yaml()

with open("tmp/agent_config.yaml", "w") as f:
    f.write(yaml_str)
```

Load from a YAML file:

```python
from tinycua_sdk import Agent

agent = Agent.from_yaml_file("path/to/agent_config.yaml")

print(f"Loaded agent: {agent.name}")
```

Like `to_json()`, `to_yaml()` accepts `redact_sensitive=True` (default).

## Common Pitfalls

**Serializing sensitive keys**. `to_json()` and `to_yaml()` redact `api_key` by
default. With `redact_sensitive=False`, the output contains your raw key. Never
commit these files to version control.

**Modifying config after agent creation**. Changes to `AgentConfig` do not
retroactively affect agents created from it. Call `Agent.from_config()` again
after mutating a config.

**YAML dependency**. `to_yaml` and `from_yaml_file` require `pyyaml`. If
missing, install it with `pip install pyyaml` or use JSON instead.

## Next Steps

- **[Language Models and Providers](../core-concepts/language-models-and-providers.md)** —
  Deep dive into model parameters and provider selection.

## See Also

- **[Creating Tools](../agent-extensions/creating-tools.md)** — Define custom
  tools for your agents.