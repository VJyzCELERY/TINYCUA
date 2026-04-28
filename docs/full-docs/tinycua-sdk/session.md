# Session Management Documentation

The `session/` package manages conversation sessions with message history.

**Package path:** `tinycua_sdk/session/`

---

## session.py - Session Class

### Purpose

`Session` provides simple file-based session persistence. It stores conversation history, system prompts, and timestamps as JSON files on disk.

### Constructor

```python
class Session:
    def __init__(
        self,
        session_id: str | None = None,
        storage_path: str | None = None,
        system_prompt: str = "You are a helpful assistant.",
    )
```

**Auto-generation:**
```python
import uuid
self.session_id = session_id or str(uuid.uuid4())
```

If no `session_id` is provided, a UUID v4 is generated automatically.

**Storage path:**
```python
self.storage_path = Path(storage_path or self._default_storage_path())
```

Default: `~/.tinycua/sessions/`

### Message Management

```python
def add_message(self, role: str, content: str, **kwargs: Any) -> None:
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    }
    message.update(kwargs)
    self.messages.append(message)
    self.updated_at = datetime.utcnow()
```

Messages are simple dicts with `role`, `content`, and `timestamp`. Additional kwargs are merged for extensibility (e.g., tool call IDs, metadata).

**Why UTC?** `datetime.utcnow()` ensures consistent timestamps regardless of the machine's local timezone.

### Serialization

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "session_id": self.session_id,
        "system_prompt": self.system_prompt,
        "messages": self.messages,
        "created_at": self.created_at.isoformat(),
        "updated_at": self.updated_at.isoformat(),
    }

@classmethod
def from_dict(cls, data: dict[str, Any]) -> "Session":
    session = cls(
        session_id=data.get("session_id"),
        system_prompt=data.get("system_prompt", "You are a helpful assistant."),
    )
    session.messages = data.get("messages", [])
    session.created_at = datetime.fromisoformat(data.get("created_at", ...))
    session.updated_at = datetime.fromisoformat(data.get("updated_at", ...))
    return session
```

Round-trip serialization via ISO format timestamps. `fromisoformat()` handles the `2024-01-15T10:30:00` format.

### Persistence

```python
def save(self) -> None:
    self.storage_path.mkdir(parents=True, exist_ok=True)
    file_path = self.storage_path / f"{self.session_id}.json"
    with open(file_path, "w") as f:
        json.dump(self.to_dict(), f, indent=2)

def load(self, session_id: str | None = None) -> bool:
    load_id = session_id or self.session_id
    file_path = self.storage_path / f"{load_id}.json"
    
    if not file_path.exists():
        return False
    
    with open(file_path, "r") as f:
        data = json.load(f)
    
    loaded = Session.from_dict(data)
    self.session_id = loaded.session_id
    self.messages = loaded.messages
    self.system_prompt = loaded.system_prompt
    self.created_at = loaded.created_at
    self.updated_at = loaded.updated_at
    return True
```

**File naming:** `{session_id}.json`. This allows direct file lookup without scanning directories.

**Why return bool from load()?** Distinguishes between successful load and missing file. Caller can decide whether to create a new session.

### Session Lifecycle

```python
def delete(self) -> bool:
    file_path = self.storage_path / f"{self.session_id}.json"
    if file_path.exists():
        file_path.unlink()
        return True
    return False

def list_sessions(self) -> list[str]:
    if not self.storage_path.exists():
        return []
    return [p.stem for p in self.storage_path.glob("*.json")]
```

`list_sessions()` uses `Path.glob("*.json")` to find all session files, then extracts the stem (filename without extension) as the session ID.

---

## Session Utilities

The `utils/session.py` module provides utility functions (NOT tools) for session lifecycle management.

```python
def create_session(name: str = "Untitled Session") -> dict
def save_session(session_id: str, messages: list[dict[str, Any]], name: str | None = None) -> dict
def load_session(session_id: str) -> dict
def list_sessions() -> dict
def delete_session(session_id: str) -> dict
```

These are thin wrappers around the `Session` class that return result dicts for API consistency.

**Example:**
```python
def create_session(name: str = "Untitled Session") -> dict:
    session = Session(system_prompt=name)
    session.save()
    return {
        "success": True,
        "session_id": session.session_id,
        "name": name,
    }
```

Note: `system_prompt` is used as the session name here. This is a convention in the utility layer.

---

## Inter-Module Data Flow

### Simple Session Flow
```
Agent conversation
  → Session.add_message(role, content)
    → Append to messages list
    → Update updated_at
  → Session.save()
    → JSON serialize to ~/.tinycua/sessions/{session_id}.json
```

### Session Loading Flow
```
Agent initialized with session_id
  → Session.load(session_id)
    → Check file exists
    → Deserialize JSON
    → Update instance fields
    → Return True/False
```
