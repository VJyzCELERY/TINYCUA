# Feature Specification: Session & Message Persistence

**Status**: Draft
**Created**: 2026-03-20
**Last Updated**: 2026-03-20
**Subproject(s) Affected**: tinycua-backend, tinycua-sdk

---

## Quick Guidelines

- Focus on **WHAT** users/callers need and **WHY** — not HOW to implement
- Every requirement must be independently testable

---

## Problem Statement

**Goals**:
- Create `messages` table on backend startup
- Make `/run` endpoint stateless (no session/message management)
- Provide explicit SDK methods for session/message management
- Allow developers to control when messages are saved

**Gaps**:
- Backend startup doesn't create `messages` table
- `/run` endpoint has session/message management logic that should be separate
- No explicit SDK methods for managing sessions/messages
- Agent.run() should remain stateless

**Non-Goals**:
- Automatic message saving

---

## User Scenarios & Testing

### Primary Scenario

A developer wants to run a deployed agent and save the conversation to a session for later retrieval:

1. Create a session via BackendClient
2. Run agent (stateless, returns result)
3. Save user message, assistant response, and tool calls explicitly

### Acceptance Scenarios

#### Session Management
1. **Given** a user, **when** they call `POST /v1/sessions`, **then** a session is created and returned with ID.

2. **Given** a session exists, **when** they call `GET /v1/sessions/{id}/messages`, **then** all messages for that session are returned.

3. **Given** a session exists, **when** they call `POST /v1/sessions/{id}/messages` with role and content, **then** a message is created and returned.

#### Stateless Run
4. **Given** a deployed agent, **when** they call `POST /v1/agents/{id}/run`, **then** the endpoint returns LLM response without managing sessions or messages.

#### SDK Integration
5. **Given** BackendClient, **when** they call `create_session()`, **then** the backend creates a session and returns it.

6. **Given** BackendClient, **when** they call `get_messages(session_id)`, **then** messages are retrieved from the backend.

7. **Given** BackendClient, **when** they call `add_message(session_id, role, content)`, **then** a message is saved to the backend.

#### RunResult Usage
8. **Given** Agent.run() with `trace=True`, **when** the agent executes, **then** RunResult is returned with `response`, `tool_calls`, `usage`, and `trace` fields.

9. **Given** a RunResult with tool_calls, **when** saving, **then** each tool call can be serialized to JSON with `tool_name`, `arguments`, and `result`.

### Edge Cases

- What happens when session doesn't exist when adding message? (Return 404)
- What happens when backend is unavailable in deployed mode? (Raise error)
- What happens with multi-step execution and trace=True? (All steps captured in trace array)

---

## Requirements

### Functional Requirements

#### Backend: Tables Creation
- **FR-001**: Backend startup MUST create both backend tables and SDK tables (sessions, messages)
- **FR-002**: Messages table MUST be created via `SessionStore(config.database.url).create_tables()`

#### Backend: Stateless Run Endpoint
- **FR-003**: `/v1/agents/{id}/run` MUST NOT create or load sessions
- **FR-004**: `/v1/agents/{id}/run` MUST NOT load messages from database
- **FR-005**: `/v1/agents/{id}/run` MUST validate agent exists before execution
- **FR-006**: `/v1/agents/{id}/run` MUST stream LLM response from runner

#### Backend: Session Endpoints
- **FR-007**: `POST /v1/sessions` MUST create a new session
- **FR-008**: `GET /v1/sessions/{id}/messages` MUST return messages for a session
- **FR-009**: `POST /v1/sessions/{id}/messages` MUST add a message to a session
- **FR-010**: Session endpoints MUST validate tenant ownership

#### SDK: BackendClient Methods
- **FR-011**: BackendClient MUST have `create_session(agent_id, name)` method
- **FR-012**: BackendClient MUST have `get_messages(session_id)` method
- **FR-013**: BackendClient MUST have `add_message(session_id, role, content)` method

#### SDK: RunResult
- **FR-014**: Agent.run() with `trace=True` MUST return RunResult with `response`, `tool_calls`, `usage`, `trace`
- **FR-015**: RunResult.tool_calls MUST contain ToolCall objects with `name`, `arguments`, `result`

#### SDK: Agent.run() Stateless
- **FR-016**: Agent.run() MUST NOT save messages automatically
- **FR-017**: Agent.run() MUST return result without side effects

---

## Key Entities

### Backend Session
```python
class Session:
    id: UUID (PK)
    tenant_id: str (FK to tenants)
    agent_id: str (FK to agents)
    name: str
    created_at: datetime
    updated_at: datetime
```

### Backend Message (via SessionStore)
```python
class Message:
    id: UUID (PK)
    session_id: UUID (FK to sessions)
    role: str  # "user", "assistant", "tool", "metadata"
    content: str
    turn_index: int
    created_at: datetime
```

### RunResult
```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    result: Any

@dataclass
class RunResult:
    response: str
    tool_calls: list[ToolCall]
    usage: dict[str, int]
    trace: list[dict[str, Any]]
    finish_reason: str | None
```

---

## API Specification

### POST /v1/sessions

**Request:**
```json
{
    "agent_id": "uuid",
    "name": "Chat 1"
}
```

**Response (201):**
```json
{
    "id": "uuid",
    "agent_id": "uuid",
    "name": "Chat 1",
    "created_at": "2026-03-20T10:00:00Z",
    "updated_at": "2026-03-20T10:00:00Z"
}
```

### GET /v1/sessions/{id}/messages

**Response (200):**
```json
[
    {
        "id": "uuid",
        "role": "user",
        "content": "Hello",
        "turn_index": 0,
        "created_at": "2026-03-20T10:00:00Z"
    }
]
```

### POST /v1/sessions/{id}/messages

**Request:**
```json
{
    "role": "user",
    "content": "Hello"
}
```

**Response (201):**
```json
{
    "id": "uuid",
    "role": "user",
    "content": "Hello",
    "turn_index": 0,
    "created_at": "2026-03-20T10:00:00Z"
}
```

---

## Success Criteria

- Backend creates messages table on startup
- `/run` endpoint is stateless
- Session/message endpoints work correctly
- SDK BackendClient has required methods
- Agent.run() is stateless and returns RunResult when trace=True
- Tool calls can be serialized to JSON for message saving

---

## Testing Plan

### Unit Tests

1. Backend: Test `/run` doesn't load/create sessions or messages
2. Backend: Test session endpoints create/retrieve messages correctly
3. SDK: Test BackendClient.create_session() calls correct endpoint
4. SDK: Test BackendClient.get_messages() returns messages
5. SDK: Test BackendClient.add_message() saves message

### Integration Tests

1. Full flow: Create session → Run agent → Save messages → Retrieve messages
2. Test RunResult contains correct tool_call data

---

## Open Questions

None.

---

## Review Checklist

- [ ] Library stack documented (if needed)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
