# Feature Specification: Session Context Management

**Status**: Draft
**Created**: 2026-03-14
**Last Updated**: 2026-03-15
**Subproject(s) Affected**: tinycua-backend

---

## Quick Guidelines

- Focus on **WHAT** users/callers need and **WHY** — not HOW to implement
- Every requirement must be independently testable

---

## Library Stack

Based on research (see design.md for details):

| Component | Library | Notes |
|-----------|---------|-------|
| HTTP Client | httpx | Async + sync support |
| AI/Embeddings | python-ai-sdk | Embeddings + tool definitions |
| Tokenizer | tiktoken | Accurate token counting |
| ORM | SQLAlchemy | Database |
| Migrations | Alembic | Schema management |
| Serialization | Pydantic | Config + types |
| Retry | tenacity | Retry logic |
| Logging | structlog | Structured logging |
| Web Framework | FastAPI | REST API |
| Server | uvicorn | ASGI server |

---

## Research References

- **OpenCode**: Agent implementation, compaction template (Goal, Instructions, Discoveries, Accomplished, Relevant files)
- **Agent S3**: Best-of-N, behavior narratives
- **AIRI**: Memory system with pgvector
- **widemem**: Importance scoring (optional future consideration)
- **FastAPI**: Web framework for REST API

---

## Problem Statement

**Goals**: Provide session context management so that an AI agent can maintain conversation history, search through past context semantically, manage memory importance, recover from errors gracefully, and provide execution observability.

**Gaps**: 
- Current session system stores messages in DB but provides no search capability
- No way for the agent to query past context beyond simple "last N messages"
- No automatic compaction when context grows large
- No persistent summary for long conversations
- No semantic understanding of context (e.g., "weather" should find "temperature", "forecast")
- No importance scoring for memories
- No error recovery mechanisms
- No execution observability

**Non-Goals**:
- Cross-session context sharing
- Real-time context sync across multiple clients

**Constraints**:
- Must work with existing `sessions` and `session_messages` tables
- Must integrate with existing `POST /v1/responses` endpoint
- Must extend, not replace, the existing `get_context` native tool
- Must use OpenAI-compatible embedding API endpoints (Ollama, LM Studio, OpenAI, etc.)

---

## User Scenarios & Testing

### Primary Scenario

A user creates a session and has a conversation with the AI. After many turns, the agent can:
1. Search past context using semantic search to find conceptually related information
2. See a summary of the conversation at the start of its prompt
3. Continue the conversation without losing context
4. Pin important memories that won't be compacted
5. Understand when errors occur and see fallback behaviors
6. Observe step-by-step execution through traces

### Acceptance Scenarios

#### Semantic Search
1. **Given** a session with 10+ turns, **when** the agent calls `search_context("weather")`, **then** it returns all turns semantically related to weather (including "temperature", "forecast", "rain", etc.) from the archived context.

#### Compaction
2. **Given** a session approaching context limit, **when** compaction triggers at threshold, **then** older turns are archived to `full_context.md`, embeddings are stored in DB, a summary is generated, and the last 3 turns remain active in the DB.

3. **Given** a session after compaction, **when** a new request arrives with `session_id`, **then** the summary is prepended to the input along with the last 3 active turns.

4. **Given** a compacted session, **when** compaction triggers again and still exceeds threshold, **then** the system recursively compacts (creates layered summaries).

#### Search API
5. **Given** a user with an API key, **when** they call `GET /v1/sessions/{id}/search?q=query`, **then** they receive semantic search results from their own session's context only.

#### Embeddings
6. **Given** a new message is added to a session, **when** the message is saved, **then** an embedding is generated and stored with the message for future semantic search.

#### Memory Depth
7. **Given** a user, **when** they mark a message as important, **then** that message is pinned and excluded from compaction.

8. **Given** a message, **when** the system analyzes it, **then** an importance score (1-10) is auto-assigned using heuristic or LLM method.

9. **Given** memory types, **when** compaction occurs, **then** older turns transition from working to short_term automatically.

#### Error Recovery
10. **Given** embedding API failure, **when** semantic search is called, **then** the system falls back to grep search and logs the error.

11. **Given** a tool execution failure, **when** retry attempts are exhausted, **then** the error is reported to the agent with retry count.

12. **Given** repeated failures, **when** circuit breaker threshold is reached, **then** the component is temporarily disabled.

#### Observability
13. **Given** a session execution, **when** LLM or tool calls are made, **then** each operation is logged as a trace event with timing and metadata.

14. **Given** a user, **when** they want to debug execution, **then** they can retrieve the execution trace via API.

### Edge Cases

- What happens when the session has fewer than 3 turns? (No compaction needed)
- What happens when embedding API is unavailable? (Log error, fallback to grep)
- What happens when model max_tokens is not configured? (Use default from config)
- What happens when summary generation fails? (Continue without summary, log error)
- What happens when embedding dimension mismatch? (Validate against configured dimension)
- What happens when no embedding results found? (Return empty results gracefully)
- What happens when all retries are exhausted? (Report error to agent, allow fallback)
- What happens when circuit breaker trips? (Use fallback, indicate degraded mode)
- What happens when pinned memory limit is reached? (Reject new pins, suggest unpinning old)

---

## Requirements

### Functional Requirements

#### Core Context Management
- **FR-001**: The system MUST store session context in both DB (active with embeddings) and file storage (archived) formats.
- **FR-002**: The system MUST generate a markdown summary via LLM when compaction triggers.
- **FR-003**: The system MUST keep the last 3 turns active in the DB after compaction.
- **FR-004**: The system MUST archive older turns to `full_context.md` during compaction.
- **FR-005**: The system MUST provide semantic search using embeddings to search through archived context.
- **FR-006**: The system MUST prepend the summary to the agent's input on every request when a session is active.
- **FR-007**: The system MUST trigger compaction when used_tokens / max_model_tokens exceeds the configured threshold.
- **FR-008**: The system MUST support recursive compaction if context still exceeds threshold after initial compaction.
- **FR-009**: The system MUST read model max_tokens from config, defaulting to a configured value if not specified.
- **FR-010**: The system MUST ensure session context is user-scoped (users can only access their own sessions).
- **FR-011**: The existing `get_context` tool MUST continue to work and return the last 3 assistant messages.

#### Semantic Search & Embeddings
- **FR-012**: New tools (`search_context`, `get_context_summary`, `get_recent_turns`) MUST be available when a session is active.
- **FR-013**: The system MUST generate and store embeddings for each new message using an OpenAI-compatible embedding API.
- **FR-014**: The system MUST support configurable embedding providers (Ollama, LM Studio, OpenAI, etc.) via config.
- **FR-015**: The system MUST use cosine similarity for semantic search ranking.

#### Token Estimation
- **FR-016**: The system MUST use tiktoken for accurate token counting.
- **FR-017**: The system MUST auto-detect encoding from model name with config fallback.
- **FR-018**: The system MUST count tokens in real-time before each LLM call.
- **FR-019**: The system MUST apply a percentage-based buffer when calculating effective token limit.
- **FR-020**: The system MUST support smart compaction triggers (threshold-based and turn-count-based).

#### Memory Depth
- **FR-021**: The system MUST support memory types: working, short_term, long_term, and pinned.
- **FR-022**: The system MUST auto-transition memory types based on compaction and age.
- **FR-023**: The system MUST assign importance scores (1-10) to messages using heuristic or LLM method.
- **FR-024**: The system MUST allow users to pin important memories via API.
- **FR-025**: The system MUST allow LLM to suggest pinning with reason.
- **FR-026**: The system MUST exclude pinned memories from compaction.
- **FR-027**: The system MUST support configurable importance thresholds.
- **FR-028**: The system MUST limit maximum pinned memories per session.

#### Error Recovery
- **FR-029**: The system MUST retry failed operations with exponential backoff.
- **FR-030**: The system MUST implement fallback chain: semantic → grep → recent_turns.
- **FR-031**: The system MUST implement circuit breaker per component (embedding API, tool API, LLM API).
- **FR-032**: The system MUST make errors visible to the agent with fallback information.
- **FR-033**: The system MUST log all errors with appropriate severity levels.

#### Observability
- **FR-034**: The system MUST log LLM request/response events with timing and metadata.
- **FR-035**: The system MUST log tool call events with arguments and results.
- **FR-036**: The system MUST log compaction events with statistics.
- **FR-037**: The system MUST support retrieving execution traces via API.
- **FR-038**: The system MUST implement hierarchical trace structure (parent-child spans).

---

## Key Entities

- **Session**: Existing entity (sess_xxx), now with `has_summary` and `summary_updated_at` fields
- **SessionMessage**: Existing entity, now with `turn_index`, `is_archived`, `embedding`, `importance`, `memory_type`, `is_pinned` fields
- **SummaryFile**: Markdown file at `{session_id}/summary.md` - frontloaded to agent
- **FullContextFile**: Markdown file at `{session_id}/full_context.md` - archived turns
- **EmbeddingConfig**: Configuration for embedding provider (endpoint, model, dimension)
- **MemoryMetadata**: Entity for storing importance scores, memory types, and pinned status
- **ExecutionTrace**: Entity for storing trace events with spans
- **TokenUsage**: Entity for tracking token usage per request

---

## Success Criteria

- **Agent can search past context semantically**: Agent calls `search_context` and receives relevant matches based on meaning
- **Embeddings are stored**: Each message has an associated embedding stored in the DB
- **Summary appears in prompt**: When a session has a summary, it is prepended to the input sent to the LLM
- **Compaction works**: After threshold, older turns are archived, summary is generated, 3 turns remain active
- **Recursive compaction works**: If still over threshold, the system creates layered summaries
- **User isolation**: Users cannot access or search another user's session context
- **Backward compatibility**: Existing `get_context` tool continues to work
- **Token estimation accurate**: tiktoken provides accurate counting with buffer
- **Memory depth works**: Importance scores assigned, memory types transition, pinning works
- **Error recovery works**: Fallbacks work, retries work, circuit breakers trip correctly
- **Observability works**: Traces are logged, retrievable via API, show step-by-step execution

---

## Testing Plan

### Unit Tests

- Semantic search returns correct semantically similar results
- Embedding generation produces correct dimension output
- Turn indexing correctly numbers messages within a session
- Compaction logic correctly identifies threshold
- File storage correctly reads/writes summary.md and full_context.md
- Summary generation prompt is correctly formatted
- Token estimation matches tiktoken output
- Importance scoring assigns reasonable scores
- Memory type transitions correctly
- Fallback chain works correctly
- Circuit breaker trips at threshold
- Trace events logged correctly

### Integration Tests

- Full flow: create session → add messages → verify embeddings stored → trigger compaction → verify files created → verify summary in prompt
- Semantic search: add messages → search for related concept → verify results include semantically similar turns
- Recursive compaction: add many turns → trigger compaction → verify layered summaries
- User isolation: attempt to access another user's session → verify 404
- Embedding provider: test with Ollama, test with LM Studio, test with OpenAI
- Error recovery: simulate API failure → verify fallback → verify error visibility
- Observability: execute request → retrieve trace → verify all events present

### Manual Tests

- Create session with long conversation → verify summary is useful
- Test semantic search with various queries (synonyms, related concepts)
- Verify compaction doesn't lose any context
- Test embedding generation with different providers
- Pin important messages → verify they survive compaction
- Trigger errors → verify fallback behavior
- Retrieve traces → verify they show step-by-step execution

---

## Open Questions

No open questions - all requirements are resolved.

---

## Review Checklist

- [x] Library stack documented
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
