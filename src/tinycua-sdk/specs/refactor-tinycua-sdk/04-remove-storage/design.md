# Stage 04 — Design: Remove Storage

## Overview

Delete the entire `storage/` package. Storage (databases, file I/O, persistence) is a consumer concern. The SDK is stateless and does not perform any I/O.

## Design Decisions

### Why Delete Storage?

1. **Stateful by definition**: Storage modules manage database connections, file handles, and persistent state.
2. **ORM models belong in consumer**: SQLAlchemy models for `Session`, `Message`, `AgentRecord` are schema definitions that the consumer should own.
3. **CRUD operations are consumer logic**: The consumer decides how to store, retrieve, and manage agent configurations and message history.
4. **SQLite is an implementation detail**: Using SQLite vs PostgreSQL vs S3 is a deployment decision, not a framework concern.

### What Replaces Storage?

Nothing in the SDK. The consumer:
- Defines its own database schema (SQLAlchemy, Django ORM, Prisma, etc.)
- Manages its own connection pools
- Handles migrations (Alembic, raw SQL, etc.)
- Implements CRUD for sessions, messages, and agent configs

The SDK provides:
- `Agent.to_config()` — serializes agent to a plain dict
- `Agent.from_config()` — deserializes agent from a plain dict
- `Skill.load()` — parses skill from a string (consumer reads the string from file/DB)

## Files to Delete

| File | Reason |
|------|--------|
| `storage/__init__.py` | Package init |
| `storage/models.py` | SQLAlchemy ORM models — consumer concern |
| `storage/store.py` | SessionStore CRUD — consumer concern |
| `storage/snapshot.py` | Snapshot manager — consumer concern |
| `storage/sqlite.py` | LocalStorage (sqlite3) — consumer concern |
| `storage/importer.py` | Import logic — consumer concern |
| `storage/export.py` | Export logic — consumer concern |

## Code Changes

### Remove storage imports from Agent

```python
# BEFORE (agent/executor.py)
from tinycua_sdk.storage.store import SessionStore
from tinycua_sdk.storage.models import Message

# AFTER
# No storage imports
```

### Remove storage-backed methods from Agent

```python
# BEFORE
class AgentExecutor:
    def _save_session(self, messages):
        SessionStore.save(self.session_id, messages)
    
    def _load_session(self):
        return SessionStore.load(self.session_id)

# AFTER
class AgentExecutor:
    # No session storage methods
    # Consumer passes messages directly to run()
```

## Impact Analysis

### Files that import from storage/

```bash
grep -r "from tinycua_sdk.storage" src/tinycua-sdk/tinycua_sdk/
grep -r "import tinycua_sdk.storage" src/tinycua-sdk/tinycua_sdk/
```

### Expected impact

- `agent/executor.py` — Remove session store interactions
- `agent/agent.py` — Remove storage-related parameters
- `cli/*.py` — Will be deleted in Stage 07 anyway
- `clients/*.py` — Will be deleted in Stage 07 anyway

## Consumer Migration Guide

### Before (SDK provides storage)
```python
from tinycua_sdk import Agent, Session
from tinycua_sdk.storage.store import SessionStore

session = Session.create("user-123")
SessionStore.save(session)
messages = SessionStore.load(session.id)
```

### After (Consumer provides storage)
```python
from tinycua_sdk import Agent, LLMModel
import sqlite3

# Consumer's own storage
class MySessionStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
    
    def save_messages(self, session_id, messages):
        # Consumer implements their own schema
        ...
    
    def load_messages(self, session_id):
        # Consumer implements their own queries
        ...

# Usage
store = MySessionStore("my_app.db")
messages = store.load_messages("user-123")
agent = Agent(llm_model=LLMModel())
response = await agent.run("Hello", messages=messages)
store.save_messages("user-123", messages + [...])
```

## Acceptance Criteria

- [ ] `storage/` package is deleted entirely.
- [ ] No imports from `tinycua_sdk.storage` remain in the codebase.
- [ ] No file I/O or database operations in `tinycua_sdk/`.
- [ ] `pytest` still passes for remaining tests.
- [ ] `Agent` does not reference storage in any way.

## Dependencies

- **Requires**: Stage 01, Stage 02.
- **Blocks**: None (can proceed in parallel with Stages 03, 05–07).
