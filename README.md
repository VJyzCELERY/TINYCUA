# TINYCUA

TINYCUA is a modular multi-subproject repository providing a complete agent system for building, deploying, and running AI agents with tools.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client   │────▶│  Backend   │────▶│   Agent   │
│   (SDK)    │     │  (FastAPI) │     │  Executor  │
│            │◀────│            │◀────│  (SDK)     │
└─────────────┘     └─────────────┘     └─────────────┘
                               │
                               ▼
                         ┌─────────┐     ┌─────────┐
                          │PostgreSQL│     │ OpenAI   │
                          │(Session) │     │Compatible│
                         └──────────┘     └──────────┘
```

## Subprojects

1. **tinycua** - CLI and TUI application for interacting with agents
2. **tinycua-sdk** - Developer SDK for building agents with tools
3. **tinycua-backend** - Backend API for agent deployment, session tracking, and tool management
4. **tinycua-finetune** *(planned)* - Fine-tuning pipeline for open-weight LLMs

## Prerequisites

- Python 3.12+
- Docker & Docker Compose (for PostgreSQL)
- An OpenAI-compatible endpoint running locally (e.g., http://localhost:1234/v1)

## Quick Start (Make - Easiest)

### 1. Install & Start Everything

```bash
# Clone and navigate to project
cd TINYCUA

# Start database (PostgreSQL)
make docker-up

# Install all dependencies
make install

# Copy config example and edit with your values
cp src/tinycua-backend/config.example.yaml src/tinycua-backend/config.yaml
# Edit config.yaml with your values

# Copy SDK env example and edit with your values
cp src/tinycua-sdk/.env.example src/tinycua-sdk/.env
# Edit .env with your backend URL and API key

# Start backend service
make run

# Load a model in your OpenAI-compatible endpoint (e.g., qwen2.5-coder-14b)

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
cd src/tinycua-sdk && pip install -e .
cd src/tinycua && pip install -e .
```

### 3. Configure

**Backend** (`src/tinycua-backend/config.yaml`):
```yaml
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

### 4. Start Services

```bash
# Start backend
cd src/tinycua-backend
python -m tinycua_backend.main
```

### 5. Run End-to-End Test

```bash
# Ensure your OpenAI-compatible endpoint is running with a model loaded
# Then run:
cd src/tinycua-sdk
python -m tests.integration.test_local_run
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
    provider="openai-compatible",
    base_url="http://127.0.0.1:1234/v1",
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
    provider="openai-compatible",
    base_url="http://127.0.0.1:1234/v1",
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

- [Full Documentation](docs/full-docs/INDEX.md) - Comprehensive docs for all subprojects
- [Agent Rules](docs/agents/) - AI agent guidelines
- [Project Rules](docs/project_rules/) - Coding standards
- [Specs](specs/) - Architecture specifications

## Folder Structure

```
TINYCUA/
├── docs/                    # Project-level documentation
│   └── full-docs/           # Comprehensive developer/contributor docs
├── specs/                   # Architecture specifications
├── docker-compose.yml       # Docker services (PostgreSQL)
├── src/
│   ├── tinycua/           # CLI/TUI application
│   ├── tinycua-backend/   # Backend API
│   ├── tinycua-sdk/       # Developer SDK
│   └── tinycua-finetune/  # Fine-tuning pipeline (planned)
└── Makefile
```
