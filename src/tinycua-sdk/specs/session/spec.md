# Feature Specification: Session & Memory Tools

**Status**: Complete
**Created**: 2026-03-16
**Last Updated**: 2026-03-16
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

**Goals**: Provide built-in tools for agents to manage conversation state and persistent memory so that agents can:
1. Remember information across conversations
2. Create, save, and load sessions
3. Interrupt execution when needed

**Gaps** (addressed):
- ✅ No built-in tools for memory - SOLVED
- ✅ No session management utilities - SOLVED  
- ✅ No cancel mechanism - SOLVED

**Non-Goals**:
- Backend storage for memory (see backend spec)
- Semantic search/embeddings (see backend spec)
- Context retrieval tools (see backend spec - deployed mode only)

---

## User Scenarios

### Primary Scenario

A user creates an agent with memory tools. The agent can:
1. Remember user preferences
2. Create new sessions
3. Load past sessions
4. Cancel execution if needed

### Acceptance Scenarios

1. **Given** an agent with `remember` tool, **when** user says "Remember my name is Bob", **then** `remember("user_name", "Bob")` stores the value.

2. **Given** stored memory, **when** user asks "What's my name?", **then** `recall("user_name")` returns "Bob".

3. **Given** user wants to save conversation, **when** they call `save_session()`, **then** all messages saved to local storage.

4. **Given** saved sessions, **when** user calls `list_sessions()`, **then** returns list of all saved sessions.

5. **Given** a session ID, **when** user calls `load_session(id)`, **then** messages restored and agent continues.

6. **Given** long-running execution, **when** user calls `agent.cancel()`, **then** execution stops gracefully.

---

## Requirements

### Memory Tools

- **FR-001**: `remember(key: str, value: str)` - Store key-value pair in memory
- **FR-002**: `recall(key: str)` - Retrieve value by key
- **FR-003**: `forget(key: str)` - Delete key from memory
- **FR-004**: `list_memory()` - List all memory keys
- **FR-005**: `clear_memory()` - Clear all memory
- **FR-006**: Memory stored in `~/.tinycua/memory.json` (local) or backend API (remote)
- **FR-007**: Hybrid storage - tries remote first, falls back to local

### Session Utilities (NOT tools)

- **FR-010**: `create_session(name: str)` - Create new session, returns session_id
- **FR-011**: `save_session(session_id: str, messages: list)` - Save messages to session
- **FR-012**: `load_session(session_id: str)` - Load session by ID
- **FR-013**: `list_sessions()` - List all saved sessions
- **FR-014**: `delete_session(session_id: str)` - Delete a session
- **FR-015**: Sessions stored in `~/.tinycua/sessions/`

### Cancel Mechanism

- **FR-020**: `agent.cancel()` - Cancel current execution
- **FR-021**: `agent.cancel_event` - asyncio.Event for interrupt
- **FR-022**: `agent.is_cancelled` - Check cancel state
- **FR-023**: `agent.reset_cancel()` - Reset cancel for next run
- **FR-024**: Runner checks cancel during streaming

### Storage

- **FR-030**: Local storage in `~/.tinycua/`
- **FR-031**: Remote storage via backend API (optional)
- **FR-032**: Fallback to local when remote unavailable

---

## Implementation

### Storage Structure

```
~/.tinycua/
├── memory.json        # remember/recall storage
└── sessions/
    ├── {uuid1}.json
    └── {uuid2}.json
```

### Memory Backends

| Backend | Description |
|---------|-------------|
| LocalMemoryBackend | JSON file storage |
| RemoteMemoryBackend | Backend API storage |
| HybridMemoryBackend | Tries remote, falls back to local |

### Configuration

```python
# Via environment
TINYCUA_BACKEND_URL=http://localhost:8000
TINYCUA_API_KEY=your_key
TINYCUA_MEMORY_LOCAL_ONLY=false  # or true to disable remote

# Or programmatically
from tinycua_sdk.tools.memory import get_memory_backend
backend = get_memory_backend(
    backend_url="http://localhost:8000",
    api_key="your_key",
    local_only=False
)
```

### Tools vs Utilities

| Type | Usage |
|------|-------|
| Memory tools | Available to agent (remember, recall, forget) |
| Session utilities | Manual usage (create_session, save_session, etc.) |

---

## Testing Plan

### Unit Tests
- ✅ remember stores correct value
- ✅ recall retrieves correct value
- ✅ forget removes value
- ✅ list_memory returns all keys
- ✅ clear_memory clears all
- ✅ Session create/save/load/list/delete work
- ✅ Hybrid backend fallback

### Integration Tests
- ✅ Full flow: remember → recall → forget
- ✅ Session create → save → load → list

---

## Status Tracker

| Item | Status |
|------|--------|
| Memory tools (remember, recall, forget) | ✅ Complete |
| Memory list/clear | ✅ Complete |
| Hybrid storage (remote + local fallback) | ✅ Complete |
| Session utilities | ✅ Complete |
| Cancel mechanism | ✅ Complete |
| Tests | ✅ Complete |

---

## Review Checklist

- [x] No implementation details
- [x] All mandatory sections completed
- [x] Requirements are testable
- [x] Scope clearly bounded
