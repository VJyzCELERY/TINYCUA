# Feature Specification: tinycua-backend

**Status**: Draft
**Created**: 2026-03-16
**Last Updated**: 2026-03-16
**Subproject(s) Affected**: tinycua-backend, tinycua-sdk

---

## Quick Guidelines

- Focus on **WHAT** users/callers need and **WHY** — not HOW to implement
- Avoid implementation details (no tech stack choices, class names, or code structure in this doc)
- Mark unclear requirements with `[NEEDS CLARIFICATION: specific question]`
- Every requirement must be independently testable
- Highlight anything that could violate KISS, YAGNI, or DRY for architecture review
- When done, requirements with `[NEEDS CLARIFICATION]` markers must be resolved before implementation begins

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a simple backend API that stores session metadata while keeping session management logic in the SDK. This allows the SDK to handle runner, tools, and local session state while the backend provides persistence for session metadata across devices.
- **Gaps**: Currently, there's no backend implementation. The SDK handles sessions locally but has no way to persist or sync session metadata across instances.
- **Non-Goals**: This spec does NOT cover:
  - User authentication/authorization (handled separately)
  - Tool execution (SDK handles this)
  - LLM inference (handled by local providers like LM Studio/Ollama)
  - Session content storage (SDK handles this locally)
- **Constraints**: 
  - Backend must expose REST API
  - Session data remains local to SDK (only metadata synced)
  - Must support future multi-device scenarios

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A user runs the SDK locally to create and manage agent sessions. The SDK maintains local session state (messages, tools, context). When needed, the SDK syncs session metadata (ID, name, created_at, updated_at, status) to the backend for persistence. Other SDK instances can fetch this metadata to display session lists.

### Acceptance Scenarios

1. **Given** a new session is created in SDK, **When** the SDK calls the backend to save metadata, **Then** the backend stores the session metadata and returns success
2. **Given** a session exists in the backend, **When** another SDK instance requests session list, **Then** the backend returns all session metadata
3. **Given** a session is deleted locally, **When** the SDK calls the backend to delete metadata, **Then** the backend removes the session metadata

### Edge Cases

- What happens when the backend is unavailable? - SDK should work offline, sync when available
- How does the system handle duplicate session IDs? - Backend should reject or merge
- What is the behavior with empty/null session metadata? - Backend should validate and reject invalid data

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Backend MUST expose REST API endpoints for CRUD operations on session metadata
- **FR-002**: Backend MUST store session metadata: id, name, created_at, updated_at, status
- **FR-003**: Backend MUST provide endpoint to list all sessions
- **FR-004**: Backend MUST provide endpoint to get a single session by ID
- **FR-005**: Backend MUST provide endpoint to update session metadata
- **FR-006**: Backend MUST provide endpoint to delete session metadata
- **FR-007**: Backend MUST validate incoming session metadata (required fields, format)
- **FR-008**: SDK MUST be able to sync session metadata to backend independently of local session state

### Key Entities _(include if feature involves data)_

- **SessionMetadata**: Represents session metadata stored in backend
  - id: unique identifier (UUID)
  - name: session name
  - created_at: creation timestamp
  - updated_at: last update timestamp
  - status: session status (active, archived, deleted)

---

## Success Criteria _(mandatory)_

Objective, measurable checks that prove the problem is solved.

- **User can create session**: SDK creates local session, syncs metadata to backend
- **User can list sessions**: Backend returns all session metadata
- **User can delete session**: Backend removes session metadata when SDK deletes
- **Offline works**: SDK functions without backend; syncs when available

---

## Testing Plan _(mandatory)_

### Unit Tests

- Session metadata validation
- API endpoint request/response handling
- Database operations

### Integration Tests

- Full CRUD workflow: create → read → update → delete session metadata
- SDK-backend sync workflow

### Manual Tests

- Create session via SDK, verify metadata appears in backend
- Delete session locally, verify metadata removed from backend

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Session CRUD API | TODO | Endpoints for create, read, update, delete |
| Database schema | TODO | Session metadata table |
| SDK integration | TODO | Sync session metadata to backend |

---

## Open Questions _(optional)_

1. **Authentication method**
   - **Owner**: TBD
   - **Target**: 2026-03-16
   - **Status**: Discussion
   - **Proposed Answer**: API key for initial version

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
