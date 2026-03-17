# Design Document: Session & Memory Tools

**Spec**: `specs/session/spec.md`
**Status**: Complete
**Last Updated**: 2026-03-16

---

## Overview

This design outlines session and memory tools for the SDK. These tools enable agents to remember information and manage conversation state locally, with optional backend integration.

**Scope**: SDK-side tools (local storage with remote fallback)
**Out of Scope**: Semantic search, embeddings, context retrieval (see backend specs)

---

## Architecture

```
Agent
├── mode = "local"
│   ├── Tools (custom)
│   ├── Memory Tools (remember, recall, forget)
│   │   └── Local storage (JSON)
│   └── Session Utilities (create, save, load, list, delete)
│       └── Local storage (JSON files)
│
└── mode = "deployed"
    ├── Tools (custom)
    ├── Memory Tools → Remote backend (with local fallback)
    └── Session Utilities → Remote backend
```

---

## Data Model

### Memory

```json
// ~/.tinycua/memory.json
{
  "user_name": "Bob",
  "favorite_color": "blue",
  "last_topic": "weather"
}
```

### Session

```json
// ~/.tinycua/sessions/{uuid}.json
{
  "id": "uuid",
  "name": "Chat with Bob",
  "created_at": "2026-03-16T10:00:00Z",
  "updated_at": "2026-03-16T10:30:00Z",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"}
  ]
}
```

---

## Memory Backends

### LocalMemoryBackend

```python
from tinycua_sdk.tools.memory import LocalMemoryBackend

storage = LocalMemoryBackend()
storage.set("key", "value")
value, found = storage.get("key")
storage.delete("key")
```

### RemoteMemoryBackend

```python
from tinycua_sdk.tools.memory import RemoteMemoryBackend

storage = RemoteMemoryBackend(
    backend_url="http://localhost:8000",
    api_key="your_key"
)
```

### HybridMemoryBackend

```python
from tinycua_sdk.tools.memory import HybridMemoryBackend

# Tries remote first, falls back to local
backend = HybridMemoryBackend(
    backend_url="http://localhost:8000",
    api_key="your_key",
    local_storage_path="~/.tinycua/memory.json"
)
```

---

## Memory Tools

| Tool | Input | Output |
|------|-------|--------|
| remember | key: str, value: str | {"success": true, "key": "..."} |
| recall | key: str | {"value": "...", "found": true} |
| forget | key: str | {"success": true, "key": "..."} |
| list_memory | - | {"keys": ["key1", "key2"]} |
| clear_memory | - | {"success": true} |

### Usage

```python
from tinycua_sdk.tools import remember, recall, forget

# Use as agent tools
agent = Agent(tools=[remember, recall, forget])

# Or invoke directly
remember.invoke(key="name", value="Bob")
recall.invoke(key="name")
forget.invoke(key="name")
```

---

## Session Utilities

Session utilities are **NOT tools** - they are manual utilities.

| Utility | Input | Output |
|---------|-------|--------|
| create_session | name: str | {"id": "uuid", "name": "..."} |
| save_session | session_id: str, messages: list | {"success": true} |
| load_session | session_id: str | {"messages": [...], "loaded": true} |
| list_sessions | - | {"sessions": [{"id": "...", "name": "..."}]} |
| delete_session | session_id: str | {"success": true} |

### Usage

```python
from tinycua_sdk.tools.session_utils import (
    create_session,
    save_session,
    load_session,
    list_sessions,
    delete_session
)

# Create a new session
result = create_session(name="My Chat")
session_id = result["session_id"]

# Save messages
save_session(session_id=session_id, messages=[...])

# Load session
loaded = load_session(session_id=session_id)
messages = loaded["messages"]

# List all sessions
list_sessions()

# Delete session
delete_session(session_id=session_id)
```

---

## Cancel Mechanism

### Agent Properties

```python
agent = Agent(name="test")

# Check cancel state
agent.is_cancelled  # False

# Cancel execution
agent.cancel()  # Sets cancel event

# Reset for next run
agent.reset_clear()
```

### Runner Integration

Runner automatically checks `cancel_event` during streaming:

```python
async for event in agent.stream("Hello"):
    if agent.is_cancelled:
        break
    # Process event
```

---

## Configuration

### Environment Variables

```bash
# Backend URL for remote storage
TINYCUA_BACKEND_URL=http://localhost:8000

# API key for authentication
TINYCUA_API_KEY=your_key

# Force local-only memory (no remote)
TINYCUA_MEMORY_LOCAL_ONLY=true
```

### Programmatic

```python
from tinycua_sdk.tools.memory import get_memory_backend

# Get appropriate backend
backend = get_memory_backend(
    backend_url="http://localhost:8000",
    api_key="your_key",
    local_only=False
)
```

---

## Storage

- **Location**: `~/.tinycua/`
- **Format**: JSON files
- **Local by default**: No backend required

---

## Implementation Status

### Phase 1 — Memory Tools ✅

- ✅ Implement storage module (`tools/memory.py`)
- ✅ Implement remember/recall/forget tools (`tools/memory_tools.py`)
- ✅ Hybrid backend with local fallback

### Phase 2 — Session Utilities ✅

- ✅ Session storage (`session/session.py`)
- ✅ Session utilities (`tools/session_utils.py`)

### Phase 3 — Cancel Mechanism ✅

- ✅ Agent cancel methods
- ✅ Runner cancel checking

### Phase 4 — Integration ✅

- ✅ Example: `examples/03_memory_and_session.py`
- ✅ Tests: `tests/unit/test_memory.py`

---

## Future (Backend)

When backend is implemented:
- RemoteMemoryBackend connects to backend API
- Context retrieval tools (get_summary, search_context)
- Embeddings for semantic search
- Compaction with layered summaries

See `specs/session-context/spec.md` for backend details.
