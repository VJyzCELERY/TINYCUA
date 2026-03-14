# Design Document: Session Context Management with Grep Search

**Spec**: `specs/session-context/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-14

---

## Overview

This design adds session context management with grep-based search and automatic compaction to the tinycua-backend. The system extends existing session storage with file-based archives and provides tools for the agent to search past context. When context grows large, the system automatically compacts by archiving older turns and generating a summary.

**Key Architectural Decisions**:
- Hybrid storage: DB for active messages, file storage for archived context
- Grep-first search (semantic search deferred to Phase 2)
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
│                    │  Studio)       │    └──────────────────┘   │
│                    └────────────────┘                             │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Tools available to agent                                     │ │
│  │ - get_context (existing)                                      │ │
│  │ - search_context_grep                                         │ │
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
        └── full_context.md     # Archived turns (grep searchable)
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
| `session_messages` table | Modified | Add `turn_index`, `is_archived` columns |
| `sessions` table | Modified | Add `has_summary`, `summary_updated_at` columns |
| Model registry | Modified | Add `max_tokens` per model |

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

### Config File Format

`config/models.yaml`:
```yaml
models:
  tinycua-gguf-7b:
    provider: ollama
    endpoint: http://localhost:11434
    max_tokens: 32768  # 32K context
    default_temperature: 0.7
  
  llama3:
    provider: openai
    endpoint: https://api.openai.com/v1
    max_tokens: 8192
    default_temperature: 0.7

default_max_tokens: 16384  # Used when model not found
```

---

## API / Interface Contracts

### New Tool Definitions

When session is active, these tools are injected into `tools[]`:

```python
# Tool: search_context_grep
search_context_grep(pattern: str) -> str:
    """
    Search through archived session context using grep pattern.
    Returns matching turns with context lines.
    """
    # Example return:
    # "Turn 5:
    # ### User
    # What's the weather?
    # ### Assistant
    # It's sunny, 72°F.
    # 
    # Turn 12:
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
      iii. Mark messages as archived in DB
      iv. Keep last 3 turns as active (not archived)
      v. Generate summary via LLM
      vi. Write summary.md
      vii. Update sessions.has_summary, summary_updated_at
   b. Recalculate usage
   c. If usage still > 0.75, repeat (recursive)
5. Prepend summary.md to input
6. Prepend active messages to input
7. Continue with orchestration loop
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

### Phase 1 — MVP

- [ ] Add database columns (`turn_index`, `is_archived`, `has_summary`, `summary_updated_at`)
- [ ] Create Alembic migration
- [ ] Implement `ContextStorage` class for file read/write
- [ ] Implement `grep_search` function
- [ ] Implement `generate_summary` function (calls LLM)
- [ ] Implement `compact_session` function
- [ ] Create new tools: `search_context_grep`, `get_context_summary`, `get_recent_turns`
- [ ] Modify orchestration loop to inject tools when session is active
- [ ] Modify orchestration loop to check compaction threshold before LLM call
- [ ] Modify orchestration loop to prepend summary to input
- [ ] Add model config file (`config/models.yaml`)
- [ ] Unit tests for storage, grep, compaction logic
- [ ] Integration tests for full flow

### Phase 2 — Enhancements (Post-MVP)

- [ ] Semantic/embedding-based search
- [ ] Configurable compaction threshold
- [ ] Configurable active turns to keep
- [ ] Summary caching to avoid regeneration

---

## Technical Decisions

1. **Decision**: Grep-first search instead of semantic embeddings
   - **Reason**: Embeddings require additional infrastructure (vector DB or numpy storage) and add latency
   - **Alternatives Considered**: Semantic search - rejected for MVP complexity

2. **Decision**: Store archived context as markdown files
   - **Reason**: Simple grep tooling, human-readable, easy to version/audit
   - **Alternatives Considered**: JSON files - rejected, markdown is more human-friendly

3. **Decision**: Keep last 3 turns active after compaction
   - **Reason**: Provides recent context without needing to grep for immediate history
   - **Alternatives Considered**: Keep all - rejected, defeats purpose of compaction

4. **Decision**: Recursive compaction with layered summaries
   - **Reason**: Prevents infinite compaction loop and preserves hierarchical context access
   - **Alternatives Considered**: Single compaction - rejected, doesn't handle very long sessions

5. **Decision**: Use config file for model max_tokens
   - **Reason**: Model-specific configuration belongs in config, not hardcoded
   - **Alternatives Considered**: Environment variable - rejected, doesn't support per-model config

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Summary generation fails | Low | High | Log error, continue without summary |
| File storage fills disk | Low | High | Add disk usage monitoring |
| Compaction loop (recursive) | Low | Medium | Add max recursion depth (e.g., 5) |
| Grep search returns too much | Low | Medium | Add max results limit |
| Token estimation inaccurate | Medium | Medium | Add buffer margin (e.g., trigger at 70%) |

---

## Open Questions

No open questions - all design decisions are resolved.

---

## References

- Spec: `specs/session-context/spec.md`
- Related: `specs/auth-session` (existing session management)
- Related: `specs/openai-responses` (orchestration loop)
- Related: `specs/runner-integration` (tool execution)
