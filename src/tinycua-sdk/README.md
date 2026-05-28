# TINYCUA SDK

Developer SDK and integration libraries for the TINYCUA project.

## Authentication Options

The SDK supports multiple authentication methods:

1. **No Auth** - Local execution only (no backend)
2. **JWT Token** - Login with email/password to get token
3. **Global API Key** - System-wide access (bypasses tenant restrictions)

### Using Global API Key

Set `TINYCUA_API_KEY` in your `.env` file:

```bash
TINYCUA_BACKEND_URL=http://localhost:8000
TINYCUA_API_KEY=your-global-api-key
```

This gives you system-wide access to all agents and tools across all tenants.

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
# Backend URL (for deployed mode)
TINYCUA_BACKEND_URL=http://localhost:8000

# API Key (for authenticated requests)
TINYCUA_API_KEY=

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

### Remote Execution (With Backend)

Deploy agents to the backend for centralized management:

```python
import asyncio
from tinycua_sdk import Agent
from tinycua_sdk.tools import tool
from tinycua_sdk.clients import BackendClient

# Configure backend connection
client = BackendClient(
    base_url="http://localhost:8000",
    email="user@example.com",
    password="password123"
)

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
    model="qwen/qwen3.5-9b",
    backend_client=client
)

async def main():
    # Deploy agent and tools to backend
    await agent.deploy()

    # Run remotely via backend -> runner
    response = await agent.run("What is 5 + 3? Use the add_numbers tool.")
    print(response)

asyncio.run(main())
```

## Examples

The SDK includes example scripts in the `examples/` directory:

| Example | Description |
|---------|-------------|
| `01_agent_basic.py` | Basic agent with tools, local execution |
| `02_agent_streaming.py` | Streaming responses with tools |
| `03_memory_and_session.py` | Session management and memory |
| `04_remote_runner.py` | Using remote HTTP runner |
| `05_agent_hierarchy.py` | Agent hierarchies and sub-agents |
| `06_local_storage.py` | Local storage and persistence |
| `07_deployed_agent.py` | Full deployed agent workflow |
| `07a_simple_deployed.py` | Minimal deployed agent example |
| `09_global_api_key.py` | Global API key (system-wide access) |

### Running Examples

```bash
# Local execution (no backend)
cd src/tinycua-sdk
python examples/01_agent_basic.py

# Deployed agent (requires backend + runner)
python examples/07_deployed_agent.py
```

---

## End-to-End Test

The SDK includes an end-to-end test that verifies the full flow:
1. Register user
2. Create tool
3. Create agent
4. Run agent (triggers backend → runner → OpenAI-compatible endpoint)

### Prerequisites

1. **PostgreSQL running**:
   ```bash
   make docker-up
   ```

2. **Backend running** (terminal 1):
   ```bash
   cd src/tinycua-backend
   python -m tinycua_backend.main
   ```

3. **Runner running** (terminal 2):
   ```bash
   cd src/tinycua-runner
   python -m tinycua_runner.main
   ```

4. **OpenAI-compatible endpoint running** with a model loaded (e.g., qwen2.5-coder-14b)

### Run the Test

```bash
# From project root
make e2e-test

# Or directly
cd src/tinycua-sdk
python -m tests.e2e.test_backend_runner
```

### Expected Output

```
==================================================
End-to-End Test: tinycua-backend + tinycua-runner
==================================================

[Step 0] Register user...
✓ Registered: tenant=...

[Step 1] Creating tool...
✓ Created tool: ... (add_numbers)

[Step 2] Creating agent...
✓ Created agent: ... (test-agent)

[Step 3] Running agent...
→ Running agent ...
  Status: 200
  Response: The sum of 5 and 3 is 8. ...

==================================================
✓ End-to-end test PASSED
```

---

## Development Commands

```bash
# Install dependencies
make install

# Run tests
make test

# Run end-to-end test
make e2e-test
```
