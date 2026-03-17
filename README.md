# TINYCUA

TINYCUA is a modular multi-subproject repository consisting of four subprojects that work together to provide a complete agent system.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client   │────▶│  Backend   │────▶│   Runner   │
│   (SDK)    │     │  (FastAPI) │     │  (Agent    │
│            │◀────│            │◀────│  Executor) │
└─────────────┘     └─────────────┘     └─────────────┘
                              │              │
                              ▼              ▼
                        ┌─────────┐     ┌─────────┐
                        │PostgreSQL    │ LM Studio │
                        │(Session)     │(LLM)      │
                        └──────────────┘└───────────┘
```

## Subprojects

1. **tinycua-backend** - Backend API for agent deployment, tool management, session tracking
2. **tinycua-runner** - Stateless execution engine that runs agents with tools
3. **tinycua-sdk** - Developer SDK for building agents with tools
4. **tinycua-finetune** - Fine-tuning pipeline for open-weight LLMs

## Prerequisites

- Python 3.12+
- Docker & Docker Compose (for PostgreSQL)
- [LM Studio](https://lmstudio.ai/) (for local LLM inference)

## Quick Start (Make - Easiest)

### 1. Install & Start Everything

```bash
# Clone and navigate to project
cd TINYCUA

# Start database (PostgreSQL)
make docker-up

# Install all dependencies
make install

# Copy config examples and edit with your values
cp src/tinycua-backend/config.example.yaml src/tinycua-backend/config.yaml
cp src/tinycua-runner/config.example.yaml src/tinycua-runner/config.yaml
# Edit config.yaml files with your values

# Copy SDK env example and edit with your values
cp src/tinycua-sdk/.env.example src/tinycua-sdk/.env
# Edit .env with your backend URL and API key

# Start all services (docker + backend + runner)
make run

# Load a model in LM Studio (e.g., qwen2.5-coder-14b)

# Run end-to-end test
make e2e-test
```

### 2. Stop Everything

```bash
make stop
```

---

## Manual Installation (Step by Step)

### 1. Start Database

```bash
# Using Docker directly
docker run -d \
  --name tinycua-postgres \
  -e POSTGRES_USER=tinycua \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=tinycua \
  -p 5432:5432 \
  postgres:17.4-alpine

# Or use docker-compose
docker-compose up -d
```

### 2. Install Dependencies

```bash
# Install all subproject dependencies
make install

# Or install individually
cd src/tinycua-backend && pip install -e .
cd src/tinycua-runner && pip install -e .
cd src/tinycua-sdk && pip install -e .
```

### 3. Configure

Create `.config.yaml` in each subproject:

**Backend** (`src/tinycua-backend/.config.yaml`):
```yaml
runner:
  url: "http://localhost:8003"
  token: "your-runner-token"

database:
  url: "postgresql://tinycua:secret@localhost:5432/tinycua"

auth:
  jwt_secret: "your-secret-key"
  jwt_algorithm: "HS256"
  jwt_expiration_hours: 24

server:
  host: "0.0.0.0"
  port: 8000
```

**Runner** (`src/tinycua-runner/.config.yaml`):
```yaml
runner_token: "your-runner-token"
host: "0.0.0.0"
port: 8003
```

### 4. Start Services

```bash
# Start backend
cd src/tinycua-backend
python -m tinycua_backend.main

# Start runner (in another terminal)
cd src/tinycua-runner
python -m tinycua_runner.main
```

### 5. Run End-to-End Test

```bash
# Ensure LM Studio is running with a model loaded
# Then run:
cd src/tinycua-sdk
python -m tests.e2e.test_backend_runner
```

---

## SDK Usage Examples

### Local Execution (No Backend)

```python
from tinycua_sdk import Agent
from tinycua_sdk.tools import tool

@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

agent = Agent(
    name="math-agent",
    instructions="You are a helpful math assistant.",
    tools=[calculate],
    provider="lmstudio",
    base_url="http://127.0.0.1:1234",
    model="qwen/qwen3.5-9b"
)

# Run locally
response = agent.run("What is 5 + 3?")
print(response)
```

### Remote Execution (With Backend)

```python
from tinycua_sdk import Agent
from tinycua_sdk.tools import tool
from tinycua_sdk.clients import BackendClient

# Configure backend client
client = BackendClient(
    base_url="http://localhost:8000",
    email="user@example.com",
    password="password123"
)

@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

agent = Agent(
    name="math-agent",
    instructions="You are a helpful math assistant.",
    tools=[calculate],
    provider="lmstudio",
    base_url="http://127.0.0.1:1234",
    model="qwen/qwen3.5-9b",
    backend_client=client
)

# Deploy to backend and run remotely
await agent.deploy()
response = await agent.run("What is 5 + 3?")
print(response)
```

---

## Development Commands

```bash
# Install dependencies
make install

# Run tests
make test

# Run linting
make lint

# Run coverage
make coverage

# Clean build artifacts
make clean

# Docker operations
make docker-up      # Start PostgreSQL
make docker-down    # Stop PostgreSQL
make docker-logs    # View logs

# Start all services
make dev-start
make dev-stop
```

---

## Documentation

- [Agent Rules](docs/agents/) - AI agent guidelines
- [Project Rules](docs/project_rules/) - Coding standards
- [Specs](specs/) - Architecture specifications

## Folder Structure

```
TINYCUA/
├── docs/                    # Project-level documentation
├── specs/                   # Architecture specifications
├── docker-compose.yml       # Docker services (PostgreSQL)
├── src/
│   ├── tinycua-backend/   # Backend API
│   ├── tinycua-runner/    # Execution engine
│   ├── tinycua-sdk/       # Developer SDK
│   └── tinycua-finetune/  # Fine-tuning pipeline
└── Makefile
```
