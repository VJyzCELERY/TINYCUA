# Agent Creation Kit Guide

The Agent Creation Kit provides flexible ways to create and configure agents using declarative configuration files. This guide covers the AGENT.md format, CLI usage, and programmatic APIs.

## Quick Start

### Create an AGENT.md File

```yaml
---
name: my-agent
description: A helpful coding assistant
model: gpt-4o-mini
provider: openai
---

# Instructions
You are a helpful coding assistant that helps users write and debug code.
```

### Load via CLI

```bash
tinycua agent create path/to/AGENT.md
```

### Load via Python

```python
from tinycua_sdk.agent.loader import AgentLoader
from pathlib import Path

loader = AgentLoader()
config = loader.load_from_markdown(Path("path/to/AGENT.md"))
```

## AGENT.md Format

The AGENT.md format uses YAML frontmatter for configuration and Markdown for agent instructions.

### YAML Frontmatter Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | (filename) | Agent name |
| `description` | string | No | - | Agent description |
| `model` | string | No | gpt-5-nano | LLM model to use |
| `provider` | string | No | openai | LLM provider |
| `base_url` | string | No | - | Custom API endpoint |
| `api_key` | string | No | - | API key (use env vars!) |
| `tools` | list[string] | No | [] | Tool names to enable |
| `skills` | list[string] | No | [] | Skills to load |
| `skill_dirs` | list[string] | No | [] | Directories to search for skills |
| `auto_load_dependencies` | boolean | No | true | Auto-load skill dependencies |
| `loop` | dict | No | default | Loop configuration |
| `policy` | dict | No | - | Policy settings |
| `system_prompt` | string | No | "You are a helpful assistant." | System prompt override |

### Complete Example

```yaml
---
name: code-assistant
description: An expert programmer agent
model: gpt-4o-mini
provider: openai
tools:
  - bash
  - read_file
  - write_file
skills:
  - code_analysis
skill_dirs:
  - ./skills
auto_load_dependencies: true
loop:
  type: default
  max_iterations: 10
policy:
  max_tool_calls: 15
  parallel_tool_calls: true
  temperature: 0.7
system_prompt: You are an expert programmer who excels at writing clean, efficient code.
---

# Instructions
You are an expert programmer. You analyze requirements carefully and provide well-structured solutions.
Always explain your reasoning and include comments in your code.
```

### Markdown Instructions Section

The content after the YAML frontmatter serves as the agent's instructions. You can use Markdown formatting:

```yaml
---
name: my-agent
---

# Agent Instructions

You are a helpful assistant with the following capabilities:

## Core Abilities
- Answer questions
- Help with coding tasks
- Provide explanations

## Guidelines
- Be concise and clear
- Use examples when helpful
- Ask clarifying questions when needed
```

## Tool Configuration

### Using Built-in Tools

```yaml
---
name: tool-agent
tools:
  - bash
  - read_file
  - write_file
  - list_directory
---

You are an agent with file system access.
```

### MCP Tools

```yaml
---
name: mcp-agent
tools:
  - mcp:filesystem
  - mcp:github
---

# Instructions
You can access the file system and GitHub.
```

## Skill Integration

Skills provide modular tool packages. See [Skills](skills.md) for details.

```yaml
---
name: skill-agent
skills:
  - code_analysis
  - web_scraper
skill_dirs:
  - ./skills
  - ~/.tinycua/skills
---

# Instructions
You have access to code analysis and web scraping tools.
```

## Loop Types

The loop type determines how the agent processes tool calls and reasoning.

### Default Loop

```yaml
---
name: default-agent
loop:
  type: default
---

Standard tool loop for simple tasks.
```

### React Loop

```yaml
---
name: react-agent
loop:
  type: react
---

Reasoning loop for complex tasks requiring thought-action-observation cycles.
```

### Plan Loop

```yaml
---
name: plan-agent
loop:
  type: plan
---

Planning loop for complex tasks requiring plan-then-execute pattern.
```

### Custom Loop

```yaml
---
name: custom-loop-agent
loop:
  type: custom
  class_name: MyCustomLoop
  source: |
    class MyCustomLoop(DefaultLoop):
        async def process(self, ...):
            # Custom implementation
            pass
---

Agent with custom loop implementation.
```

## Templates

Templates provide pre-configured agent setups for common use cases.

### Available Templates

| Template | Description | Best For |
|----------|-------------|----------|
| `coder` | Code generation and debugging | Technical tasks |
| `researcher` | Research and information gathering | Research tasks |
| `assistant` | General-purpose helper | General assistance |

### Using Templates

```bash
# Create from template
tinycua agent create --template coder

# Create with overrides
tinycua agent create --template coder --model gpt-4o

# List available templates
tinycua agent templates
```

### Programmatic Template Usage

```python
from tinycua_sdk import Agent

# Create from template
agent = Agent.from_template("coder")

# Create with overrides
agent = Agent.from_template("researcher", overrides={
    "model": "gpt-4o",
    "policy": {"temperature": 0.3}
})
```

## JSON Configuration

You can also define agents using JSON configuration.

### JSON Format

```json
{
  "name": "json-agent",
  "instructions": "You are a helpful assistant.",
  "model": "gpt-4o-mini",
  "provider": "openai",
  "tools": ["bash", "read_file"],
  "skills": ["code_analysis"],
  "loop": {
    "type": "default"
  },
  "policy": {
    "max_tool_calls": 10,
    "temperature": 1.0
  }
}
```

### Loading JSON

```python
from tinycua_sdk.agent.config import AgentConfig

# From file
config = AgentConfig.from_json_file(Path("agent.json"))

# From string
config = AgentConfig.from_json('{"name": "test", "instructions": "Helpful."}')

# From dict
config = AgentConfig.from_json({"name": "test", "instructions": "Helpful."})
```

### Environment Variable Substitution

```json
{
  "name": "env-agent",
  "api_key": "${TINYCUA_API_KEY}",
  "base_url": "${TINYCUA_BASE_URL}"
}
```

## CLI Usage

### Create Agent from AGENT.md

```bash
tinycua agent create path/to/AGENT.md
```

### Create Agent from Template

```bash
tinycua agent create --template coder
tinycua agent create --template researcher
tinycua agent create --template assistant
```

### Create with CLI Overrides

```bash
tinycua agent create --template coder --model gpt-4o --provider openai
tinycua agent create --template researcher --temperature 0.5
```

### Create with Override File

```bash
tinycua agent create --template coder --override-file overrides.json
tinycua agent create --template coder --override-file overrides.yaml
```

### List Templates

```bash
tinycua agent templates
tinycua agent templates --verbose
```

### Show Agent Info

```bash
tinycua agent info --file path/to/AGENT.md
tinycua agent info --template coder
```

## Programmatic Usage

### Loading from AGENT.md

```python
from tinycua_sdk.agent.loader import AgentLoader
from pathlib import Path

loader = AgentLoader()

# Load from file
config = loader.load_from_markdown(Path("path/to/AGENT.md"))

# Load from directory (looks for AGENT.md)
config = loader.load_from_markdown(Path("path/to/agent-dir"))
```

### Creating Agent from Config

```python
from tinycua_sdk import Agent
from tinycua_sdk.agent.config import AgentConfig

# Create config
config = AgentConfig(
    name="my-agent",
    instructions="You are a helpful assistant.",
    model="gpt-4o-mini",
    tools=["bash", "read_file"]
)

# Create agent
agent = Agent(config)
```

### Using Templates

```python
from tinycua_sdk import Agent

# Simple template
agent = Agent.from_template("coder")

# With overrides
agent = Agent.from_template("researcher", overrides={
    "model": "gpt-4o",
    "tools": ["search_web", "read_file"],
    "policy": {"temperature": 0.5}
})
```

## Error Handling

### Common Errors

#### AgentNotFoundError

```python
from tinycua_sdk.agent.loader import AgentLoader, AgentNotFoundError

loader = AgentLoader()
try:
    config = loader.load_from_markdown(Path("nonexistent.md"))
except AgentNotFoundError as e:
    print(f"Agent file not found: {e}")
```

#### AgentParseError

```python
from tinycua_sdk.agent.loader import AgentLoader, AgentParseError

loader = AgentLoader()
try:
    config = loader.load_from_markdown(Path("invalid.md"))
except AgentParseError as e:
    print(f"Failed to parse AGENT.md: {e}")
```

#### Path Validation

```python
from pathlib import Path

# Directory traversal is blocked
try:
    path = Path("../etc/passwd")
    # Validation happens in loader
except ValueError as e:
    print(f"Invalid path: {e}")
```

## Best Practices

### When to Use Each Method

| Method | Use Case |
|--------|----------|
| AGENT.md | Declarative, version-controlled agent definitions |
| JSON | OpenCode compatibility, configuration files |
| Python/Programmatic | Complex dynamic configurations, testing |

### Template Selection

- **coder**: For code generation, debugging, technical tasks
- **researcher**: For research, information gathering, analysis
- **assistant**: For general-purpose help, Q&A

### Skill Integration

1. Start with minimal skills, add as needed
2. Use `skill_dirs` for custom skill locations
3. Be aware of conditional activation based on available tools
4. Use `auto_load_dependencies: true` for automatic dependency loading

### Loop Type Selection

- **default**: Standard tool loop for most use cases
- **react**: For reasoning-heavy tasks requiring thought-action observation
- **plan**: For complex tasks requiring planning before execution

### Security Considerations

1. **Never commit API keys**: Use environment variables
2. **Validate AGENT.md files**: Before loading from untrusted sources
3. **Path validation**: The loader prevents directory traversal attacks
4. **Use placeholder values**: In examples, use placeholder API keys

```yaml
---
# Good: Use environment variables
api_key: ${TINYCUA_API_KEY}

# Good: Leave blank for user to set
api_key: ""

# Avoid: Hardcoded keys
api_key: "sk-1234567890abcdef"
---
```

## Examples

See the following examples in `docs/examples/config-based/`:

- [basic-agent.md](../examples/config-based/basic-agent.md) - Minimal agent configuration
- [agent-with-tools.md](../examples/config-based/agent-with-tools.md) - Agent with tool references
- [agent-with-skills.md](../examples/config-based/agent-with-skills.md) - Agent with skill integration
- [agent-with-custom-loop.md](../examples/config-based/agent-with-custom-loop.md) - Custom loop configuration
- [template-coder.md](../examples/config-based/template-coder.md) - Template-based coder agent
- [template-researcher.md](../examples/config-based/template-researcher.md) - Template-based researcher agent
- [json-config.json](../examples/config-based/json-config.json) - JSON configuration example

## Related Documentation

- [Skills](skills.md) - Skill system and integration
- [Context Management](context-management.md) - Context handling
- [Middleware](middleware.md) - Middleware and hooks
- [Agent Development](agent-development.md) - Basic agent development