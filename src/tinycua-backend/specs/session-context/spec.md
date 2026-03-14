# Feature Specification: Session Context Management with Grep Search

**Status**: Draft
**Created**: 2026-03-14
**Last Updated**: 2026-03-14
**Subproject(s) Affected**: tinycua-backend

---

## Quick Guidelines

- Focus on **WHAT** users/callers need and **WHY** — not HOW to implement
- Avoid implementation details (no tech stack choices, class names, or code structure in this doc)
- Every requirement must be independently testable

---

## Problem Statement

**Goals**: Provide session context management so that an AI agent can maintain conversation history, search through past context, and have a frontloaded summary in its prompt.

**Gaps**: 
- Current session system stores messages in DB but provides no search capability
- No way for the agent to query past context beyond simple "last N messages"
- No automatic compaction when context grows large
- No persistent summary for long conversations

**Non-Goals**:
- Semantic/embedding-based search (deferred to Phase 2)
- Cross-session context sharing
- Real-time context sync across multiple clients

**Constraints**:
- Must work with existing `sessions` and `session_messages` tables
- Must integrate with existing `POST /v1/responses` endpoint
- Must extend, not replace, the existing `get_context` native tool

---

## User Scenarios & Testing

### Primary Scenario

A user creates a session and has a conversation with the AI. After many turns, the agent can:
1. Search past context using grep to find specific information
2. See a summary of the conversation at the start of its prompt
3. Continue the conversation without losing context

### Acceptance Scenarios

1. **Given** a session with 10+ turns, **when** the agent calls `search_context_grep("weather")`, **then** it returns all turns containing "weather" from the full archived context.

2. **Given** a session approaching context limit, **when** compaction triggers at 75% threshold, **then** older turns are archived to `full_context.md`, a summary is generated, and the last 3 turns remain active in the DB.

3. **Given** a session after compaction, **when** a new request arrives with `session_id`, **then** the summary is prepended to the input along with the last 3 active turns.

4. **Given** a compacted session, **when** compaction triggers again and still exceeds 75%, **then** the system recursively compacts (creates layered summaries).

5. **Given** a user with an API key, **when** they call `GET /v1/sessions/{id}/search?q=pattern`, **then** they receive grep results from their own session's context only.

### Edge Cases

- What happens when the session has fewer than 3 turns? (No compaction needed)
- What happens when `full_context.md` doesn't exist yet? (Only search active messages)
- What happens when model max_tokens is not configured? (Use default from config)
- What happens when summary generation fails? (Continue without summary, log error)

---

## Requirements

### Functional Requirements

- **FR-001**: The system MUST store session context in both DB (active) and file storage (archived) formats.
- **FR-002**: The system MUST generate a markdown summary via LLM when compaction triggers.
- **FR-003**: The system MUST keep the last 3 turns active in the DB after compaction.
- **FR-004**: The system MUST archive older turns to `full_context.md` during compaction.
- **FR-005**: The system MUST provide a grep-based search tool that searches through archived context.
- **FR-006**: The system MUST prepend the summary to the agent's input on every request when a session is active.
- **FR-007**: The system MUST trigger compaction when used_tokens / max_model_tokens exceeds 75%.
- **FR-008**: The system MUST support recursive compaction if context still exceeds 75% after initial compaction.
- **FR-009**: The system MUST read model max_tokens from a config file, defaulting to a configured value if not specified.
- **FR-010**: The system MUST ensure session context is user-scoped (users can only access their own sessions).
- **FR-011**: The existing `get_context` tool MUST continue to work and return the last 3 assistant messages.
- **FR-012**: New tools (`search_context_grep`, `get_context_summary`, `get_recent_turns`) MUST be available when a session is active.

### Key Entities

- **Session**: Existing entity (sess_xxx), now with `has_summary` and `summary_updated_at` fields
- **SessionMessage**: Existing entity, now with `turn_index` and `is_archived` fields
- **SummaryFile**: Markdown file at `{session_id}/summary.md` - frontloaded to agent
- **FullContextFile**: Markdown file at `{session_id}/full_context.md` - grep searchable archive

---

## Success Criteria

- **Agent can search past context**: Agent calls `search_context_grep` and receives relevant matches with turn context
- **Summary appears in prompt**: When a session has a summary, it is prepended to the input sent to the LLM
- **Compaction works**: After 75% threshold, older turns are archived, summary is generated, 3 turns remain active
- **Recursive compaction works**: If still over 75%, the system creates layered summaries
- **User isolation**: Users cannot access or search another user's session context
- **Backward compatibility**: Existing `get_context` tool continues to work

---

## Testing Plan

### Unit Tests

- Grep search returns correct matches from markdown content
- Turn indexing correctly numbers messages within a session
- Compaction logic correctly identifies 75% threshold
- File storage correctly reads/writes summary.md and full_context.md
- Summary generation prompt is correctly formatted

### Integration Tests

- Full flow: create session → add messages → trigger compaction → verify files created → verify summary in prompt
- Grep search: add messages → search → verify results include correct turns
- Recursive compaction: add many turns → trigger compaction → verify layered summaries
- User isolation: attempt to access another user's session → verify 404

### Manual Tests

- Create session with long conversation → verify summary is useful
- Test grep search with various patterns
- Verify compaction doesn't lose any context

---

## Open Questions

No open questions - all requirements are resolved.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
