# TINYCUA SDK

Developer SDK and integration libraries for the TINYCUA project.

## Folder Structure

```
tinycua-sdk/
├── docs/                      # Documentation directory
├── tinycua_sdk/               # Source code
├── tests/                     # Testing files
│   └── e2e/                   # End-to-end tests
├── specs/                     # Specifications and design docs
├── pyproject.toml             # Configuration for Python tooling
├── Makefile                   # Build and task automation
└── README.md                  # Subproject overview
```

## Setup Instructions

1. Create a virtual environment:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```
   make install
   ```
3. Copy and configure environment:
   ```
   cp .env.example .env
   # Edit .env with your values
   ```

---

## Configuration (.env)

Copy `.env.example` to `.env` and configure:

```bash
# OpenAI-compatible endpoint (for local execution)
TINYCUA_PROVIDER=openai-compatible
TINYCUA_MODEL=qwen/qwen3.5-9b
TINYCUA_BASE_URL=http://localhost:1234/v1
```

---

## Usage Examples

### Local Execution (No Backend)

Run agents directly on your machine using an OpenAI-compatible endpoint:

```python
from tinycua_sdk import Agent
from tinycua_sdk.tools import tool

@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

agent = Agent(
    name="math-agent",
    instructions="You are a helpful math assistant that uses tools.",
    tools=[calculate],
    provider="openai-compatible",
    base_url="http://127.0.0.1:1234/v1",
    model="qwen/qwen3.5-9b"
)

# Run locally - no backend required
response = agent.run("What is 5 + 3? Use the add_numbers tool.")
print(response)
```

## Examples

The SDK includes example scripts in the `examples/` directory:

| Example | Description |
|---------|-------------|
| `01_agent_basic.py` | Basic agent with tools, local execution |
| `02_agent_streaming.py` | Streaming responses with tools |
| `05_agent_hierarchy.py` | Agent hierarchies and sub-agents |
| `10_custom_loop.py` | Custom loop implementation |
| `12_skills_example.py` | Skills and toolsets |

### Running Examples

```bash
# Local execution (no backend)
cd src/tinycua-sdk
python examples/01_agent_basic.py
```

---

## Development Commands

```bash
# Install dependencies
make install

# Run tests
make test

```
