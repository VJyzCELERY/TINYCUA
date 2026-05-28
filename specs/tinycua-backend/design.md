# Design Document: tinycua-backend

**Spec**: `specs/tinycua-backend/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-16

---

## Overview

This design document outlines a simple backend API that stores session metadata. The SDK handles all session management, tool execution, and local state. The backend provides persistence for session metadata (ID, name, timestamps, status) to enable future multi-device scenarios.

---

## Architecture

### Component Overview

```
┌─────────────────┐     ┌─────────────────┐
│   tinycua-sdk   │     │ tinycua-backend │
│                 │     │                 │
│  - Runner       │     │  - REST API     │
│  - Session      │────▶│  - SQLite DB    │
│  - Tools        │     │  - Session Meta │
│  - Local State  │     │                 │
└─────────────────┘     └─────────────────┘
```

- **SDK (Local)**: Handles runner, tools, message history, tool execution, local session storage
- **Backend (Remote)**: Stores only session metadata (not content) for persistence/sync

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| tinycua_backend | New | Main backend package |
| tinycua_backend.api | New | API endpoints |
| tinycua_backend.db | New | Database layer |
| tinycua_sdk.session | Modified | Add backend sync capability |

---

## Data Model

### SessionMetadata

```python
# Stored in backend database
SessionMetadata:
    id: str           # UUID, primary key
    name: str         # Session name
    created_at: datetime  # Creation timestamp (ISO 8601)
    updated_at: datetime  # Last update timestamp (ISO 8601)
    status: str       # active, archived, deleted
```

### Schema

SQLite table `sessions`:

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);
```

---

## API / Interface Contracts

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/sessions | Create session metadata |
| GET | /api/v1/sessions | List all sessions |
| GET | /api/v1/sessions/{id} | Get single session |
| PATCH | /api/v1/sessions/{id} | Update session metadata |
| DELETE | /api/v1/sessions/{id} | Delete session metadata |

### Request/Response Formats

**POST /api/v1/sessions**

Request:
```json
{
    "id": "uuid-string",
    "name": "Session Name",
    "created_at": "2026-03-16T10:00:00Z",
    "updated_at": "2026-03-16T10:00:00Z",
    "status": "active"
}
```

Response (201):
```json
{
    "id": "uuid-string",
    "name": "Session Name",
    "created_at": "2026-03-16T10:00:00Z",
    "updated_at": "2026-03-16T10:00:00Z",
    "status": "active"
}
```

**GET /api/v1/sessions**

Response (200):
```json
{
    "sessions": [
        {
            "id": "uuid-string",
            "name": "Session Name",
            "created_at": "2026-03-16T10:00:00Z",
            "updated_at": "2026-03-16T10:00:00Z",
            "status": "active"
        }
    ]
}
```

### Error Handling

| Error Case | Response | Notes |
|------------|----------|-------|
| Session not found | 404 Not Found | |
| Invalid session data | 400 Bad Request | Validation error |
| Duplicate session ID | 409 Conflict | |

---

## Implementation Phases

### Phase 1 — MVP

- [ ] Set up backend project structure
- [ ] Implement SQLite database layer
- [ ] Implement session CRUD API endpoints
- [ ] Add basic validation
- [ ] Write unit tests for API and DB

### Phase 2 — Enhancements

- [ ] Add API key authentication
- [ ] Add pagination for session list
- [ ] Add SDK sync capability

---

## Technical Decisions

1. **Decision**: Use SQLite for simplicity
   - **Reason**: No external DB required, simple file-based storage
   - **Alternatives Considered**: PostgreSQL - rejected for complexity in MVP

2. **Decision**: Store only metadata, not session content
   - **Reason**: SDK handles all session content locally; backend only provides sync capability
   - **Alternatives Considered**: Full session storage - rejected per spec non-goals

3. **Decision**: Use FastAPI for REST API
   - **Reason**: Fast to implement, built-in validation, easy to use
   - **Alternatives Considered**: Flask - more boilerplate

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SDK offline not handled | Medium | Medium | SDK should queue requests and sync when online |
| No authentication | High | High | Add API key in Phase 2 |

---

## Open Questions _(optional)_

1. **Should backend validate UUID format?**
   - Current thinking: Yes, reject invalid UUIDs at API layer

---

## References

- Spec: `specs/tinycua-backend/spec.md`
