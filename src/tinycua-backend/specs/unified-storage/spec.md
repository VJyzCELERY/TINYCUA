# Feature Specification: Unified Database Storage

**Status**: Draft
**Created**: 2026-03-17
**Last Updated**: 2026-03-17
**Subproject(s) Affected**: tinycua-sdk, tinycua-backend

---

## Problem Statement

**Goals**: Unified memory and session storage that works for both local SDK and backend:
1. Single storage layer supporting SQLite (local) and PostgreSQL (production)
2. Advanced context retrieval available to both local and remote agents
3. Agent can choose which context retrieval tool to use

**Gaps**:
- Current SDK stores memory/session locally in JSON files only
- No unified storage that works across local and remote
- No advanced context retrieval (semantic, grep) available locally

**Non-Goals**:
- Real-time sync between local and remote storage
- Cross-session context sharing

---

## User Scenarios

### Local SDK Usage
1. **Given** a user running SDK locally, **when** they create an agent with session tools, **then** all data stored in local SQLite (`./tinycua.db`)

2. **Given** a local session, **when** the agent calls `search_context_grep("bob")`, **then** it searches the full_context_md in SQLite

3. **Given** a local session, **when** the agent calls `search_context_semantic("weather")`, **then** it calculates embedding similarity in Python

### Backend Usage
4. **Given** a user accessing via API, **when** they pass `X-Session-ID` header, **then** session data retrieved from PostgreSQL

5. **Given** a deployed agent, **when** it needs context, **then** it can use any retrieval tool (semantic/grep/summary/recent)

---

## Requirements

### FR-001

The system MUST support both SQLite (local) and PostgreSQL (production) via a single DATABASE_URL config

### FR-002

The system MUST store sessions with the following fields:
- id (UUID, PK)
- name (str)
- user_id (str)
- created_at (datetime)
- updated_at (datetime)
- has_summary (bool)
- summary_updated_at (datetime)
- summary_md (TEXT)
- full_context_md (TEXT)

### FR-003

The system MUST store messages with the following fields:
- id (UUID, PK)
- session_id (FK)
- role (str)
- content (text)
- reasoning (TEXT) -- agent reasoning/thinking (flexible for different model formats)
- turn_index (int)
- is_archived (bool)
- embedding (JSON) -- stored as JSON for SQLite, vector for PostgreSQL
- importance (int) -- 1-10
- memory_type (str) -- working/short_term/long_term/pinned
- is_pinned (bool)
- created_at (datetime)

Note: Tool calls are NOT stored in session context (they are execution details)

### FR-004

The system MUST provide context retrieval tools that the agent can choose:
- search_context_semantic(query: str)
- search_context_grep(query: str)
- get_context_summary()
- get_recent_turns()

### FR-005

For SQLite, embeddings MUST be stored as JSON and searched using Python cosine similarity

### FR-006

For PostgreSQL, embeddings SHOULD use pgvector when available, with JSON fallback

### FR-007

The agent MUST decide which context retrieval tool to use based on the query

### FR-008

Local SDK MUST default to SQLite at `./tinycua.db`

---

## Configuration

```bash
# SQLite (local default)
DATABASE_URL=sqlite:///./tinycua.db

# PostgreSQL (production)
DATABASE_URL=postgresql://user:pass@localhost/tinycua
```

---

## Acceptance Criteria

1. SQLite database created at `./tinycua.db` when using local SDK
2. PostgreSQL database used when DATABASE_URL points to PostgreSQL
3. Sessions stored with all required fields
4. Messages stored with all required fields including embeddings
5. search_context_grep returns matching results from full_context_md
6. search_context_semantic returns results based on embedding similarity
7. get_context_summary returns summary_md
8. get_recent_turns returns last 3 non-archived messages
9. Agent can choose which tool to use dynamically

---

## Future Considerations (Out of Scope)

### Events/Trace Table

For observability, a future Trace table is planned:

```
traces:
  - id (UUID, PK)
  - session_id (FK)
  - message_id (FK, optional) -- link to parent message
  - event_type (str) -- llm_request, llm_response, tool_call, tool_result
  - parent_span_id (UUID) -- for hierarchical tracing
  - metadata (JSON) -- timing, model, tokens, tool args/results
  - created_at (datetime)
```

This enables:
- Step-by-step execution replay
- Debugging agent behavior
- Performance monitoring
- Each message can reference its trace for detailed inspection

---

## Review Checklist

- [ ] No implementation details
- [ ] All mandatory sections completed
- [ ] Requirements are testable
- [ ] Scope clearly bounded
