# Design Document: tinycua-runner Core

**Spec**: `specs/runner-core/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-17

---

## Overview

The tinycua-runner is a stateless execution service that receives execution requests from the backend, uses tinycua-sdk to execute agents with full session context, and streams results back via SSE.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           tinycua-runner                               │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        FastAPI App                               │  │
│  │  ┌──────────────┐  ┌──────────────────────────────────────────┐ │  │
│  │  │   Auth      │  │              Execution Service             │ │  │
│  │  │  Middleware │  │  ┌────────────┐  ┌────────────────────┐  │ │  │
│  │  │             │──▶│  │  Executor  │──▶│    tinycua-sdk    │  │ │  │
│  │  │  (Token)    │  │  └────────────┘  │  Agent + Runner   │  │ │  │
│  │  └──────────────┘  │                   │  + SessionStore  │  │ │  │
│  │                    │                   └────────────────────┘  │ │  │
│  │                    └──────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
        │                                            ▲
        │ POST /internal/v1/run                     │
        │ (with db_url)                             │ SSE Stream
        ▼                                            │
┌─────────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL DB                                   │
│                     (provided in request)                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

### Environment Variables

```bash
# Runner
RUNNER_TOKEN=runner-secret-token
HOST=0.0.0.0
PORT=8001
```

### Or `.env` file

```bash
RUNNER_TOKEN=runner-secret-token
HOST=0.0.0.0
PORT=8001
```

---

## Authentication

### Token Validation Middleware

```python
from fastapi import Request, HTTPException
import os

RUNNER_TOKEN = os.getenv("RUNNER_TOKEN")

async def validate_runner_token(request: Request):
    """Validate that the request comes from trusted backend."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authorization")
    
    scheme, token = auth_header.split(" ", 1)
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid scheme")
    
    if token != RUNNER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return True
```

---

## Execution Flow

```
Backend ──▶ Runner
   │
   │ POST /internal/v1/run
   │ {
   │   "agent_config": {...},
   │   "session_id": "uuid",
   │   "db_url": "postgresql://...",
   │   "user_input": "..."
   │ }
   │
Runner:
   │
   ├─▶ 1. Create SessionStore(db_url)
   │       └─▶ Connect to PostgreSQL
   │
   ├─▶ 2. Create context tools with SessionStore + session_id
   │       ├─▶ search_context_grep_tool
   │       ├─▶ search_context_semantic_tool
   │       ├─▶ get_context_summary_tool
   │       └─▶ get_recent_turns_tool
   │
   ├─▶ 3. Create Agent from agent_config
   │       └─▶ Add context tools
   │
   ├─▶ 4. Execute agent.run(user_input)
   │       └─▶ Returns async iterator of events
   │
   └─▶ 5. Stream events back via SSE
           └─▶ Forward each event to client
```

---

## API Endpoint

### POST /internal/v1/run

```python
from fastapi import FastAPI, Depends
from pydantic import BaseModel
import uuid

app = FastAPI()

class RunRequest(BaseModel):
    agent_config: dict
    session_id: uuid.UUID
    db_url: str
    user_input: str

@app.post("/internal/v1/run")
async def run_agent(request: RunRequest, _: bool = Depends(validate_runner_token)):
    """Execute an agent with session context."""
    
    # Create executor
    executor = Executor(
        db_url=request.db_url,
        session_id=request.session_id
    )
    
    # Stream results
    async def event_stream():
        async for event in executor.execute(
            agent_config=request.agent_config,
            user_input=request.user_input
        ):
            yield f"data: {event}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## Executor

```python
class Executor:
    """Handles agent execution with session context."""
    
    def __init__(self, db_url: str, session_id: uuid.UUID):
        """Initialize executor with database connection."""
        self.db_url = db_url
        self.session_id = session_id
        self.store = SessionStore(db_url)
        self.store.create_tables()
    
    async def execute(self, agent_config: dict, user_input: str):
        """Execute agent and yield events."""
        
        # Create context tools with session store
        from tinycua_sdk.tools.context_tools import (
            search_context_grep_tool,
            search_context_semantic_tool,
            get_context_summary_tool,
            get_recent_turns_tool,
        )
        
        tools = [
            search_context_grep_tool(self.store, self.session_id),
            search_context_semantic_tool(self.store, self.session_id),
            get_context_summary_tool(self.store, self.session_id),
            get_recent_turns_tool(self.store, self.session_id),
        ]
        
        # Build agent from config
        from tinycua_sdk.agent import Agent
        
        agent = Agent(
            name=agent_config.get("name", "runner-agent"),
            instructions=agent_config.get("instructions", ""),
            system_prompt=agent_config.get("system_prompt", "You are a helpful assistant."),
            model=agent_config.get("model", "gpt-4o-mini"),
            provider=agent_config.get("provider", "openai"),
            base_url=agent_config.get("base_url"),
            api_key=agent_config.get("api_key"),
            tools=tools,
        )
        
        # Execute
        async for event in agent.run(user_input, stream_sse=True):
            yield event
```

---

## Tool Bundle Handling

The runner receives bundled tools from the backend. These tools are already resolved with their dependencies and ready to be registered and executed.

### Tool Registration

```python
class ToolRegistry:
    """In-memory registry for custom tools."""
    
    def __init__(self):
        self._tools: dict[str, dict] = {}
    
    def register(self, tool_bundle: dict) -> None:
        """Register a tool from bundle."""
        name = tool_bundle["name"]
        self._tools[name] = tool_bundle
    
    def get(self, name: str) -> dict | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_all(self) -> list[dict]:
        """List all registered tools."""
        return list(self._tools.values())


def materialize_tool(tool_bundle: dict) -> Callable:
    """Materialize a tool from source code.
    
    Uses exec() to create a callable function from source code.
    """
    source = tool_bundle["source"]
    name = tool_bundle["name"]
    
    namespace = {}
    exec(source, namespace)
    
    return namespace.get(name)
```

### Updated Request Model

```python
class RunRequest(BaseModel):
    agent_config: dict
    session_id: uuid.UUID
    db_url: str
    user_input: str
    tools: list[dict] | None = None  # NEW: bundled tools
    messages: list[dict] | None = None  # NEW: conversation history
```

### Updated Execution Flow

```
Backend ──▶ Runner
   │
   │ POST /internal/v1/run
   │ {
   │   "agent_config": {...},
   │   "session_id": "uuid",
   │   "db_url": "postgresql://...",
   │   "user_input": "...",
   │   "tools": [...],        # NEW: bundled tools
   │   "messages": [...]      # NEW: conversation history
   │ }
   │
Runner:
   │
   ├─▶ 1. Register tools from bundle
   │       ├─▶ For each tool in tools:
   │       │   └─▶ ToolRegistry.register(tool_bundle)
   │       │
   ├─▶ 2. Create SessionStore(db_url)
   │       └─▶ Connect to PostgreSQL
   │
   ├─▶ 3. Create context tools with SessionStore + session_id
   │
   ├─▶ 4. Materialize bundled tools
   │       ├─▶ For each registered tool:
   │       │   └─▶ materialize_tool(tool_bundle) → callable
   │       │
   ├─▶ 5. Create Agent from agent_config
   │       └─▶ Add context tools + materialized tools
   │
   ├─▶ 6. Execute agent.run(user_input, messages=messages)
   │       └─▶ Returns async iterator of events
   │
   └─▶ 7. Stream events back via SSE
```

### Tool Materialization

When executing a tool, the runner:

1. Looks up the tool in the registry
2. Uses `materialize_tool()` to create a callable from source
3. Executes the tool with provided arguments
4. Returns the result

Note: External dependencies (e.g., `requests`) are NOT auto-installed in MVP.
The tool source should have all dependencies available in the runner's environment.


---

## SSE Event Format

```python
# Events from SDK are already in SSE format
# Just forward them through

# Example event:
# data: {"type": "content", "content": "Hello"}

async def event_generator():
    async for event in agent.run(user_input, stream_sse=True):
        # event is already a string in SSE format
        yield event
```

---

## Execution Flow Sequence

```
Backend                      Runner                         SessionStore                  DB
   │                           │                               │                        │
   │ POST /internal/v1/run    │                               │                        │
   │ Authorization: Bearer ..  │                               │                        │
   │ {                         │                               │                        │
   │   agent_config: {...},    │                               │                        │
   │   session_id: "uuid",     │                               │                        │
   │   db_url: "...",         │                               │                        │
   │   user_input: "..."      │                               │                        │
   │ }                        │                               │                        │
   │──────────────────────────▶│                               │                        │
   │                           │                               │                        │
   │                           │ Validate token               │                        │
   │                           │───▶ Check RUNNER_TOKEN      │                        │
   │                           │◀─── OK                     │                        │
   │                           │                               │                        │
   │                           │ Create SessionStore(db_url)  │                        │
   │                           │─────────────────────────────▶│                        │
   │                           │                               │ CREATE CONNECTION      │
   │                           │─────────────────────────────▶│───────────────────────▶│
   │                           │                               │◀───────────────────────│
   │                           │                               │                        │
   │                           │ Create context tools         │                        │
   │                           │ (with store + session_id)    │                        │
   │                           │                               │                        │
   │                           │ ┌─────────────────────────┐ │                        │
   │                           │ │ search_context_grep    │ │                        │
   │                           │ │ search_context_semantic│ │                        │
   │                           │ │ get_context_summary    │ │                        │
   │                           │ │ get_recent_turns       │ │                        │
   │                           │ └─────────────────────────┘ │                        │
   │                           │                               │                        │
   │                           │ Build Agent from config      │                        │
   │                           │ (add tools + context)        │                        │
   │                           │                               │                        │
   │                           │ agent.run(user_input)        │                        │
   │                           │         │                    │                        │
   │                           │         │ LLM Request        │                        │
   │                           │         │───────────────────▶│                        │
   │                           │         │                    │                        │
   │                           │         │ LLM Response       │                        │
   │                           │◀─────────────────────────────│                        │
   │                           │         │                    │                        │
   │                           │         │ Tool Call:        │                        │
   │                           │         │ get_recent_turns()│                        │
   │                           │         │                    │                        │
   │                           │         │ get_recent_turns  │                        │
   │                           │         │ (session_id)       │                        │
   │                           │         │───────────────────▶│                        │
   │                           │         │                    │ SELECT messages       │
   │                           │         │                    │─────────────────────▶│
   │                           │         │                    │◀─────────────────────│
   │                           │         │                    │                        │
   │                           │         │ returns: {...}    │                        │
   │                           │◀─────────────────────────────│                        │
   │                           │         │                    │                        │
   │                           │ [Generate response]         │                        │
   │                           │         │                    │                        │
   │                           │ [SSE Event: content]       │                        │
   │◀──────────────────────────│                               │                        │
   │                           │                               │                        │
   │                           │ [SSE Event: done]          │                        │
   │◀──────────────────────────│                               │                        │
   │                           │                               │                        │
```

---

## Health Check

```python
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
```

---

## Implementation Phases

### Phase 1: Setup + Auth

- [ ] Project setup (FastAPI)
- [ ] Environment config
- [ ] Token validation middleware
- [ ] Health endpoint

### Phase 2: Execution

- [ ] Run endpoint
- [ ] SessionStore integration
- [ ] Context tools creation
- [ ] Agent creation from config
- [ ] Execution with streaming

### Phase 3: Testing

- [ ] Unit tests for auth
- [ ] Integration test with mock backend
- [ ] Concurrent execution test

---

## Security Considerations

1. **Token Validation**: Only accept requests with valid runner token
2. **DB Access Scope**: Runner only accesses the specific session_id provided
3. **No Persistent Storage**: Runner doesn't store any state
4. **Timeout**: Set appropriate timeouts for execution
5. **Resource Limits**: Consider adding execution timeout limits
