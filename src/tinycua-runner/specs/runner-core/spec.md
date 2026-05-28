# Feature Specification: tinycua-runner Core

**Status**: Draft
**Created**: 2026-03-17
**Last Updated**: 2026-03-17
**Subproject**: tinycua-runner

---

## Problem Statement

**Goals**: Build the tinycua-runner service that:
1. Validates authentication from backend
2. Executes agents using tinycua-sdk
3. Uses SessionStore to access session context (via provided db_url)
4. Streams results back to backend via SSE
5. Handles concurrent executions

**Gaps**:
- No existing runner service
- Need to integrate with SDK
- Need session context tools

**Non-Goals**:
- Multiple runner instances management (handled by backend)
- Authentication for external clients (only accepts internal requests)

---

## User Scenarios

### Backend Triggers Execution
1. **Given** a valid runner token, **when** backend sends execution request, **then** runner executes agent with context

2. **Given** session with messages, **when** runner executes, **then** context tools (grep, semantic, summary, recent) can access session data

3. **Given** multiple concurrent requests, **when** runner receives them, **then** each executes independently with its own session context

---

## Requirements

### FR-001: Runner Token Authentication

The runner MUST validate the runner token from backend:

- Token passed via `Authorization: Bearer <token>`
- Must match configured `RUNNER_TOKEN` environment variable
- Return 401 if invalid

### FR-002: Execution Endpoint

The runner MUST expose:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/internal/v1/run` | Execute agent |

**Request**:
```json
{
  "agent_config": {...},
  "session_id": "uuid",
  "db_url": "postgresql://user:pass@localhost:5432/tinycua",
  "user_input": "What is my name?",
  "tools": [...],
  "messages": [...]
}
```

**Response**: SSE stream of events

### FR-003: Tool Bundle Registration

The runner MUST handle bundled tools from backend:
- Receive `tools` array in request (optional)
- Each tool bundle contains: name, description, parameters, source, external_dependencies, tool_dependencies, version
- Register tools to local ToolRegistry
- Materialize tools from source code using `exec()`
- Dependencies are already resolved by backend (bundled together)

### FR-004: SessionStore Integration

The runner MUST connect to the provided database URL:
- Creates SessionStore with provided `db_url`
- Uses context tools to access session data
- Tools work natively with SessionStore

### FR-005: Context Tools

The runner MUST provide context retrieval tools:
- `search_context_grep(query)` - Text search
- `search_context_semantic(query)` - Semantic search (if embeddings available)
- `get_context_summary()` - Get session summary
- `get_recent_turns(count)` - Get recent turns

### FR-006: Streaming Response

The runner MUST stream results back:
- Use SSE (Server-Sent Events) format
- Forward all events from SDK Runner
- Handle connection close gracefully

### FR-007: Concurrent Execution

The runner MUST handle concurrent requests:
- Each request gets its own session context
- Requests don't interfere with each other
- Use async/await for handling multiple requests

---

## Acceptance Criteria

1. Runner validates runner token from backend
2. Execution endpoint accepts requests with agent_config, session_id, db_url, tools
3. Bundled tools are registered to local registry
4. SessionStore connects to provided db_url
5. Context tools work (grep, semantic, summary, recent)
6. SSE streaming works correctly
7. Multiple concurrent requests handled properly

---

## Review Checklist

- [ ] No implementation details
- [ ] All mandatory sections completed
- [ ] Requirements are testable
- [ ] Scope clearly bounded
