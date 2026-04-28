# Session & Message Persistence Design

## Overview

This document describes the design for session and message persistence in the TINYCUA system.

## Goals

1. Messages table created on backend startup
2. Stateless `/run` endpoint - only executes, no session/message management
3. Session and message management via explicit SDK/BackendClient calls
4. Agent.run() stays stateless - returns result without side effects
5. RunResult used for detailed execution trace (multi-step, tool calls, token usage)

## Architecture

### Database Schema

Both SQLite (local) and PostgreSQL (deployed) use the same `SessionStore` with nullable columns:

```
sessions table (shared):
┌──────────┬───────────┬──────────┬───────────┬─────────┐
│    id    │ tenant_id │ user_id  │ agent_id  │  name   │
├──────────┼───────────┼──────────┼───────────┼─────────┤
│ UUID (PK)│ nullable  │ nullable │ nullable  │  str    │
└──────────┴───────────┴──────────┴───────────┴─────────┘

messages table (shared):
┌──────────┬────────────┬──────┬─────────────────┬─────────────┐
│    id    │ session_id │ role │    content      │ turn_index  │
├──────────┼────────────┼──────┼─────────────────┼─────────────┤
│ UUID (PK)│ FK→session │ str  │      text       │    int      │
└──────────┴────────────┴──────┴─────────────────┴─────────────┘
```

### Two Usage Modes

| Mode | Session/Message Storage | Flow |
|------|------------------------|------|
| **Local** | SQLite (via SDK SessionStore) | SDK creates tables, stores locally |
| **Deployed** | PostgreSQL (via Backend API) | Backend creates tables, SDK calls API |

## Components

### 1. Backend: Tables Creation

**File:** `backend/main.py`

On startup, create both backend tables and SDK tables:

```python
from tinycua_backend.database import create_tables
from tinycua_sdk.storage import SessionStore

# In lifespan():
create_tables()  # Backend tables (tenants, agents, tools, sessions)
SessionStore(config.database.url).create_tables()  # SDK tables (sessions, messages)
```

### 2. Backend: Stateless `/run` Endpoint

**File:** `backend/routers/run.py`

The `/run` endpoint should ONLY:
1. Validate agent exists
2. Call runner
3. Stream response

**REMOVED:**
- Session creation/loading
- Message loading
- Message saving

```python
@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, request: RunRequest, ...):
    # 1. Validate agent exists
    agent = load_agent(agent_id, tenant_id, db)
    
    # 2. Call runner (stateless)
    # 3. Stream response
    
    # NO session management
    # NO message loading/saving
```

### 3. Backend: Session/Message Endpoints

**File:** `backend/routers/sessions.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/sessions` | POST | Create session |
| `/v1/sessions` | GET | List sessions |
| `/v1/sessions/{id}` | GET | Get session |
| `/v1/sessions/{id}/messages` | GET | List messages |
| `/v1/sessions/{id}/messages` | POST | Add message |

**Add Message Request:**
```python
class MessageCreate(BaseModel):
    role: str  # "user", "assistant", "tool", "metadata"
    content: str

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    turn_index: int
    created_at: str
```

### 4. SDK: BackendClient Methods

**File:** `sdk/clients/backend.py`

Add methods for session/message management:

```python
class BackendClient:
    async def create_session(
        self,
        agent_id: str,
        name: str | None = None,
    ) -> dict:
        """Create a new session.
        
        Returns:
            {"id": "uuid", "agent_id": "...", "name": "...", ...}
        """
        
    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get messages for a session.
        
        Returns:
            [{"id": "...", "role": "user", "content": "...", ...}, ...]
        """
        
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> dict:
        """Add a message to a session.
        
        Returns:
            {"id": "uuid", "role": "...", "content": "...", ...}
        """
```

### 5. SDK: RunResult Structure

**File:** `sdk/models/result.py`

The `RunResult` captures execution details for message saving:

```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    result: Any = None

@dataclass
class RunResult:
    response: str                          # Assistant's text response
    tool_calls: list[ToolCall]            # All tool calls made
    usage: dict[str, int]                 # Token usage (input/output/total)
    trace: list[dict[str, Any]]           # Raw LLM request/response pairs
    finish_reason: str | None             # Why execution ended
    
    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)
    
    @property
    def input_tokens(self) -> int:
        return self.usage.get("input_tokens", 0)
    
    @property
    def output_tokens(self) -> int:
        return self.usage.get("output_tokens", 0)
```

### 6. Agent.run() Signature

**File:** `sdk/agent/agent.py`

Agent.run() remains stateless:

```python
async def run(
    self,
    user_input: str,
    instructions: str | None = None,
    trace: bool = False,    # Default False, returns string
    verbose: bool = False,
    stream_sse: bool = False,
    force_local: bool = False,
) -> Union[str, RunResult]:
    """Run the agent with a user input.
    
    Args:
        user_input: The user's message
        trace: If True, return RunResult with full execution details
        
    Returns:
        Assistant response string, or RunResult if trace=True
    """
    # Just executes and returns result
    # NO saving, NO session management
```

## Usage Example

```python
from tinycua_sdk import Agent, BackendClient
import json

# Setup
client = BackendClient(base_url="http://localhost:8000")
agent = Agent(
    provider="lmstudio",
    base_url="http://localhost:1234",
    tools=[add_numbers, multiply],
    backend_url="http://localhost:8000",
    backend_api_key=client.api_key,
)

# Deploy
await agent.deploy()

# Create session (can reuse for multiple agents)
session = await client.create_session(agent_id=agent.agent_id, name="Math Chat")
session_id = session["id"]

# Run with trace to get full details
result = await agent.run("What is 5 + 3, then multiply by 2?", trace=True)

# result.response = "5 + 3 = 8, then 8 * 2 = 16"
# result.tool_calls = [
#   ToolCall(name="add_numbers", args={"a": 5, "b": 3}, result=8),
#   ToolCall(name="multiply", args={"a": 8, "b": 2}, result=16),
# ]
# result.usage = {"input_tokens": 150, "output_tokens": 45, "total_tokens": 195}

# Save messages explicitly
await client.add_message(session_id, "user", "What is 5 + 3, then multiply by 2?")

await client.add_message(session_id, "assistant", result.response)

# Save tool calls as JSON
for tc in result.tool_calls:
    await client.add_message(session_id, "tool", json.dumps({
        "tool_name": tc.name,
        "arguments": tc.arguments,
        "result": tc.result,
    }))

# Optionally save metadata
await client.add_message(session_id, "metadata", json.dumps({
    "usage": result.usage,
    "finish_reason": result.finish_reason,
}))

# Later: retrieve conversation
messages = await client.get_messages(session_id)
for msg in messages:
    print(f"[{msg['role']}] {msg['content']}")
```

## Files to Modify

| File | Changes |
|------|---------|
| `backend/main.py` | Add `SessionStore.create_tables()` |
| `backend/routers/run.py` | Remove session/message logic |
| `backend/routers/sessions.py` | Fix import, add `POST /sessions`, add message endpoints |
| `sdk/clients/backend.py` | Add `create_session`, `get_messages`, `add_message` |

## Open Questions

1. **Trace captures all steps?** Yes - `trace` array contains all LLM request/response pairs for multi-step execution.

2. **Usage data?** Currently captures from final LLM response only. For per-step usage, use `trace` array.

3. **Tool message format?** JSON with `tool_name`, `arguments`, `result`.
