# Memory System Documentation

The `memory/` package provides multi-tier memory management for agents: short-term conversation context, long-term persistent storage, caching, compression, and pluggable backends.

**Package path:** `tinycua_sdk/memory/`

---

## short_term.py - Short-Term Memory

### Purpose

Manages conversation context within a single session. Thread-safe, with configurable message window and token limits.

### Message Dataclass

```python
@dataclass
class Message:
    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
```

Represents a single message in the conversation history. Includes metadata for extensibility (e.g., tool call IDs, importance scores).

### ShortTermMemory Class

```python
class ShortTermMemory:
    def __init__(
        self,
        session_id: str | None = None,
        message_window: int = 100,
        max_tokens: int = 100000,
    )
```

**Parameters:**
- `session_id`: Identifier for the session (default: `"default"`)
- `message_window`: Maximum number of messages to retain (FIFO eviction)
- `max_tokens`: Maximum estimated tokens in context window

**Thread Safety:**
```python
self._lock = RLock()
```

Uses `threading.RLock` (reentrant lock) so the same thread can acquire the lock multiple times without deadlocking.

### Adding Messages

```python
def add(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
    with self._lock:
        msg = Message(role=role, content=content, metadata=metadata or {})
        self._messages.append(msg)
        
        if len(self._messages) > self._message_window:
            self._messages.pop(0)
```

When the window is exceeded, the oldest message is removed (FIFO). This prevents unbounded memory growth.

### Context Retrieval

```python
def get_context(self, max_tokens: int | None = None) -> list[dict[str, Any]]:
    with self._lock:
        limit = max_tokens or self._max_tokens
        result = []
        total_tokens = 0
        
        for msg in reversed(self._messages):
            tokens = self._estimate_tokens(msg.content)
            if total_tokens + tokens > limit and result:
                break
            result.insert(0, msg.to_dict())
            total_tokens += tokens
        
        return result
```

**Algorithm:**
1. Iterate messages in reverse (newest first)
2. Estimate tokens for each message
3. Accumulate until limit reached
4. If limit exceeded and we have at least one message, stop
5. Insert at position 0 to maintain chronological order

**Why insert at 0?** Because we're iterating backwards, each new (older) message needs to be prepended to maintain order.

**Edge case:** `if total_tokens + tokens > limit and result` - the `and result` ensures we keep at least one message even if it exceeds the limit. Prevents empty context.

### Token Estimation

```python
def _estimate_tokens(self, text: str) -> int:
    return max(1, len(text) // 4)
```

Conservative estimate: 4 characters per token. This is a rough heuristic (actual tokenization depends on the model's tokenizer) but is fast and doesn't require model-specific dependencies.

**Why conservative?** Underestimating tokens could exceed the model's context window. Overestimating is safer - it just means we might drop messages earlier than necessary.

---

## long_term.py - Long-Term Memory

### Purpose

Manages persistent long-term memory using file-based storage. Stores facts, preferences, and agent state across sessions.

### Storage Layout

Default storage path: `~/.tinycua/`

Standard files:
- `MEMORY.md`: Persistent facts and agent memory
- `USER.md`: User preferences and profile

### Constructor

```python
class LongTermMemory:
    def __init__(self, storage_path: str | None = None)
```

**Thread Safety:**
```python
self._lock = RLock()
```

All read/write operations are protected by a reentrant lock.

### File Operations

```python
def _file_path(self, name: str) -> Path:
    return self._storage_path / name

def read(self, name: str = "MEMORY.md") -> str:
    with self._lock:
        file_path = self._file_path(name)
        if not file_path.exists():
            return ""
        return file_path.read_text(encoding="utf-8")

def write(self, content: str, name: str = "MEMORY.md") -> dict[str, Any]:
    with self._lock:
        file_path = self._file_path(name)
        file_path.write_text(content, encoding="utf-8")
        return {"success": True, "name": name, "path": str(file_path)}
```

**Why file-based?** Simple, portable, human-readable. No database setup required. Users can directly edit `MEMORY.md` and `USER.md`.

### Key-Value Operations

```python
def update(self, key: str, value: str, name: str = "MEMORY.md") -> dict[str, Any]:
    content = self.read(name)
    lines = content.split("\n") if content else []
    found = False
    new_lines = []
    
    for line in lines:
        if line.startswith(f"{key}:"):
            new_lines.append(f"{key}: {value}")
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        new_lines.append(f"{key}: {value}")
    
    return self.write("\n".join(new_lines), name)

def delete(self, key: str, name: str = "MEMORY.md") -> dict[str, Any]:
    content = self.read(name)
    lines = content.split("\n") if content else []
    new_lines = [line for line in lines if not line.startswith(f"{key}:")]
    return self.write("\n".join(new_lines), name)
```

Simple line-based key-value format (`key: value`). Updates replace existing lines; appends if not found.

**Format limitations:** Keys cannot contain colons. Values are everything after the first colon.

### Integration with Modeling

```python
def get_user_model(self) -> "UserModel":
    from tinycua_sdk.modeling.user import UserModel
    return UserModel(self)

def get_personality(self) -> "Personality":
    from tinycua_sdk.modeling.personality import Personality
    return Personality(self)
```

Lazy imports to avoid circular dependencies. `LongTermMemory` acts as the persistence layer for `UserModel` and `Personality`.

---

## cache.py - Prompt Cache

### Purpose

Implements OpenAI-compatible prompt caching with TTL and size limits. Reduces redundant LLM calls by caching prompt-result pairs.

### CacheEntry Dataclass

```python
@dataclass
class CacheEntry:
    key: str
    value: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl: float | None = None
    hit_count: int = 0
```

Tracks access patterns for eviction decisions:
- `created_at`: For TTL expiration
- `last_accessed`: For LRU eviction
- `hit_count`: For LFU eviction

### PromptCache Class

```python
class PromptCache:
    def __init__(
        self,
        max_size: int = 100,
        default_ttl: float | None = 3600,
        refresh_strategy: str = "lru",
    )
```

**Parameters:**
- `max_size`: Maximum cached entries
- `default_ttl`: Time-to-live in seconds (`None` = no expiration)
- `refresh_strategy`: Eviction strategy - `"lru"`, `"lfu"`, or `"ttl"`

### get() - Retrieval

```python
def get(self, prompt: str) -> str | None:
    with self._lock:
        key = self._make_key(prompt)
        entry = self._cache.get(key)
        
        if entry is None:
            return None
        
        if self._is_expired(entry):
            del self._cache[key]
            return None
        
        entry.hit_count += 1
        entry.last_accessed = time.time()
        return entry.value
```

**Key generation:**
```python
def _make_key(self, prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
```

Uses SHA256 of the full prompt text. This is deterministic and collision-resistant.

**Why SHA256?** Prompts can be very long (thousands of characters). SHA256 produces a fixed-size key. The chance of collision is cryptographically negligible.

### set() - Storage

```python
def set(self, prompt: str, result: str, ttl: float | None = None) -> dict[str, Any]:
    with self._lock:
        if len(self._cache) >= self._max_size:
            self._evict_oldest()
        
        key = self._make_key(prompt)
        entry = CacheEntry(key=key, value=result, ttl=ttl or self._default_ttl)
        self._cache[key] = entry
        return {"success": True, "key": key}
```

Evicts before inserting if at capacity. This ensures we never exceed `max_size`.

### Eviction Strategies

```python
def _evict_oldest(self) -> None:
    if not self._cache:
        return
    
    if self._refresh_strategy == "lru":
        oldest = min(self._cache.values(), key=lambda e: e.last_accessed)
        del self._cache[oldest.key]
    elif self._refresh_strategy == "lfu":
        least_used = min(self._cache.values(), key=lambda e: e.hit_count)
        del self._cache[least_used.key]
    elif self._refresh_strategy == "ttl":
        expired = [e for e in self._cache.values() if self._is_expired(e)]
        if expired:
            del self._cache[expired[0].key]
        else:
            oldest = min(self._cache.values(), key=lambda e: e.created_at)
            del self._cache[oldest.key]
```

| Strategy | Eviction Criteria | Best For |
|----------|-------------------|----------|
| LRU | Least recently accessed | Temporal locality (recent prompts likely to repeat) |
| LFU | Least frequently accessed | Popular prompts that should stay cached |
| TTL | Expired first, then oldest | Time-sensitive data |

---

## compression.py - Context Compression

### Purpose

Compresses conversation context to fit within token limits using summarization, truncation, or sliding window strategies.

### ContextCompressor Class

```python
class ContextCompressor:
    def __init__(
        self,
        token_threshold: int = 50000,
        compression_ratio: float = 0.5,
        summarize_fn: Callable[[list[dict[str, Any]]], str] | None = None,
    )
```

**Parameters:**
- `token_threshold`: Token count that triggers compression
- `compression_ratio`: Target ratio after compression (0.0-1.0)
- `summarize_fn`: Optional custom summarization function

### Compression Strategies

#### Summarize Strategy

```python
def _compress_summarize(self, messages: list[dict[str, Any]], target_tokens: int) -> list[dict[str, Any]]:
    if self._summarize_fn:
        summary = self._summarize_fn(messages)
    else:
        summary = self._generate_summary(messages)
    
    return [{
        "role": "system",
        "content": f"[Previous conversation summary: {summary}]",
        "metadata": {"compressed": True},
    }]
```

Replaces all messages with a single system message containing a summary. Most aggressive compression.

#### Truncate Strategy

```python
def _compress_truncate(self, messages: list[dict[str, Any]], target_tokens: int) -> list[dict[str, Any]]:
    result = []
    total_tokens = 0
    
    for msg in reversed(messages):
        tokens = self._estimate_tokens(msg.get("content", ""))
        if total_tokens + tokens > target_tokens:
            break
        result.insert(0, msg)
        total_tokens += tokens
    
    return result
```

Keeps only the most recent messages that fit within the token limit. Simple but loses older context.

#### Window Strategy

```python
def _compress_window(self, messages: list[dict[str, Any]], target_tokens: int) -> list[dict[str, Any]]:
    if len(messages) <= 2:
        return messages
    
    window_size = len(messages) // 2
    recent = messages[-window_size:]
    return messages[:1] + recent
```

Keeps the first message (usually system prompt) plus the most recent half. Balances between keeping initial instructions and recent context.

### Extractive Summary Generation

```python
def _generate_summary(self, messages: list[dict[str, Any]]) -> str:
    # Build word frequency (excluding stop words)
    word_freq = {}
    for msg in messages:
        content = msg.get("content", "").lower()
        words = content.split()
        for word in words:
            clean_word = "".join(c for c in word if c.isalnum())
            if clean_word and clean_word not in stop_words and len(clean_word) > 2:
                word_freq[clean_word] = word_freq.get(clean_word, 0) + 1
    
    # Get top 10 topics
    top_topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Build summary parts
    summary_parts = [f"{len(messages)} messages"]
    if topic_list:
        summary_parts.append(f"topics: {topic_list}")
    if first_msg:
        summary_parts.append(f"started with: {first_msg}...")
    if last_msg:
        summary_parts.append(f"ended with: {last_msg}...")
    
    return "; ".join(summary_parts)
```

Simple extractive summarization:
1. Count word frequencies (excluding common stop words)
2. Extract top topics
3. Include message count, topics, first/last message snippets

**Why extractive?** Fast, no LLM call required, works offline. Quality is lower than abstractive summarization but sufficient for context compression.

---

## plugin.py - Memory Plugin System

### Purpose

Provides pluggable memory backends with file, in-memory, and SQLite implementations.

### MemoryPlugin (ABC)

```python
class MemoryPlugin(ABC):
    @abstractmethod
    def read(self, key: str) -> str | None: ...
    @abstractmethod
    def write(self, key: str, value: str) -> dict[str, Any]: ...
    @abstractmethod
    def delete(self, key: str) -> dict[str, Any]: ...
    @abstractmethod
    def list_keys(self) -> list[str]: ...
    
    def clear(self) -> dict[str, Any]:
        keys = self.list_keys()
        for key in keys:
            self.delete(key)
        return {"success": True}
```

Default `clear()` iterates and deletes. Subclasses can override with more efficient implementations (e.g., `TRUNCATE TABLE` for SQL).

### FileMemoryPlugin

```python
class FileMemoryPlugin(MemoryPlugin):
    def __init__(self, storage_path: str | None = None)
```

Stores data in `~/.tinycua/plugin_memory.json` as a single JSON object.

**Thread safety:** Uses `threading.RLock` for all read/write operations.

### InMemoryPlugin

```python
class InMemoryPlugin(MemoryPlugin):
    def __init__(self)
```

Simple dict-based storage. Data is lost when process exits. Useful for testing.

### SQLiteMemoryPlugin

```python
class SQLiteMemoryPlugin(MemoryPlugin):
    def __init__(self, db_path: str | None = None)
```

Stores data in SQLite database at `~/.tinycua/memory.db`.

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS memory (
    key TEXT PRIMARY KEY,
    value TEXT
)
```

**Why SQLite?** ACID guarantees, better concurrency than file-based JSON, supports large datasets.

### Factory Function

```python
def get_memory_plugin(plugin_type: str = "memory", **kwargs: Any) -> MemoryPlugin:
    plugins = {
        "file": FileMemoryPlugin,
        "memory": InMemoryPlugin,
        "sqlite": SQLiteMemoryPlugin,
    }
    plugin_class = plugins.get(plugin_type, InMemoryPlugin)
    return plugin_class(**kwargs)
```

---

## session.py - MemorySession Facade

### Purpose

`MemorySession` provides a high-level, session-scoped API for storing and retrieving factual memories, knowledge, and observations tied to a specific conversation session. It is a **facade** over the existing `LocalStorage` / `SessionStore` layer, which already supports session-scoped memory via the `memory` table's `session_id` column.

**Why it exists:** The SQLite schema (`storage/sqlite.py`) already has a `memory` table with `session_id`, `memory_type`, `content`, and `metadata` columns. However, there was no clean object-oriented API to use it. `MemorySession` fills this gap without duplicating storage logic.

**Relationship to `ShortTermMemory`:**
- `ShortTermMemory` = conversation message history (user/assistant/system roles, ephemeral)
- `MemorySession` = factual memories, preferences, observations (typed, persistent per session)

### MemorySession Class

```python
class MemorySession:
    def __init__(
        self,
        session_id: str,
        storage: LocalStorage | None = None,
    )
```

**Parameters:**
- `session_id`: The session identifier all operations are scoped to
- `storage`: Optional `LocalStorage` instance (defaults to a new one)

**Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `add(content, memory_type, metadata=None)` | `str` | Save a new memory, auto-generate UUID, return memory_id |
| `get(memory_id)` | `dict \| None` | Load a single memory by ID |
| `list(memory_type=None)` | `list[dict]` | List all memories for this session, optionally filtered by type |
| `search(query)` | `list[dict]` | Case-insensitive substring search across memory content |
| `delete(memory_id)` | `bool` | Delete a memory by ID |
| `clear()` | `bool` | Delete all memories for this session |

### Implementation Details

```python
def add(self, content: str, memory_type: str, metadata: dict | None = None) -> str:
    memory_id = str(uuid.uuid4())
    self._storage.save_memory(
        memory_id=memory_id,
        memory_type=memory_type,
        content=content,
        session_id=self.session_id,
        metadata=metadata,
    )
    return memory_id
```

Auto-generates a UUID v4, delegates to `LocalStorage.save_memory()` with `session_id` bound at initialization.

```python
def list(self, memory_type: str | None = None) -> list[dict]:
    return self._storage.list_memory(
        session_id=self.session_id,
        memory_type=memory_type,
    )
```

Delegates to `LocalStorage.list_memory()` with the bound `session_id`.

```python
def search(self, query: str) -> list[dict]:
    all_memories = self.list()
    query_lower = query.lower()
    return [
        m for m in all_memories
        if query_lower in m.get("content", "").lower()
    ]
```

Performs case-insensitive substring matching in Python. Future enhancement: push search to SQL `LIKE` for large datasets.

```python
def clear(self) -> bool:
    memories = self.list()
    for memory in memories:
        self._storage.delete_memory(memory["id"])
    return True
```

Iterates and deletes one-by-one (N+1 queries). Future enhancement: single bulk `DELETE FROM memory WHERE session_id = ?`.

### Usage Example

```python
from tinycua_sdk.memory import MemorySession

session = MemorySession(session_id="chat-123")

# Add memories
fact_id = session.add("Python 3.12 released in 2023", memory_type="fact")
pref_id = session.add("User prefers dark mode", memory_type="preference")

# Search
results = session.search("python")
# → [{"id": "...", "content": "Python 3.12 released in 2023", "memory_type": "fact", ...}]

# List by type
prefs = session.list(memory_type="preference")

# Delete
session.delete(fact_id)

# Clear all
session.clear()
```

### Design Decisions

1. **Facade over wrapper:** `MemorySession` delegates to `LocalStorage` rather than reimplementing SQL. This keeps the storage schema in one place.
2. **Session binding at init:** `session_id` is set once at construction, so every operation is automatically scoped. No need to pass `session_id` on every call.
3. **UUID generation in Python:** The facade generates IDs, not the database. This allows the ID to be returned immediately without a round-trip.
4. **Case-insensitive search:** Implemented in Python for simplicity. The dataset per session is expected to be small enough for O(n) scanning.

---

## Inter-Module Data Flow

### Short-Term Memory Flow
```
Agent conversation
  → ShortTermMemory.add(role, content)
    → Append Message to _messages
    → FIFO eviction if > message_window
  → ShortTermMemory.get_context(max_tokens)
    → Reverse iterate
    → Token estimation
    → Return fitting messages
```

### Long-Term Memory Flow
```
Agent needs persistent fact
  → LongTermMemory.update(key, value)
    → Read file
    → Update line
    → Write file
  → LongTermMemory.read(name)
    → Read file
    → Return content
```

### Cache Flow
```
Agent.run(user_input)
  → PromptCache.get(prompt)
    → SHA256(prompt) → key
    → Check cache
    → If expired: delete, return None
    → If valid: update hit_count, last_accessed, return value
  → (if cache miss) LLM call
  → PromptCache.set(prompt, result)
    → Evict if at capacity
    → Store CacheEntry
```

### MemorySession Flow
```
Agent.run(user_input)
  → (agent stores extracted facts)
    → MemorySession.add(content, memory_type="fact")
      → uuid.uuid4() → memory_id
      → LocalStorage.save_memory(memory_id, ..., session_id="bound-session")
        → SQLite INSERT INTO memory
  → (later turn needs context)
    → MemorySession.search("relevant topic")
      → LocalStorage.list_memory(session_id="bound-session")
        → SQLite SELECT * FROM memory WHERE session_id = ?
      → Python substring filter
    → Inject relevant memories into system prompt
```

### Compression Flow
```
Runner.build_messages()
  → ContextCompressor.should_compress(messages)
    → Estimate total tokens
    → If > threshold: compress
  → ContextCompressor.compress(messages, strategy="summarize")
    → _compress_summarize() or _compress_truncate() or _compress_window()
    → Return compressed message list
```
