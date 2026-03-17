# Design Document: Unified Database Storage

**Spec**: `specs/unified-storage/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-17

---

## Overview

This design outlines a unified storage layer for memory and session management that works with both SQLite (local SDK) and PostgreSQL (production backend).

---

## Library Stack

| Component | Library | Notes |
|-----------|---------|-------|
| ORM | SQLAlchemy 2.0 | Async support |
| Database | sqlite3 (built-in) | Local default |
| Database | psycopg2/asyncpg | PostgreSQL |
| Embeddings | python-ai-sdk | OpenAI-compatible |
| Tokenizer | tiktoken | Token counting |

---

## Architecture

```
                    ┌─────────────────────────┐
                    │   Unified Storage       │
                    │   (SessionStore)       │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
     │   SQLite     │  │ PostgreSQL   │  │   Memory     │
     │  (local)     │  │ (production)│  │   Backend    │
     └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Data Models

### Session Model

```python
class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID, primary_key=True)
    name = Column(String(255))
    user_id = Column(String(255), nullable=True)  # For multi-tenancy
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    has_summary = Column(Boolean, default=False)
    summary_updated_at = Column(DateTime, nullable=True)
    summary_md = Column(Text, nullable=True)  # Compacted summary
    full_context_md = Column(Text, nullable=True)  # Full session as markdown
```

### Message Model

```python
class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID, primary_key=True)
    session_id = Column(UUID, ForeignKey("sessions.id"))
    role = Column(String(50))  # user/assistant/tool
    content = Column(Text)
    reasoning = Column(Text, nullable=True)  # Agent reasoning/thinking
    turn_index = Column(Integer)
    is_archived = Column(Boolean, default=False)
    embedding = Column(JSON, nullable=True)  # [0.1, 0.2, ...]
    importance = Column(Integer, default=5)  # 1-10
    memory_type = Column(String(50), default="working")  # working/short_term/long_term/pinned
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("Session", backref="messages")
```

#### Reasoning Field (Flexible for Different Models)

Different models use different patterns for thinking/reasoning:

| Model | Thinking Pattern | How to Extract |
|-------|-----------------|----------------|
| OpenAI o1/o3 | `reasoning` field in response | Direct extraction |
| Anthropic | `<thinking>` tags | Regex extraction |
| Qwen | `</reasoning>` tags | Regex extraction |
| Custom | Configurable pattern | User-defined regex |

**Extraction Configuration**:

```python
# Configurable reasoning extraction
reasoning_config = {
    "pattern": r"</?thinking>",  # Default pattern
    "field_name": "reasoning",  # or "thinking", "reflection", etc.
    "strip_tags": True,  # Remove thinking tags from content
}

# Store extracted reasoning
message.reasoning = extracted_reasoning  # Stored separately
message.content = clean_content  # Without thinking tags
```

---

## Unified Storage API

### SessionStore Class

```python
class SessionStore:
    def __init__(self, database_url: str):
        """Initialize with database URL.
        
        Args:
            database_url: SQLite or PostgreSQL URL
        """
        self.engine = create_engine(database_url)
        self.session_factory = sessionmaker(bind=self.engine)
    
    # Session operations
    def create_session(self, name: str, user_id: str = None) -> Session
    def get_session(self, session_id: UUID) -> Session
    def list_sessions(self, user_id: str = None) -> list[Session]
    def update_session(self, session_id: UUID, **kwargs) -> Session
    def delete_session(self, session_id: UUID) -> bool
    
    # Message operations
    def add_message(self, session_id: UUID, role: str, content: str) -> Message
    def get_messages(self, session_id: UUID, limit: int = None) -> list[Message]
    def archive_message(self, message_id: UUID) -> Message
    
    # Context retrieval
    def search_semantic(self, session_id: UUID, query: str, limit: int = 5) -> list[dict]
    def search_grep(self, session_id: UUID, query: str, limit: int = 5) -> list[dict]
    def get_summary(self, session_id: UUID) -> str | None
    def get_recent_turns(self, session_id: UUID, count: int = 3) -> list[Message]
    
    # Full context
    def update_full_context(self, session_id: UUID) -> None
    def generate_summary(self, session_id: UUID) -> str
```

---

## Embedding Storage by Database

### SQLite

```python
# Embedding stored as JSON
embedding = Column(JSON)  # [0.1, 0.2, ...]

# Semantic search in Python
def search_semantic(self, session_id: UUID, query: str):
    messages = self.get_messages(session_id)
    query_embedding = self.get_embedding(query)
    
    results = []
    for msg in messages:
        if msg.embedding:
            similarity = cosine_similarity(query_embedding, msg.embedding)
            results.append({"message": msg, "score": similarity})
    
    return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]
```

### PostgreSQL

```python
# Embedding as vector (pgvector)
try:
    from pgvector.sqlalchemy import Vector
    embedding = Column(Vector(1536))  # OpenAI ada-002 dimension
except ImportError:
    embedding = Column(JSON)  # Fallback

# Semantic search via SQL
def search_semantic(self, session_id: UUID, query: str):
    query_embedding = self.get_embedding(query)
    # Use <-> (cosine distance) operator
    stmt = text("""
        SELECT *, embedding <=> :query_embedding as similarity
        FROM messages
        WHERE session_id = :session_id AND embedding IS NOT NULL
        ORDER BY similarity
        LIMIT :limit
    """)
```

---

## Context Retrieval Tools

### search_context_semantic

```python
@tool()
def search_context_semantic(query: str) -> dict:
    """Search session context using semantic similarity.
    
    Args:
        query: Search query text
        
    Returns:
        {"results": [{"content": "...", "role": "...", "score": 0.95}]}
    """
    session_id = get_current_session_id()
    results = store.search_semantic(session_id, query)
    return {"results": results}
```

### search_context_grep

```python
@tool()
def search_context_grep(query: str) -> dict:
    """Search session context using text matching.
    
    Args:
        query: Search query text
        
    Returns:
        {"results": [{"content": "...", "role": "..."}]}
    """
    session_id = get_current_session_id()
    results = store.search_grep(session_id, query)
    return {"results": results}
```

### get_context_summary

```python
@tool()
def get_context_summary() -> dict:
    """Get the compacted summary of the session.
    
    Returns:
        {"summary": "..."}
    """
    session_id = get_current_session_id()
    summary = store.get_summary(session_id)
    return {"summary": summary}
```

### get_recent_turns

```python
@tool()
def get_recent_turns(count: int = 3) -> dict:
    """Get the most recent turns from the session.
    
    Args:
        count: Number of recent turns (default 3)
        
    Returns:
        {"turns": [{"role": "...", "content": "..."}]}
    """
    session_id = get_current_session_id()
    turns = store.get_recent_turns(session_id, count)
    return {"turns": [{"role": t.role, "content": t.content} for t in turns]}
```

---

## Configuration

### Environment Variables

```bash
# Database URL
DATABASE_URL=sqlite:///./tinycua.db

# Or PostgreSQL
DATABASE_URL=postgresql://user:pass@localhost/tinycua

# Embedding provider (for semantic search)
EMBEDDING_PROVIDER=openai  # or ollama, lmstudio
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_URL=http://localhost:11434/v1
EMBEDDING_API_KEY=optional
```

### Initialization

```python
from tinycua_storage import SessionStore

# Local SQLite
store = SessionStore("sqlite:///./tinycua.db")

# Production PostgreSQL
store = SessionStore("postgresql://user:pass@localhost/tinycua")

# Create tables
store.create_tables()
```

---

## Full Context Markdown Format

```markdown
# Session: Chat with Assistant
Created: 2026-03-17T10:00:00Z

---

## Turn 1
**User**: Hello, my name is Bob
**Assistant**: Hi Bob! Nice to meet you.

## Turn 2
**User**: What's the weather like?
**Assistant**: The weather today is sunny, 72°F.

## Turn 3
**User**: Remember my favorite color is blue
**Assistant**: I'll remember that your favorite color is blue!
```

---

## Implementation Phases

### Phase 1: Database Layer

- [ ] Create SQLAlchemy models (Session, Message)
- [ ] Implement SessionStore with SQLite support
- [ ] Add PostgreSQL support with JSON fallback

### Phase 2: Context Retrieval

- [ ] Implement search_grep (SQL LIKE/REGEX)
- [ ] Implement search_semantic (Python cosine similarity)
- [ ] Implement get_summary
- [ ] Implement get_recent_turns

### Phase 3: Integration

- [ ] Update SDK memory tools
- [ ] Add context retrieval tools
- [ ] Test with both SQLite and PostgreSQL

---

## Testing Plan

### Unit Tests
- Session create/read/update/delete
- Message add and archive
- Grep search returns correct results
- Semantic search returns correct similarity scores
- Summary generation

### Integration Tests
- Full flow: create session → add messages → search → verify results
- SQLite vs PostgreSQL consistency
- Context retrieval tools work as agent tools

---

## Future: Trace/Events Table (Out of Scope)

For observability, a future Trace table enables step-by-step execution tracking:

```python
class Trace(Base):
    __tablename__ = "traces"

    id = Column(UUID, primary_key=True)
    session_id = Column(UUID, ForeignKey("sessions.id"))
    message_id = Column(UUID, ForeignKey("messages.id"), nullable=True)
    event_type = Column(String(50))  # llm_request, llm_response, tool_call, tool_result
    parent_span_id = Column(UUID, nullable=True)  # For hierarchical tracing
    metadata = Column(JSON)  # {model, tokens, timing, tool_args, tool_result, etc.}
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Use Cases**:
- Step-by-step execution replay
- Debugging agent behavior
- Performance monitoring
- Token usage tracking

**Message-Trace Relationship**:
- Each message can optionally link to a trace
- Trace can have parent trace (hierarchical spans)
- Tool calls linked to their results via trace IDs
