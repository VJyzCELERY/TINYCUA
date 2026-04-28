# TINYCUA

TINYCUA - Computer-Use Agent CLI Application

## Overview

TINYCUA is a command-line interface application for computer-use AI agents. It provides an interactive REPL (Read-Eval-Print Loop) for running AI agents with tools for automation, memory management, and context handling.

## Features

- **Interactive REPL**: Command-line interface for interacting with AI agents
- **Tool System**: Built-in tools for computer use, memory, and context management
- **Backend Integration**: Connect to backend services for deployed agent workflows
- **Local Execution**: Run agents locally using an OpenAI-compatible endpoint
- **TUI Mode**: Text-based user interface for enhanced interaction

## Installation

### From PyPI

```bash
pip install tinycua
```

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/tinycua.git
cd tinycua

# Install in development mode
pip install -e .
```

## Requirements

- Python 3.12+
- tinycua-sdk (automatically installed)
- rich>=13.0.0
- prompt-toolkit>=3.0.0
- httpx>=0.27.0

### Optional Dependencies

For TUI mode:
```bash
pip install tinycua[tui]
```

For CUA (Computer Use Agent) features:
```bash
pip install tinycua[cua]
```

## Quick Start

### Basic Usage

```bash
# Start the REPL
tinycua
```

### Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
# Backend URL (optional - for deployed mode)
TINYCUA_BACKEND_URL=http://localhost:8000

# API Key (for authenticated requests)
TINYCUA_API_KEY=your-api-key

# LLM Provider
TINYCUA_PROVIDER=openai-compatible
TINYCUA_MODEL=qwen/qwen3.5-9b
TINYCUA_BASE_URL=http://localhost:1234/v1
```

### Running Agents

```python
from tinycua import Agent
from tinycua_sdk.tools import tool

@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

agent = Agent(
    name="my-agent",
    instructions="You are a helpful assistant.",
    tools=[calculate],
    provider="openai-compatible",
    base_url="http://localhost:1234/v1",
    model="qwen/qwen3.5-9b"
)

response = agent.run("What is 5 + 3?")
print(response)
```

## CLI Commands

The TINYCUA CLI provides various commands:

| Command | Description |
|---------|-------------|
| `tinycua` | Start the interactive REPL |
| `tinycua run <agent>` | Run a specific agent |
| `tinycua list` | List available agents |
| `tinycua deploy` | Deploy an agent to the backend |

## Development

### Setup

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

### Running the CLI

```bash
# From source
python -m tinycua.cli.main
```

## License

MIT License - see LICENSE file for details.