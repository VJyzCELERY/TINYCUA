# Feature Specification: tinycua-backend Core

**Status**: Draft
**Created**: 2026-03-17
**Last Updated**: 2026-03-17
**Subproject**: tinycua-backend

---

## Problem Statement

**Goals**: Build the tinycua-backend service that:
1. Provides agent storage and management (CRUD)
2. Handles authentication (JWT + API keys) with multi-tenancy
3. Manages sessions and session messages
4. Triggers execution on tinycua-runner
5. Streams results back to client

**Gaps**:
- No existing backend service
- Need auth system for multi-tenant access
- Need session management
- Need runner integration

**Non-Goals**:
- Built-in frontend (separate project)
- Real-time WebSocket for chat (SSE is sufficient)

---

## User Scenarios

### SDK Client
1. **Given** a user with API key, **when** they call `Agent.deploy()` via SDK, **then** agent is stored in backend database

2. **Given** a user with API key, **when** they call `Agent.run()` with deployed agent, **then** backend triggers runner and streams results back

### Frontend Client
3. **Given** a user with JWT token, **when** they access `/v1/sessions/{id}`, **then** they can see their session and messages

### Multi-tenancy
4. **Given** a user in tenant A, **when** they list agents, **then** they only see their own tenant's agents

---

## Requirements

### FR-001: Configuration

The system MUST load configuration from `.config.yaml` in the project root

The config file MUST contain:
- `runner.url` - URL of the runner service
- `runner.token` - Token for runner authentication
- `database.url` - PostgreSQL connection string
- `auth.jwt_secret` - Secret for JWT signing
- `auth.jwt_algorithm` - Algorithm (HS256, RS256)
- `server.host` - Server host
- `server.port` - Server port

The config MUST auto-reload when the file changes

### FR-002: Authentication

The system MUST support two authentication methods:

**API Key (for SDK/programmatic access)**:
- Passed via `Authorization: Bearer <api_key>`
- Scopes: `agent:read`, `agent:write`, `session:read`, `session:write`
- Multi-tenant: Each API key belongs to a tenant

**JWT Token (for frontend clients)**:
- Passed via `Authorization: Bearer <jwt_token>`
- Contains: `sub` (user_id), `tenant_id`, `exp`
- Must validate signature using `auth.jwt_secret`

### FR-003: Multi-tenancy

The system MUST enforce tenant isolation:
- All resources (agents, sessions) belong to a tenant
- Users can only access their own tenant's resources
- API keys are tenant-scoped

### FR-004: Agent Management

The system MUST provide agent CRUD endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/agents` | Create agent |
| `GET` | `/v1/agents` | List agents (tenant-scoped) |
| `GET` | `/v1/agents/{id}` | Get agent by ID |
| `PUT` | `/v1/agents/{id}` | Update agent |
| `DELETE` | `/v1/agents/{id}` | Delete agent |

**Agent fields**:
- `id` (UUID)
- `tenant_id` (UUID)
- `name` (string)
- `config` (JSON) - Agent configuration from SDK
- `is_active` (boolean)
- `created_at` (datetime)
- `updated_at` (datetime)

### FR-005: Session Management

The system MUST provide session endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/sessions` | List sessions |
| `GET` | `/v1/sessions/{id}` | Get session with messages |
| `POST` | `/v1/sessions/{id}/messages` | Add message to session |

**Session fields**:
- `id` (UUID)
- `tenant_id` (UUID)
- `agent_id` (UUID)
- `name` (string)
- `created_at` (datetime)
- `updated_at` (datetime)

**Message fields** (from unified storage):
- `id` (UUID)
- `session_id` (UUID)
- `role` (string)
- `content` (text)
- `reasoning` (text, nullable)
- `turn_index` (int)
- `is_archived` (boolean)
- `embedding` (JSON)
- `importance` (int)
- `memory_type` (string)
- `is_pinned` (boolean)
- `created_at` (datetime)

### FR-006: Agent Execution

The system MUST trigger execution on runner:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/agents/{id}/run` | Execute agent |

**Request**:
- `user_input` (string, required)
- `session_id` (string, optional) - existing session or new one

**Flow**:
1. Validate authentication
2. Load agent from DB
3. Load session (if session_id provided) with messages
4. Send request to runner with agent_config, session_id, db_url
5. Stream SSE response back to client
6. Store new messages in DB

### FR-007: Runner Integration

The system MUST communicate with runner:

**Request to runner**:
```
POST {runner.url}/internal/v1/run
Authorization: Bearer {runner.token}
Content-Type: application/json

{
  "agent_config": {...},
  "session_id": "uuid",
  "db_url": "postgresql://...",
  "user_input": "..."
}
```

**Response**: SSE stream of events

---

## Acceptance Criteria

1. Config loads from `.config.yaml` and auto-reloads on changes
2. API key authentication works with tenant isolation
3. JWT authentication works with signature validation
4. Agent CRUD endpoints work correctly
5. Session CRUD endpoints work correctly
6. Agent execution triggers runner and streams results
7. Multi-tenancy enforced on all endpoints
8. Runner authentication validated

---

## Review Checklist

- [ ] No implementation details
- [ ] All mandatory sections completed
- [ ] Requirements are testable
- [ ] Scope clearly bounded
