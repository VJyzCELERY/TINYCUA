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
import asyncio
from tinycua_sdk import Agent, LanguageModel, tool

@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b

async def main():
    agent = Agent(
        name="math-agent",
        instructions="You are a helpful math assistant that uses tools.",
        llm_model=LanguageModel(
            provider="openai-compatible",
            base_url="http://127.0.0.1:1234/v1",
            model_name="qwen/qwen3.5-9b",
        ),
    )
    agent.add_tools(calculate)

    # Run locally - no backend required
    response = await agent.run("What is 5 + 3? Use the calculate tool.")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

## Examples

The SDK includes example scripts in the `docs/examples/` directory:

| Example | Description |
|---------|-------------|
| `01_basic_agent.py` | Basic agent with LanguageModel |
| `02_tools.py` | Agent with `@tool` decorator and `add_tools()` |
| `03_skills.py` | Agent with `Skill.load()` and `add_skills()` |
| `04_config_file.py` | Agent from YAML config (`Agent.from_config()`) |
| `05_streaming.py` | Streaming responses with `stream="off"` |
| `06_sub_agents.py` | Agent composition and sub-agent delegation |
| `07_custom_loop.py` | Custom ReAct loop extending `BaseLoop` |

### Running Examples

```bash
# Local execution (requires OpenAI-compatible server running)
cd src/tinycua-sdk
python docs/examples/01_basic_agent.py
```

---

## Development Commands

```bash
# Install dependencies
make install

# Run tests
make test

```
