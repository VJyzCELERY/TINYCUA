# Sync System

**Files**:
- `tinycua_backend/sync/endpoints.py`
- `tinycua_backend/sync/service.py`
- `tinycua_backend/sync/resolver.py`

---

## sync/endpoints.py — Sync API Endpoints

**Purpose**: Exposes REST endpoints for multi-device synchronization. Allows clients to push local changes, pull remote updates, and resolve conflicts.

**Router prefix**: `/v1/sync`
**Tags**: `["sync"]`

### Global SyncService Instance

```python
_sync_service = SyncService()
```

A module-level singleton `SyncService` is created at import time. This is acceptable because `SyncService` is stateless and relies on `get_session_store()` for database access.

### Pydantic Models

#### `SessionSyncItem`
```python
class SessionSyncItem(BaseModel):
    id: str
    name: str | None = None
    updated_at: str | None = None
```

Represents a session sent from the client. `updated_at` is an ISO timestamp string used for conflict resolution.

#### `SessionSyncRequest`
```python
class SessionSyncRequest(BaseModel):
    sessions: list[SessionSyncItem]
```

#### `SessionSyncResponse`
```python
class SessionSyncResponse(BaseModel):
    synced: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    errors: list[dict[str, Any]]
```

- `synced`: Successfully synchronized sessions
- `conflicts`: Sessions where local and remote diverged, with resolution info
- `errors`: Sessions that failed to sync

#### `MemorySyncItem`
```python
class MemorySyncItem(BaseModel):
    id: str
    content: str | None = None
    updated_at: str | None = None
```

**Note**: The `id` here is treated as `session_id` in the service layer. This naming inconsistency is a known artifact — the client sends memory items with session IDs.

#### `MemorySyncRequest` / `MemorySyncResponse`

Same pattern as session sync but for messages (called "memories" in the sync API).

#### `PullResponse`
```python
class PullResponse(BaseModel):
    sessions: list[dict[str, Any]]
    memories: list[dict[str, Any]]
```

### `POST /v1/sync/sessions` — Sync Sessions

**Request**: `SessionSyncRequest`

**Response**: `SessionSyncResponse`

**Logic**:
```python
user_id = str(current.user_id) if current.user_id else str(current.tenant.id)
sessions_dict = [s.model_dump() for s in sync_data.sessions]
result = _sync_service.sync_sessions(user_id, sessions_dict)
return SessionSyncResponse(**result)
```

- Converts Pydantic models to plain dicts for the service layer
- Resolves `user_id` from either the authenticated user or the tenant ID

### `POST /v1/sync/memory` — Sync Memory

**Request**: `MemorySyncRequest`

**Response**: `MemorySyncResponse`

Same pattern as session sync but delegates to `SyncService.sync_memory()`.

### `GET /v1/sync/pull` — Pull Updates

**Query params**: `since: str | None = None` (ISO timestamp)

**Response**: `PullResponse`

**Logic**:
```python
user_id = str(current.user_id) if current.user_id else str(current.tenant.id)
result = _sync_service.pull_updates(user_id, since)
return PullResponse(**result)
```

Returns all sessions and messages that have been updated since the given timestamp. If `since` is omitted, returns all sessions and messages.

---

## sync/service.py — SyncService

**Purpose**: Implements the business logic for synchronization, including conflict detection, last-write-wins resolution, and batch operations.

### `_get_store()`

```python
def _get_store(self) -> Any:
    return get_session_store()
```

Delegates to the cached `SessionStore`.

### `sync_sessions(user_id, sessions) -> dict`

**Algorithm per session**:

```
For each session_data in sessions:
    1. Validate session_id exists
    2. Parse session_id as UUID
    3. Look up existing session in SessionStore
    4. If exists:
        a. Convert existing to dict
        b. detect_conflict(local=session_data, remote=existing_dict)
        c. If conflict:
            - resolve_conflict() -> winner, resolution
            - If remote wins: update session in store
            - Append to conflicts list
        d. If no conflict: use existing (no change needed)
    5. If not exists:
        a. create_session() with provided ID
        b. Append to synced list
    6. On error: append to errors list
```

**Why session_id in create_session()?** The SDK's `SessionStore.create_session()` accepts an optional `session_id` parameter, allowing the client to preserve UUIDs across devices. If the client generated the UUID locally, passing it ensures consistency.

**Conflict fields checked**: `name`, `content`, `role` (in `resolver.py`)

### `sync_memory(user_id, memories) -> dict`

**Algorithm per memory item**:

```
For each memory_data in memories:
    1. Extract session_id from memory_data["id"]  (note: client sends session_id as "id")
    2. Parse as UUID
    3. Look up session in SessionStore
    4. If session not found: error
    5. Add message to session:
        role = memory_data.get("role", "user")
        content = memory_data.get("content", "")
        reasoning = memory_data.get("reasoning")
    6. If success: append to synced list
    7. On error: append to errors list
```

**Note**: Memory sync does NOT use conflict detection. It blindly appends messages. This is by design: messages are append-only and conflicts are not expected at the message level (only at the session metadata level).

### `pull_updates(user_id, since) -> dict`

**Algorithm**:

1. List all sessions for the user:
   ```python
   sessions = store.list_sessions(user_id=user_id)
   ```

2. If `since` is provided, filter sessions:
   ```python
   since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
   sessions = [s for s in sessions if s.updated_at.replace(tzinfo=timezone.utc) > since_dt]
   ```

3. For each session, get messages and filter by `since`:
   ```python
   for session in sessions:
       messages = store.get_messages(session.id)
       for msg in messages:
           if since and msg_created <= since_dt:
               continue
           memories.append({...})
   ```

4. Return both session dicts and memory dicts

**Timezone handling**: `since.replace("Z", "+00:00")` converts ISO 8601 `Z` suffix to Python's `+00:00` format, which `datetime.fromisoformat()` can parse in Python 3.11+.

**Performance note**: `pull_updates` fetches ALL messages for each session, then filters in Python. For large message histories, this is O(n*m) and could be optimized with database-level filtering.

---

## sync/resolver.py — Conflict Detection and Resolution

**Purpose**: Provides deterministic conflict detection and last-write-wins resolution for sync operations.

### `_parse_datetime(value)`

```python
def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
```

Helper that normalizes string timestamps to `datetime` objects. Handles both ISO strings and existing `datetime` instances (defensive programming).

### `resolve_conflict(local_item, remote_item) -> tuple[dict, str]`

**Last-Write-Wins (LWW) algorithm**:

```python
local_updated = _parse_datetime(local_item.get("updated_at"))
remote_updated = _parse_datetime(remote_item.get("updated_at"))

if local_updated is None:
    local_updated = datetime.min.replace(tzinfo=timezone.utc)
if remote_updated is None:
    remote_updated = datetime.min.replace(tzinfo=timezone.utc)

if remote_updated > local_updated:
    return remote_item, "remote_wins"
elif local_updated > remote_updated:
    return local_item, "local_wins"
else:
    server_time = datetime.now(timezone.utc).isoformat()
    local_item["updated_at"] = server_time
    return local_item, "local_wins"
```

**Rules**:
1. If `remote_updated > local_updated`: remote wins
2. If `local_updated > remote_updated`: local wins
3. If timestamps are equal (or both missing): local wins, but timestamp is bumped to current server time to break the tie

**Why "local wins" on tie?** Arbitrary choice, but deterministic. Bumping the timestamp ensures future syncs won't re-detect the same conflict.

### `detect_conflict(local_item, remote_item) -> bool`

**Two-phase detection**:

**Phase 1 — Timestamp mismatch**:
```python
local_updated = _parse_datetime(local_item.get("updated_at"))
remote_updated = _parse_datetime(remote_item.get("updated_at"))

if local_updated is None or remote_updated is None:
    return False

if local_updated != remote_updated:
    return True
```

If either item lacks a timestamp, no conflict is assumed (can't compare). If timestamps differ, a conflict is declared.

**Phase 2 — Field-level divergence** (only if timestamps are equal):
```python
conflict_fields = ["name", "content", "role"]
for field in conflict_fields:
    local_val = local_item.get(field)
    remote_val = remote_item.get(field)
    if local_val != remote_val:
        return True
```

If timestamps are identical but fields differ, it's a true conflict (same edit time on different devices).

**Why check fields when timestamps differ?** Actually, the function returns `True` immediately on timestamp mismatch. The field check only runs when timestamps are equal. This means:
- Different timestamps → conflict (regardless of content)
- Same timestamps → check content for divergence

This is conservative: any concurrent modification is treated as a conflict, even if the final values happen to be the same.

---

## Sync Data Flow

```
Client Device A                    Backend                    Client Device B
    |                                |                            |
    |--> POST /v1/sync/sessions      |                            |
    |    [{id: "x", name: "New"}]    |                            |
    |                                |                            |
    |<-- SessionSyncResponse         |                            |
    |    {synced: [...]}             |                            |
    |                                |                            |
    |                                |<-- POST /v1/sync/sessions   |
    |                                |    [{id: "x", name: "Alt"}] |
    |                                |                            |
    |                                |--> detect_conflict()       |
    |                                |    timestamps differ?      |
    |                                |                            |
    |                                |--> resolve_conflict()      |
    |                                |    last-write-wins         |
    |                                |                            |
    |                                |--> SessionSyncResponse      |
    |                                |    {conflicts: [{...}]}     |
    |                                |                            |
    |<-- GET /v1/sync/pull?since=... |                            |
    |                                |                            |
    |<-- {sessions: [...],           |                            |
    |     memories: [...]}           |                            |
```

---

## Design Decisions

1. **Last-Write-Wins**: Simple, deterministic, and sufficient for chat sessions where user intent is clear. Does not handle merge conflicts (e.g., concurrent edits to the same message).

2. **Session-level conflicts only**: Messages are append-only. If two devices add messages to the same session, both are accepted without conflict detection.

3. **UUID preservation**: Clients can specify session IDs during sync, preserving cross-device identity without a separate mapping layer.

4. **No operational transforms**: The sync system does not use OT or CRDTs. Conflicts are resolved by timestamp, not by merging content.
