# Design Document: Session Context Management

**Spec**: `specs/session-context/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-15

---

## Overview

This design adds comprehensive session context management with embedding-based semantic search, memory depth with importance scoring, error recovery with fallback chains, and observability with execution traces.

**Key Architectural Decisions**:
- Hybrid storage: DB for active messages with embeddings, file storage for archived context
- Semantic search using embeddings (cosine similarity)
- OpenAI-compatible embedding API (Ollama, LM Studio, OpenAI)
- Recursive compaction with layered summaries
- Hierarchical memory types with importance scoring
- Retry with exponential backoff + circuit breaker
- Prefect-style execution traces
- Custom agent loop (inspired by OpenCode approach)

---

## Library Stack

Based on research:

| Component | Library | Usage |
|-----------|---------|-------|
| HTTP Client | **httpx** | All HTTP calls, async + sync |
| AI/Embeddings | **python-ai-sdk** | embed_many, cosine_similarity, tool decorator |
| Tokenizer | **tiktoken** | Token counting |
| ORM | **SQLAlchemy** | Database |
| Migrations | **Alembic** | Schema management |
| Serialization | **Pydantic** | Config + types |
| Retry | **tenacity** | Retry logic |
| Logging | **structlog** | Structured logging |
| Web Framework | **FastAPI** | REST API |
| Server | **uvicorn** | ASGI server |

### Why python-ai-sdk?

- **Zero-configuration** embeddings with batching
- Built-in **cosine_similarity** for semantic search
- Tool definition decorator (we build custom executor)
- Provider-agnostic (OpenAI, Anthropic)

### Why Custom Agent Loop?

Following **OpenCode's approach**:
- Build custom orchestration (don't use LangGraph)
- Use python-ai-sdk for provider abstraction + embeddings
- Control the loop: LLM → tools → LLM cycle
- Full control over compaction, memory, error recovery

---

## Project Structure

```
src/tinycua-backend/
├── pyproject.toml           # Dependencies
├── tinycua_backend/
│   ├── __init__.py
│   ├── logging.py           # structlog setup
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py          # SQLAlchemy base
│   │   ├── session.py       # Session factory
│   │   └── migrations/
│   │       ├── env.py
│   │       └── versions/
│   ├── http/
│   │   ├── __init__.py
│   │   ├── client.py        # HTTPClient wrapper
│   │   └── exceptions.py    # Custom exceptions
│   ├── config/
│   │   ├── __init__.py
│   │   ├── models.py        # Pydantic models
│   │   ├── settings.py      # Settings class
│   │   ├── default.yaml
│   │   ├── models.yaml
│   │   └── embedding.yaml
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py          # Base provider
│   │   ├── openai.py        # OpenAI provider
│   │   ├── anthropic.py     # Anthropic provider
│   │   └── factory.py       # Provider factory
│   ├── context/
│   │   ├── __init__.py
│   │   ├── storage.py       # File storage
│   │   ├── search.py        # Semantic search
│   │   ├── summary.py        # Summary generation
│   │   └── compaction.py     # Compaction logic
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── manager.py       # Memory manager
│   │   └── scoring.py       # Importance scoring
│   ├── error/
│   │   ├── __init__.py
│   │   ├── retry.py         # Retry logic
│   │   ├── fallback.py      # Fallback chains
│   │   └── circuit.py       # Circuit breaker
│   ├── tracing/
│   │   ├── __init__.py
│   │   └── tracer.py        # Execution tracer
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py      # Tool registry
│   │   └── definitions.py   # Tool definitions
│   ├── agent/
│   │   ├── __init__.py
│   │   └── orchestrator.py  # Custom agent loop
│   └── api/
│       ├── __init__.py
│       └── routes.py        # API routes
└── tests/
    ├── unit/
    │   ├── test_logging.py
    │   ├── test_database.py
    │   ├── test_http_client.py
    │   ├── test_config.py
    │   └── test_providers.py
    └── integration/
        ├── test_api.py
        └── test_full_flow.py
```

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        tinycua-backend                              │
│                                                                     │
│  ┌──────────────┐    ┌────────────────┐    ┌──────────────────┐  │
│  │ POST         │    │ Orchestration  │    │ SessionContext   │  │
│  │ /v1/responses│───▶│ Loop           │───▶│ Manager          │  │
│  └──────────────┘    └───────┬────────┘    └────────┬─────────┘  │
│                              │                      │             │
│                              ▼                      ▼             │
│                    ┌────────────────┐    ┌──────────────────┐   │
│                    │ Provider       │    │ ContextStorage   │   │
│                    │ (Ollama/LM    │    │ (DB + Files)    │   │
│                    │  Studio)      │    │ + Embeddings    │   │
│                    └────────────────┘    └──────────────────┘   │
│                              │                      │             │
│                              ▼                      ▼             │
│                    ┌────────────────┐    ┌──────────────────┐   │
│                    │ Embedding      │    │ TokenEstimator   │   │
│                    │ Service        │    │ (tiktoken)      │   │
│                    └────────────────┘    └──────────────────┘   │
│                              │                      │             │
│                              ▼                      ▼             │
│                    ┌────────────────┐    ┌──────────────────┐   │
│                    │ MemoryManager │    │ ErrorRecovery    │   │
│                    │ (depth/types) │    │ (retry/fallback)│   │
│                    └────────────────┘    └──────────────────┘   │
│                                        │                        │
│                                        ▼                        │
│                              ┌─────────────────────┐           │
│                              │ ExecutionTracer    │           │
│                              │ (traces/spans)    │           │
│                              └─────────────────────┘           │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Tools available to agent                                     │ │
│  │ - get_context (existing)                                      │ │
│  │ - search_context                                             │ │
│  │ - get_context_summary                                        │ │
│  │ - get_recent_turns                                           │ │
│  │ - pin_memory / unpin_memory                                 │ │
│  │ - suggest_pin                                                │ │
│  │ - get_execution_trace                                        │ │
│  │ - force_compact                                              │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Storage Layout

```
TINYCUA_DATA_DIR/
└── sessions/
    └── {session_id}/
        ├── summary.md           # Frontloaded to agent prompt
        └── full_context.md     # Archived turns
```

---

## 0. Compaction Template (OpenCode-Inspired)

Inspired by **OpenCode's compaction system** (`compaction.ts`):

### Summary Template

Use this structure when generating session summaries:

```markdown
## Goal

[What goal(s) is the user trying to accomplish?]

## Instructions

- [What important instructions did the user give you that are relevant]
- [If there is a plan or spec, include information about it so next agent can continue using it]

## Discoveries

[What notable things were learned during this conversation that would be useful for the next agent to know when continuing the work]

## Accomplished

[What work has been completed, what work is still in progress, and what work is left?]

## Relevant files / directories

[Construct a structured list of relevant files that have been read, edited, or created that pertain to the task at hand. If all the files in a directory are relevant, include the path to the directory.]
```

### Compaction Buffer

Following OpenCode's approach:
- Reserve a configurable token buffer (default: 20,000 tokens)
- Calculate: `usable_tokens = model_limit.input - reserved`
- Trigger compaction when: `current_tokens >= usable_tokens`

### Pruning vs Compaction

OpenCode separates these concepts:
- **Pruning**: Strip old tool call outputs (keep context, remove large outputs)
- **Full compaction**: Archive turns to file, generate summary, keep recent turns

Consider implementing pruning first, then full compaction as needed.

---

## Data Model

### Database Schema Changes

**Table: `sessions`** (modify)
| Column | Type | Notes |
|--------|------|-------|
| `has_summary` | bool NOT NULL DEFAULT false | Whether summary exists |
| `summary_updated_at` | datetime | Last time summary was generated |
| `compaction_config` | JSON | Per-session compaction preferences |

**Table: `session_messages`** (modify)
| Column | Type | Notes |
|--------|------|-------|
| `turn_index` | int NOT NULL | Order within session (1, 2, 3, ...) |
| `is_archived` | bool NOT NULL DEFAULT false | True if moved to full_context.md |
| `embedding` | blob | Serialized embedding vector (JSON) |
| `importance` | int DEFAULT 5 | Importance score 1-10 |
| `memory_type` | str DEFAULT 'working' | working/short_term/long_term/pinned |
| `is_pinned` | bool NOT NULL DEFAULT false | True if pinned |
| `pinned_by` | str | 'user' or 'llm' |
| `pinned_reason` | str | Reason for pinning |

**Table: `memory_metadata`** (new)
| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | Auto-increment |
| `session_id` | str NOT NULL | FK to sessions |
| `message_id` | int NOT NULL | FK to session_messages |
| `importance` | int NOT NULL DEFAULT 5 | 1-10 scale |
| `memory_type` | str NOT NULL DEFAULT 'working' | working/short_term/long_term/pinned |
| `is_pinned` | bool NOT NULL DEFAULT false | Pinned status |
| `pinned_by` | str | 'user' or 'llm' |
| `pinned_reason` | str | Optional reason |
| `auto_generated` | bool NOT NULL DEFAULT true | LLM-assigned vs user-tagged |
| `created_at` | datetime NOT NULL | Timestamp |
| `updated_at` | datetime NOT NULL | Timestamp |

**Table: `execution_traces`** (new)
| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | Auto-increment |
| `session_id` | str NOT NULL | FK to sessions |
| `trace_id` | str NOT NULL | Unique per session execution |
| `span_id` | str NOT NULL | Hierarchical span ID |
| `parent_span_id` | str | Parent span ID |
| `event_type` | str NOT NULL | llm_request, tool_call, etc. |
| `event_data` | JSON NOT NULL | Flexible payload |
| `created_at` | datetime NOT NULL | Timestamp |

**Table: `token_usage`** (new)
| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | Auto-increment |
| `session_id` | str NOT NULL | FK to sessions |
| `model` | str NOT NULL | Model used |
| `prompt_tokens` | int NOT NULL | Tokens in prompt |
| `completion_tokens` | int NOT NULL | Tokens in completion |
| `total_tokens` | int NOT NULL | Total tokens |
| `context_before` | int NOT NULL | Context tokens before |
| `context_after` | int NOT NULL | Context tokens after |
| `compaction_triggered` | bool NOT NULL | Whether compaction ran |
| `created_at` | datetime NOT NULL | Timestamp |

---

## 1. Token Estimation

### Approach

| Component | Implementation |
|-----------|----------------|
| **Tokenizer** | tiktoken library |
| **Model Detection** | Auto-detect from model name → fallback to config |
| **Counting** | Real-time before each LLM call |
| **Buffer** | Percentage-based (configurable) |

### Encoding Auto-Detection

```python
MODEL_ENCODING_MAP = {
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "gpt-4o": "cl100k_base",
    "gpt-4o-mini": "cl100k_base",
    "o1": "cl100k_base",
    "o1-mini": "cl100k_base",
    "llama": "cl100k_base",
    "llama2": "cl100k_base",
    "llama3": "cl100k_base",
    "mistral": "cl100k_base",
    "qwen": "cl100k_base",
    "qwen2": "cl100k_base",
    "phi": "cl100k_base",
    "gemini": "cl100k_base",
}
```

### Token Counting Flow

```
Before each LLM call:
1. Get model name → determine encoding
2. Count tokens in:
   - System prompt
   - Summary (if exists)
   - Active messages
   - Current input
3. Apply buffer: effective_limit = max_tokens * (1 - buffer_percentage)
4. If current > effective_limit:
   a. Trigger compaction
   b. Recount after compaction
   c. If still over, trigger again (recursive, max 3 times)
```

### Smart Compaction Triggers

| Trigger | Condition | Priority |
|---------|-----------|----------|
| **Threshold** | usage > (1 - buffer_percentage) | High |
| **Turn Count** | After N turns (configurable, default: 20) | Medium |
| **Manual** | API call to force compaction | Low |
| **Hybrid** | Weighted combination | High |

### Configuration

```yaml
token_estimation:
  tokenizer: "tiktoken"
  buffer_percentage: 0.1  # 10% buffer, trigger at 90%

  # Auto-detection mapping
  encoding_map:
    gpt-4: "cl100k_base"
    llama3: "cl100k_base"
    # Add model-specific overrides

  # Fallback if model not recognized
  default_encoding: "cl100k_base"
  default_max_tokens: 16384

  compaction:
    trigger_threshold: 0.9  # 90% (after buffer)
    turns_threshold: 20    # Trigger after N turns
    smart_algorithm: true  # Use hybrid approach
    max_recursive_attempts: 3
```

---

## 2. Memory Depth

### Memory Types

| Type | Description | Retention |
|------|-------------|-----------|
| **working** | Current context in LLM window | Until next compaction |
| **short_term** | Recent memories | Until long-term or explicit archive |
| **long_term** | Archived, searchable | Indefinite |
| **pinned** | User/LLM marked important | Never auto-delete |

### Auto-Transition Rules

```
After each compaction:
- Recent N turns → working (N = config.working_turns, default 3)
- Previous turns → short_term
- short_term > short_term_retention_days → prompt for long_term or auto-archive
```

### Importance Scoring

**Hybrid Method (Recommended)**:
1. **Heuristic (fast, no LLM)**:
   - Base score: 5
   - Keywords: "important", "remember", "don't forget", "critical" → +3
   - Length > 500 chars → +2
   - Tool success → +1
   - Tool error → -1

2. **LLM Refinement (optional, more accurate)**:
   - After response generation, use lightweight model to score
   - Can be enabled/disabled via config

### Pinning

| Action | Method |
|--------|--------|
| **User pin** | `POST /sessions/{id}/pin/{message_id}` |
| **LLM suggest** | `suggest_pin(message_id, reason)` → stored for user approval |
| **Unpin** | `DELETE /sessions/{id}/pin/{message_id}` |
| **Max pinned** | Configurable (default: 50) |

### Configuration

```yaml
memory:
  importance:
    # Scoring method: "heuristic", "llm", or "hybrid"
    scoring_method: "hybrid"

    # For LLM scoring (if enabled)
    llm_model: "tiny-embed"
    llm_score_threshold: 7  # Score above this is "important"

    # Thresholds (configurable)
    thresholds:
      high: 7
      medium: 4
      low: 1

    # Keyword bonuses for heuristic
    keyword_bonus:
      - "important"
      - "remember"
      - "don't forget"
      - "critical"
      - "key"
      - "essential"

  types:
    working_turns: 3  # Keep last N turns as working
    short_term_retention_days: 30
    auto_promote_to_long_term: false

  pinning:
    allow_user_pin: true
    allow_llm_suggest: true
    max_pinned: 50
    require_approval_for_llm_suggest: true  # LLM suggestions need user approval
```

---

## 3. Error Recovery

### Retry Strategy

| Component | Max Retries | Base Delay | Exponential Base |
|-----------|-------------|------------|------------------|
| **LLM API** | 3 | 1000ms | 2 |
| **Embedding API** | 3 | 500ms | 2 |
| **Tool Execution** | 3 | 1000ms | 2 |
| **File Operations** | 2 | 500ms | 1.5 |

### Fallback Chain

```
Primary: Semantic Search (embeddings)
    ↓ (if fails or unavailable)
Fallback 1: Grep Search (keyword/regex)
    ↓ (if fails)
Fallback 2: Recent Turns (last 3)
    ↓ (if fails)
Error: Return with explanation to agent
```

### Circuit Breaker

| Component | Failure Threshold | Window | Recovery Timeout |
|-----------|-------------------|--------|------------------|
| **Embedding API** | 5 failures | 60s | 30s |
| **Tool API** | 5 failures | 60s | 30s |
| **LLM API** | 3 failures | 60s | 60s |

### Error Visibility to Agent

```json
{
  "type": "tool_result",
  "tool": "search_context",
  "success": false,
  "error": {
    "code": "EMBEDDING_API_UNAVAILABLE",
    "message": "Embedding service temporarily unavailable",
    "fallback_used": "grep",
    "retry_count": 2
  },
  "data": { /* grep results as fallback */ }
}
```

### Configuration

```yaml
error_recovery:
  retry:
    max_retries: 3
    base_delay_ms: 1000
    max_delay_ms: 10000
    exponential_base: 2

  circuit_breaker:
    enabled: true
    failure_threshold: 5
    failure_window_seconds: 60
    recovery_timeout_seconds: 30

  fallback_chain:
    search:
      - semantic    # Primary
      - grep        # Fallback 1
      - recent      # Fallback 2

    tool_execution:
      - execute     # Primary
      - retry       # Built into tool execution
      - error       # Return error

  visibility:
    show_errors_to_agent: true
    show_fallbacks_to_agent: true
    include_stack_trace: false  # Production mode
```

---

## 4. Observability - Execution Traces

### Trace Structure

```
Session Execution (Root Span)
├── Initialization
├── LLM Call Loop
│   ├── LLM Request Span
│   │   └── Prompt preparation
│   ├── LLM Response Span
│   │   └── Response parsing
│   └── Tool Call Decision
│       ├── Tool A Execution
│       │   ├── Tool A Request Span
│       │   └── Tool A Result Span
│       └── Tool B Execution
│           ├── Tool B Request Span
│           └── Tool B Result Span
├── Compaction (conditional)
│   ├── Archive Span
│   ├── Summary Generation Span
│   └── Metadata Update Span
└── Finalization
```

### Event Types

| Event | Type | Data |
|-------|------|------|
| `session.start` | root | session_id, user_id, model |
| `llm.request` | span | model, messages, tools, max_tokens |
| `llm.response` | span | content, usage, finish_reason |
| `tool.call` | span | tool_name, arguments |
| `tool.result` | span | success, output, error, duration_ms |
| `compaction.start` | span | reason, turn_count |
| `compaction.complete` | span | turns_archived, tokens_saved, summary_tokens |
| `memory.pinned` | event | message_id, pinned_by, reason |
| `error` | span | error_type, message, stack_trace |
| `session.end` | root | final_state, total_tokens, duration_ms |

### SSE Events Format

```json
{
  "type": "execution_trace",
  "event": "llm_request",
  "timestamp": "2026-03-15T10:30:00Z",
  "trace_id": "trace_abc123",
  "span_id": "span_001",
  "parent_span_id": "span_000",
  "data": {
    "model": "llama3",
    "message_count": 5,
    "tools_count": 3
  }
}
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/sessions/{id}/trace` | GET | SSE stream of traces |
| `/v1/sessions/{id}/trace` | GET | Get full trace (non-streaming) |
| `/v1/sessions/{id}/trace/{trace_id}` | GET | Get specific trace |

### Configuration

```yaml
observability:
  enabled: true
  retention_days: 30

  # What's traced
  trace_llm: true
  trace_tools: true
  trace_compaction: true
  trace_errors: true

  # Detail levels
  include_prompts: true
  include_results: true
  max_span_data_size: 10000  # Truncate after N chars

  # SSE
  sse_enabled: true
  sse_heartbeat_seconds: 30
```

---

## 5. Embeddings Service

### OpenAI-Compatible API Format

Request:
```json
POST {endpoint}/embeddings
{
  "model": "nomic-embed-text",
  "input": "Text to embed"
}
```

Response:
```json
{
  "data": [{
    "embedding": [0.1, -0.2, 0.3, ...],
    "index": 0
  }],
  "model": "nomic-embed-text"
}
```

### Supported Providers

| Provider | Endpoint Example | Model Examples |
|----------|-----------------|----------------|
| Ollama | `http://localhost:11434/v1` | `nomic-embed-text`, `mxbai-embed-large` |
| LM Studio | `http://localhost:1234/v1` | `nomic-embed-text`, `text-embedding-3-small` |
| OpenAI | `https://api.openai.com/v1` | `text-embedding-3-small`, `text-embedding-ada-002` |
| Azure OpenAI | `https://{resource}.openai.azure.com/v1` | `text-embedding-3-small` |
| LocalAI | `http://localhost:8080/v1` | `(local-embedding-model)` |

---

## 6. API / Interface Contracts

### New Tool Definitions

```python
# Tool: search_context
search_context(query: str, limit: int = 5) -> str:
    """
    Search through session context using semantic similarity.
    Falls back to grep if semantic search fails.
    """

# Tool: get_context_summary
get_context_summary() -> str:
    """
    Returns the current session summary markdown.
    """

# Tool: get_recent_turns
get_recent_turns(n: int = 3) -> str:
    """
    Returns the last n active turns from the session.
    """

# Tool: pin_memory
pin_memory(message_id: int, reason: str = None) -> bool:
    """
    Pin a memory so it won't be compacted.
    """

# Tool: unpin_memory
unpin_memory(message_id: int) -> bool:
    """
    Unpin a memory.
    """

# Tool: suggest_pin
suggest_pin(message_id: int, reason: str) -> str:
    """
    Suggest pinning a memory. Returns status (pending/approved).
    """

# Tool: get_execution_trace
get_execution_trace(trace_id: str = None) -> str:
    """
    Get execution trace for debugging.
    """

# Tool: force_compact
force_compact() -> str:
    """
    Manually trigger compaction.
    """
```

---

## 7. Implementation Phases

### Phase 1 — Core Infrastructure

This phase sets up the foundational infrastructure.

**Task 1.1: Project Setup + Dependencies**
- Create pyproject.toml with all dependencies
- Install dependencies (requires uv or pip)
- Create project structure with `__init__.py` files

**Task 1.2: Logging Setup**
- Create `tinycua_backend/logging.py` with structlog
- Create tests in `tinycua_backend/tests/unit/test_logging.py`

**Task 1.3: Database Setup (SQLite)**
- Create SQLAlchemy base (`tinycua_backend/db/base.py`)
- Create session factory (`tinycua_backend/db/session.py`)
- Create Alembic migrations
- Create tests in `tinycua_backend/tests/unit/test_database.py`

**Task 1.4: HTTP Client Wrapper**
- Create httpx wrapper (`tinycua_backend/http/client.py`)
- Create custom exceptions
- Create tests in `tinycua_backend/tests/unit/test_http_client.py`

**Task 1.5: Configuration Management**
- Create config models (`tinycua_backend/config/models.py`)
- Create settings class with Pydantic
- Create YAML config files in `tinycua_backend/config/`
- Create tests in `tinycua_backend/tests/unit/test_config.py`

**Task 1.6: Provider Abstraction**
- Create provider base class and implementations
- Create factory for provider selection
- Create tests in `tinycua_backend/tests/unit/test_providers.py`

---

### Phase 2 — Core Context & Embeddings

**Task 2.1: Context Storage**
- Implement ContextStorage for file read/write
- Create summary.md and full_context.md handling

**Task 2.2: EmbeddingService**
- Implement embedding generation using python-ai-sdk
- Implement semantic search with cosine similarity

**Task 2.3: Summary Generation**
- Implement LLM-based summary creation
- Use OpenCode-inspired template

**Task 2.4: Compaction Logic**
- Implement token threshold detection
- Implement archive + summarize flow
- Support recursive compaction

---

### Phase 3 — Token Estimation

- [ ] tiktoken integration
- [ ] Auto-encoding detection
- [ ] Real-time token counting
- [ ] Smart compaction triggers
- [ ] TokenUsage tracking

---

### Phase 4 — Memory Depth

- [ ] MemoryMetadata model
- [ ] Importance scoring (heuristic + LLM)
- [ ] Memory type transitions
- [ ] Pinning API
- [ ] Pin limits

---

### Phase 5 — Error Recovery

- [ ] Retry decorator with backoff
- [ ] Fallback chains
- [ ] Circuit breaker
- [ ] Error visibility

---

### Phase 6 — Observability

- [ ] ExecutionTracer service
- [ ] Trace event logging
- [ ] SSE endpoints
- [ ] Trace retrieval API

---

### Phase 7 — Agent Loop (Custom)

- [ ] Design agent state
- [ ] Main loop: LLM → tools → LLM cycle
- [ ] Integration with token counting, compaction, tools, memory
- [ ] SSE streaming
- [ ] SSE endpoints
- [ ] Trace retrieval API

---

## Technical Decisions

### Library Stack

1. **httpx for HTTP**
   - **Reason**: Async + sync support, modern, well-maintained

2. **python-ai-sdk for embeddings + tools**
   - **Reason**: Zero-config embeddings with batching, cosine_similarity, tool decorator
   - **Usage**: Partial - we use embeddings + tool definitions, but build custom executor

3. **tiktoken for token estimation**
   - **Reason**: Accurate, well-maintained, supports many encodings

4. **SQLAlchemy + Alembic**
   - **Reason**: Standard Python ORM, works well with SQLite

5. **Pydantic for serialization**
   - **Reason**: Most popular, good integration with FastAPI

6. **tenacity for retry**
   - **Reason**: Flexible retry logic with exponential backoff

7. **structlog for logging**
   - **Reason**: Structured logging, better for debugging

### Design Decisions

8. **Decision**: Custom agent loop (like OpenCode)
   - **Reason**: Full control over orchestration, matches our spec exactly
   - **Alternative**: LangGraph - rejected for complexity

9. **Decision**: OpenCode-inspired compaction template
   - **Reason**: Proven template with Goal, Instructions, Discoveries, Accomplished, Relevant files

10. **Decision**: Hybrid importance scoring
    - **Reason**: Fast heuristic + accurate LLM option

11. **Decision**: Per-component circuit breaker
    - **Reason**: Isolates failures, prevents cascading

12. **Decision**: Errors visible to agent
    - **Reason**: Agent can make informed decisions about fallbacks

13. **Decision**: Hierarchical traces (Prefect-style)
    - **Reason**: Clear parent-child relationships, better debugging

14. **Decision**: Store embeddings in DB as JSON blob
    - **Reason**: SQLite-compatible, no need for external vector DB

15. **Decision**: OpenAI-compatible embedding API
    - **Reason**: Works with Ollama, LM Studio, OpenAI, Azure

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Token estimation inaccurate | Medium | Medium | Add buffer, use tiktoken |
| Circuit breaker false positive | Low | Medium | Tune thresholds |
| Pinning limit reached | Low | Low | Warn user, suggest unpin |
| Trace storage grows large | Medium | Medium | Retention policy, truncation |
| Embedding API unavailable | Medium | Medium | Fallback to grep |
| Summary generation fails | Low | High | Log error, continue |

---

## Open Questions

No open questions - all design decisions are resolved.

---

## References

- Spec: `specs/session-context/spec.md`
- Related: `specs/auth-session` (existing session management)
- Related: `specs/openai-responses` (orchestration loop)
- Related: `specs/runner-integration` (tool execution)
- **OpenCode**: https://github.com/anomalyco/opencode (agent loop, compaction template)
- python-ai-sdk: https://github.com/python-ai-sdk/sdk
- tiktoken: https://github.com/openai/tiktoken
- FastAPI: https://fastapi.tiangolo.com/
- Prefect telemetry: https://docs.prefect.io/v3/api-ref/python/prefect-telemetry
- AIRI memory system: https://github.com/moeru-ai/airi
- Agent S3: https://www.simular.ai/articles/agent-s3
- widemem (optional): https://github.com/remete618/widemem-ai
