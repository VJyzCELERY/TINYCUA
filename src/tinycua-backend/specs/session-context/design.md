# Design Document: Session Context Management with Semantic Search

**Spec**: `specs/session-context/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-14

---

## Overview

This design adds session context management with embedding-based semantic search and automatic compaction to the tinycua-backend. The system extends existing session storage with file-based archives and provides tools for the agent to semantically search past context. When context grows large, the system automatically compacts by archiving older turns and generating a summary.

**Key Architectural Decisions**:
- Hybrid storage: DB for active messages with embeddings, file storage for archived context
- Semantic search using embeddings (cosine similarity)
- OpenAI-compatible embedding API (Ollama, LM Studio, OpenAI)
- Recursive compaction with layered summaries

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
│                    │ (Ollama/LM     │    │ (DB + Files)     │   │
│                    │  Studio)       │    │ + Embeddings     │   │
│                    └────────────────┘    └──────────────────┘   │
│                              │                      │             │
│                              ▼                      ▼             │
│                    ┌────────────────┐    ┌──────────────────┐   │
│                    │ Embedding      │    │ EmbeddingService │   │
│                    │ Provider       │───▶│ (OpenAI compat)  │   │
│                    └────────────────┘    └──────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Tools available to agent                                     │ │
│  │ - get_context (existing)                                      │ │
│  │ - search_context                                              │ │
│  │ - get_context_summary                                         │ │
│  │ - get_recent_turns                                            │ │
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

### File Formats

**summary.md**:
```markdown
# Session Summary - {session_id}
Generated: {timestamp}

## Overview (Turns 1-{n})
- Narrative summary of the conversation
- Key facts and decisions
- User intents identified

## Recent Context (Turns {n-2} to {n})
### Turn {n-2}
**User**: ...
**Assistant**: ...

### Turn {n-1}
...

### Turn {n}
...
```

**full_context.md**:
```markdown
# Full Context - Session {session_id}

## Turn 1
### User
Hello, what's the weather?

### Assistant
The weather is sunny, 72°F.

## Turn 2
### User
Do I need an umbrella?
### Assistant
No, it's sunny.
...
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_backend/session/` | Modified | Add compaction and storage logic |
| `tinycua_backend/context/` | New | New package for context management |
| `tinycua_backend/embedding/` | New | Embedding service for OpenAI-compatible APIs |
| `session_messages` table | Modified | Add `turn_index`, `is_archived`, `embedding` columns |
| `sessions` table | Modified | Add `has_summary`, `summary_updated_at` columns |
| Model registry | Modified | Add `max_tokens` per model |
| Config | Modified | Add embedding configuration |

---

## Data Model

### Database Schema Changes

**Table: `sessions`** (modify)
| Column | Type | Notes |
|--------|------|-------|
| `has_summary` | bool NOT NULL DEFAULT false | Whether summary exists |
| `summary_updated_at` | datetime | Last time summary was generated |

**Table: `session_messages`** (modify)
| Column | Type | Notes |
|--------|------|-------|
| `turn_index` | int NOT NULL | Order within session (1, 2, 3, ...) |
| `is_archived` | bool NOT NULL DEFAULT false | True if moved to full_context.md |
| `embedding` | blob | Serialized embedding vector (JSON/pickle) |

### Config File Format

**config/models.yaml**:
```yaml
models:
  tinycua-gguf-7b:
    provider: ollama
    endpoint: http://localhost:11434
    max_tokens: 32768
    default_temperature: 0.7
  
  llama3:
    provider: openai
    endpoint: https://api.openai.com/v1
    max_tokens: 8192
    default_temperature: 0.7

default_max_tokens: 16384
```

**config/embedding.yaml**:
```yaml
embedding:
  # Provider: ollama, lmstudio, openai, azure, localai
  provider: ollama
  endpoint: http://localhost:11434/v1
  model: nomic-embed-text
  dimension: 768
  api_key: ""  # Optional, for cloud providers
  timeout: 30
```

---

## Embedding Service

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

### Embedding Flow

```
When a new message is added:
1. Get message content (user or assistant)
2. Call embedding API with content
3. Receive embedding vector
4. Store embedding in DB with message
5. Continue with normal flow

Note: Embeddings are stored per-message, not regenerated during search.
This allows incremental addition of new context.
```

### Semantic Search Flow

```
When agent calls search_context(query):
1. Embed the search query using embedding service
2. Get all non-archived + archived messages from DB
3. Calculate cosine similarity between query and each stored embedding
4. Sort by similarity score (highest first)
5. Return top-k results with turn context
6. If DB search fails/few results, fallback to grep search
```

---

## API / Interface Contracts

### New Tool Definitions

When session is active, these tools are injected into `tools[]`:

```python
# Tool: search_context
search_context(query: str, limit: int = 5) -> str:
    """
    Search through session context using semantic similarity.
    Returns the most relevant turns based on meaning, not just exact matches.
    
    Args:
        query: The search query (e.g., "weather", "temperature")
        limit: Maximum number of results to return (default 5)
    
    Returns:
        Formatted context with relevant turns and similarity scores.
    """
    # Example return:
    # "Found 3 relevant turns:
    # 
    # Turn 5 (similarity: 0.92):
    # ### User
    # What's the weather?
    # ### Assistant
    # It's sunny, 72°F.
    # 
    # Turn 12 (similarity: 0.85):
    # ### User
    # Will it rain later?
    # ### Assistant
    # No rain expected..."
```

```python
# Tool: get_context_summary
get_context_summary() -> str:
    """
    Returns the current session summary markdown.
    """
```

```python
# Tool: get_recent_turns
get_recent_turns(n: int = 3) -> str:
    """
    Returns the last n active turns from the session.
    Default n=3.
    """
```

### Compaction Flow

```
Before each LLM call:
1. Get model max_tokens from config (or default)
2. Estimate current context size (summary + active messages)
3. Calculate: usage = estimated_tokens / max_tokens
4. If usage > 0.75:
   a. Run compaction:
      i. Get all non-archived messages ordered by turn_index
      ii. Write to full_context.md (append mode)
      iii. Mark messages as archived in DB (embeddings preserved!)
      iv. Keep last 3 turns as active (not archived)
      v. Generate summary via LLM
      vi. Write summary.md
      vii. Update sessions.has_summary, summary_updated_at
   b. Recalculate usage
   c. If usage still > 0.75, repeat (recursive)
5. Prepend summary.md to input
6. Prepend active messages to input
7. Continue with orchestration loop

Note: Embeddings are NOT deleted during compaction - they remain in DB
for semantic search even after messages are archived to files.
```

### Summary Generation Prompt

```markdown
Given the following conversation turns, create a summary that includes:
1. A narrative overview (2-3 sentences) of what the user has asked and accomplished
2. Bullet points of key facts, decisions, and user intents
3. Recent context (last 2-3 turns in detail, include actual messages)

Format the output as markdown suitable for frontloading to an AI assistant.
Use this structure:

# Session Summary - {session_id}
Generated: {timestamp}

## Overview (Turns 1-{n})
[Narrative summary]

## Key Points
- [Point 1]
- [Point 2]
- ...

## Recent Context
### Turn {n-2}
**User**: ...
**Assistant**: ...

### Turn {n-1}
...

Conversation:
{all_turns_markdown}
```

---

## Implementation Phases

### Phase 1 — MVP (All Features)

- [ ] Add database columns (`turn_index`, `is_archived`, `embedding`, `has_summary`, `summary_updated_at`)
- [ ] Create Alembic migration
- [ ] Implement `EmbeddingService` class for OpenAI-compatible embedding APIs
- [ ] Implement `ContextStorage` class for file read/write
- [ ] Implement `semantic_search` function using cosine similarity
- [ ] Implement `generate_summary` function (calls LLM)
- [ ] Implement `compact_session` function
- [ ] Create new tools: `search_context`, `get_context_summary`, `get_recent_turns`
- [ ] Modify orchestration loop to generate embeddings for new messages
- [ ] Modify orchestration loop to inject tools when session is active
- [ ] Modify orchestration loop to check compaction threshold before LLM call
- [ ] Modify orchestration loop to prepend summary to input
- [ ] Add model config file (`config/models.yaml`)
- [ ] Add embedding config file (`config/embedding.yaml`)
- [ ] Unit tests for storage, semantic search, compaction logic
- [ ] Integration tests for full flow

---

## Technical Decisions

1. **Decision**: Semantic search using embeddings from start
   - **Reason**: Embeddings don't require training, just inference. Easy to add with OpenAI-compatible APIs.
   - **Alternatives Considered**: Grep-first - rejected, semantic search provides better UX

2. **Decision**: Store embeddings in DB as blob (JSON/pickle)
   - **Reason**: SQLite-compatible, no need for external vector DB
   - **Alternatives Considered**: pgvector - rejected, requires PostgreSQL extension

3. **Decision**: Keep embeddings after compaction
   - **Reason**: Embeddings enable semantic search even for archived context
   - **Alternatives Considered**: Delete embeddings - rejected, loses search capability

4. **Decision**: OpenAI-compatible embedding API
   - **Reason**: Works with Ollama, LM Studio, OpenAI, Azure - flexible provider selection
   - **Alternatives Considered**: Provider-specific SDKs - rejected, adds complexity

5. **Decision**: Keep last 3 turns active after compaction
   - **Reason**: Provides recent context without needing to search for immediate history
   - **Alternatives Considered**: Keep all - rejected, defeats purpose of compaction

6. **Decision**: Recursive compaction with layered summaries
   - **Reason**: Prevents infinite compaction loop and preserves hierarchical context access
   - **Alternatives Considered**: Single compaction - rejected, doesn't handle very long sessions

7. **Decision**: Use config file for model max_tokens and embedding settings
   - **Reason**: Configuration belongs in config, not hardcoded
   - **Alternatives Considered**: Environment variables - rejected, doesn't support per-model config

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Embedding API unavailable | Medium | Medium | Log error, allow fallback to basic text matching |
| Embedding dimension mismatch | Low | High | Validate dimension on startup |
| Summary generation fails | Low | High | Log error, continue without summary |
| File storage fills disk | Low | High | Add disk usage monitoring |
| Compaction loop (recursive) | Low | Medium | Add max recursion depth (e.g., 5) |
| Token estimation inaccurate | Medium | Medium | Add buffer margin (e.g., trigger at 70%) |
| Semantic search returns nothing | Low | Low | Return empty results gracefully |

---

## Open Questions

No open questions - all design decisions are resolved.

---

## References

- Spec: `specs/session-context/spec.md`
- Related: `specs/auth-session` (existing session management)
- Related: `specs/openai-responses` (orchestration loop)
- Related: `specs/runner-integration` (tool execution)
- AIRI memory system: https://github.com/moeru-ai/airi (inspiration for embedding approach)
