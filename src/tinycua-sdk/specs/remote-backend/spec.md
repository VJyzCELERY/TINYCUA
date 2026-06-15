# Feature Specification: Backend Client SDK

**Status**: Draft
**Created**: 2026-03-16
**Last Updated**: 2026-03-17
**Subproject(s) Affected**: tinycua-sdk

---

## Quick Guidelines

- Focus on **WHAT** users/callers need and **WHY** — not HOW to implement
- Every requirement must be independently testable

---

## Problem Statement

**Goals**: Provide SDK users a seamless experience to deploy and run agents on a backend:
1. Users interact ONLY with the Agent class
2. Agent automatically runs locally or remotely based on configuration
3. Support multi-tenancy (different users/organizations)

**Gaps**:
- No unified interface for local vs deployed mode
- Users currently need to know about backend Client

**Non-Goals**:
- Implementing actual backend (users build their own)
- Hosting/infrastructure

---

## User-Facing API (Agent Class)

Users only interact with the **Agent** class:

```python
# Create and deploy agent
agent = Agent(
    name="my-agent",
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
    user_id="user-123",  # Optional: for multi-tenancy
)

await agent.deploy()  # Deploy to backend, agent.agent_id is set

# Run (automatically uses backend when deployed)
response = await agent.run("Hello")

# Force local run (ignore deployment)
response = await agent.run("Hello", force_local=True)

# Delete from backend
await agent.delete()
```

---

## Requirements

### FR-001

The Agent MUST support deployment to a backend via `deploy()` and set `agent_id` on success.

### FR-002

The Agent MUST automatically use backend when running if deployed (unless `force_local=True`).

### FR-003

The Agent MUST support multi-tenancy via custom headers (backend decides the header name).

### FR-004

The Agent MUST support authentication via `backend_api_key` or custom headers.

### FR-005

The Agent MUST support deleting from backend via `delete()`.

### FR-006

The Agent MUST support loading from backend via `load_agent(agent_id)`.

### FR-007

The Agent MUST have `__str__()` method for formatted output.

### FR-008

The SDK MUST provide standalone utility functions: `get_agent()`, `list_agents()`, `health_check()`.

### FR-009

The SDK MUST load backend configuration from global config if not provided per-agent.

---

## Configuration

Backend settings can be provided at multiple levels:

### Global Config (tinycua_sdk/config.py)

```python
from tinycua_sdk import config

# Set globally
config.configure(
    backend_url="http://localhost:8000",
    backend_api_key="global-key",
)

# Or via environment
# TINYCUA_BACKEND_URL
# TINYCUA_API_KEY
```

### Per-Agent

```python
agent = Agent(
    name="my-agent",
    backend_url="http://localhost:8000",  # Override global
    backend_api_key="per-agent-key",      # Override global
    backend_headers={
        "X-User-ID": "user-123",           # Multi-tenancy (backend decides header name)
        "X-Tenant-ID": "tenant-456",       # Alternative
        "Authorization": "Bearer token",   # Custom auth
    },
)
```

### Priority

1. Per-agent (backend_url, backend_api_key, backend_headers)
2. Global config (Config.BACKEND_URL, Config.API_KEY)
3. Default: http://localhost:8000

---

## Standalone Functions (Utilities)

These are standalone functions, not part of Agent class:

```python
from tinycua_sdk import get_agent, list_agents, health_check

# Get agent details from backend by ID (requires auth)
agent_data = await get_agent(
    agent_id="agent-123",
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
)

# List all agents in backend (requires auth)
agents = await list_agents(
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
    backend_headers={"X-User-ID": "user-123"},  # Multi-tenancy via custom headers
)

# Check if backend is healthy (no auth required)
is_healthy = await health_check(
    backend_url="http://localhost:8000",
)
```

| Function | Auth Required | Description |
|----------|--------------|-------------|
| `get_agent()` | Yes | Get agent details by ID |
| `list_agents()` | Yes | List all agents |
| `health_check()` | No | Check backend health |

**Note**: Multi-tenancy is handled via `backend_headers` - the backend decides what header to use (e.g., `X-User-ID`, `X-Tenant-ID`, etc.)

---

## API Contract (Backend Endpoints)

| Method | Endpoint | Used By |
|--------|----------|---------|
| POST | /v1/agents | Agent.deploy() |
| GET | /v1/agents/{id} | get_agent() |
| DELETE | /v1/agents/{id} | Agent.delete() |
| POST | /v1/agents/{id}/run | Agent.run() (internal) |
| GET | /v1/agents | list_agents() |
| GET | /health | health_check() |

### Multi-Tenancy

All endpoints support multi-tenancy via:
- Header: `X-User-ID: <user_id>`

### Authentication

The SDK passes authentication via:
- Default: `Authorization: Bearer {backend_api_key}`
- Override: Custom headers via `backend_headers`

---

## Status

| Component | Status |
|-----------|--------|
| Agent.deploy() | ⏳ |
| Agent.run() (deployed) | ⏳ |
| Agent.delete() | ⏳ |
| Agent.load_agent() | ⏳ |
| Agent.__str__() | ⏳ |
| get_agent() | ⏳ |
| list_agents() | ⏳ |
| health_check() | ⏳ |
| Multi-tenancy | ⏳ |

---

## Review Checklist

- [ ] No implementation details
- [ ] All mandatory sections completed
- [ ] Requirements are testable
- [ ] Scope clearly bounded
