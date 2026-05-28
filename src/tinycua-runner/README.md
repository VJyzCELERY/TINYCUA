# tinycua-runner

Stateless execution engine that runs agents with tools.

## Features

- **Stateless Execution**: Receives execution requests, runs agents, returns results
- **Tool Registry**: Materializes tools from source code at runtime
- **Backend Integration**: Validates runner token from backend
- **Context Tools**: Provides session context retrieval (search, summary, recent)
- **Multiple Providers**: Supports OpenAI, LM Studio, Ollama, etc.

## Setup

```bash
# Install dependencies
pip install -e .

# Or use make
make install
```

## Configuration

Create `.config.yaml`:

```yaml
runner_token: "your-secret-token"
host: "0.0.0.0"
port: 8003
```

## Running

```bash
python -m tinycua_runner.main
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/internal/health` | Health check |
| POST | `/internal/v1/run` | Execute agent |

## Execution Flow

```
Backend ──▶ Runner
   │
   │ POST /internal/v1/run
   │ { agent_config, session_id, db_url, tools, messages }
   │
Runner:
   │
   ├─▶ 1. Validate runner token
   ├─▶ 2. Register bundled tools
   ├─▶ 3. Create SessionStore (db_url)
   ├─▶ 4. Create context tools
   ├─▶ 5. Execute agent
   └─▶ 6. Stream SSE results
```

## Development

```bash
# Run tests
make test

# Run lint
make lint

# Run coverage
make coverage
```
