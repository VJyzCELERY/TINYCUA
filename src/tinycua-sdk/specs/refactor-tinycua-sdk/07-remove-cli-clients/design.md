# Stage 07 — Design: Remove CLI & Clients

## Overview

Delete the `cli/` and `clients/` packages. Command-line interfaces and HTTP clients are consumers of the SDK, not part of the SDK itself.

## Design Decisions

### Why Delete CLI?

1. **Separate deliverable**: A CLI is a standalone application that uses the SDK, not part of the SDK library.
2. **Different dependencies**: CLIs may require `click`, `rich`, `prompt-toolkit` — dependencies that SDK consumers don't need.
3. **Different release cycle**: The CLI can evolve independently of the SDK.

### Why Delete Clients?

1. **HTTP is infrastructure**: HTTP clients, connection pools, retries, and auth are consumer concerns.
2. **Backend communication**: The consumer decides how to talk to remote backends — REST, gRPC, WebSocket, etc.
3. **Stateless SDK**: The SDK does not initiate network requests.

### What Replaces CLI & Clients?

- **CLI**: Moved to a separate package (`tinycua-cli/`) if needed.
- **Clients**: The consumer implements its own HTTP client using `httpx`, `requests`, or any library.

## Files to Delete

### CLI

| File | Reason |
|------|--------|
| `cli/__init__.py` | Package init |
| `cli/main.py` | CLI entry point |
| `cli/repl.py` | Interactive REPL |
| `cli/agent_commands.py` | Agent management commands |

### Clients

| File | Reason |
|------|--------|
| `clients/__init__.py` | Package init |
| `clients/backend.py` | HTTP client for backend — consumer concern |
| `clients/client.py` | ResponsesClient — consumer concern |
| `clients/protocol.py` | Protocol definitions — consumer concern |
| `clients/agent_client.py` | AgentClient — consumer concern |

## Code Changes

### Remove CLI entry point from pyproject.toml

```toml
# BEFORE
[project.scripts]
tinycua = "tinycua_sdk.cli.main:main"

# AFTER
# No CLI entry point
```

### Remove client imports from Agent

```python
# BEFORE (agent/executor.py)
from tinycua_sdk.clients.backend import BackendClient
from tinycua_sdk.clients.client import ResponsesClient

# AFTER
# No client imports
# Agent runs locally; consumer handles remote execution
```

## Impact Analysis

### Files that reference cli/ or clients/

```bash
grep -r "from tinycua_sdk.cli" src/tinycua-sdk/tinycua_sdk/
grep -r "from tinycua_sdk.clients" src/tinycua-sdk/tinycua_sdk/
grep -r "tinycua = " pyproject.toml
```

### Expected impact

- `pyproject.toml` — Remove `[project.scripts]` entry
- `agent/executor.py` — Remove remote execution path (or simplify to only local)
- Tests — Already deleted in Stage 01

## Consumer Migration Guide

### Before (SDK provides CLI)
```bash
$ tinycua run --agent researcher --query "What is quantum computing?"
```

### After (Consumer provides CLI)
```python
# host_app/cli.py
import click
from tinycua_sdk import Agent

@click.command()
@click.option("--config", required=True)
@click.argument("query")
def run(config, query):
    agent = Agent.from_config(config)
    response = asyncio.run(agent.run(query))
    click.echo(response)

if __name__ == "__main__":
    run()
```

### Before (SDK provides client)
```python
from tinycua_sdk.clients import AgentClient

client = AgentClient(base_url="https://api.example.com")
response = await client.execute(agent_id, messages)
```

### After (Consumer provides client)
```python
import httpx

class MyBackendClient:
    def __init__(self, base_url):
        self.base_url = base_url
    
    async def execute(self, agent_id, messages):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/agents/{agent_id}/run",
                json={"messages": messages}
            )
            return resp.json()["response"]
```

## Acceptance Criteria

- [ ] `cli/` package is deleted entirely.
- [ ] `clients/` package is deleted entirely.
- [ ] No `[project.scripts]` entry in `pyproject.toml`.
- [ ] No imports from `tinycua_sdk.cli` or `tinycua_sdk.clients` in SDK code.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02.
- **Blocks**: None (can proceed in parallel with Stages 03–06, 08).
