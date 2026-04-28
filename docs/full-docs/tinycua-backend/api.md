# API Endpoints Documentation

**Files**: `tinycua_backend/api/auth.py`, `tinycua_backend/api/sessions.py`, `tinycua_backend/api/messages.py`, `tinycua_backend/api/tenant.py`, `tinycua_backend/api/dependencies.py`

---

## api/dependencies.py — Shared API Dependencies

**Purpose**: Provides reusable FastAPI dependencies used across multiple endpoint modules.

### `get_store() -> Any`

```python
def get_store() -> Any:
    return get_session_store()
```

Thin wrapper around `storage.database.get_session_store()`. Returns a cached `SessionStore` instance from the SDK. Used by endpoints to perform CRUD on sessions and messages.

### `get_session_or_404(session_id: str, current: CurrentTenant)`

```python
async def get_session_or_404(
    session_id: str,
    current: CurrentTenant = Depends(get_current_tenant),
) -> Any:
```

**Purpose**: Validates a session ID, looks up the session, verifies tenant ownership, and returns the session object. Used as a FastAPI dependency in endpoints that operate on a specific session.

**Step-by-step**:
1. **Parse UUID**:
   ```python
   try:
       uuid_session_id = uuid.UUID(session_id)
   except ValueError:
       raise HTTPException(status_code=400, detail="Invalid session ID")
   ```
   Rejects malformed UUIDs immediately with 400 Bad Request.

2. **Lookup session**:
   ```python
   store = get_store()
   session = store.get_session(uuid_session_id)
   if not session:
       raise HTTPException(status_code=404, detail="Session not found")
   ```

3. **Verify tenant**:
   ```python
   _verify_session_tenant(session, current)
   ```

### `_verify_session_tenant(session: Any, current: CurrentTenant)`

```python
def _verify_session_tenant(session: Any, current: CurrentTenant) -> None:
    if current.is_system:
        return
    session_user_id = str(session.user_id) if session.user_id else None
    expected_id = str(current.user_id) if current.user_id else str(current.tenant.id)
    if session_user_id != expected_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this tenant")
```

**Access control logic**:
- **System tenant**: Always allowed (`is_system` bypasses checks)
- **User-scoped session**: `session.user_id` must match `current.user_id`
- **Tenant-scoped session** (no specific user): `session.user_id` must match `current.tenant.id`

This ensures users can only access sessions belonging to their tenant (or themselves).

---

## api/auth.py — Authentication Endpoints

**Router prefix**: `/v1/auth`
**Tags**: `["auth"]`

### Rate Limiting

```python
_rate_limit_store: defaultdict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()
```

In-memory rate limiting storage keyed by client IP. Uses a `threading.Lock()` for thread safety in multi-worker deployments (note: does not scale across multiple processes).

```python
DUMMY_HASH = "$2b$12$cDDFuYGuSw2dot4asdD61u2NNn9EZW1Tom/yGpOcSdFYJ2A0wDhPS"
```

A fixed bcrypt hash used for timing-safe failure when a user is not found. This prevents timing attacks that could reveal whether an email exists in the database.

#### `_rate_limit_dependency(max_requests=5, window_seconds=60)`

Factory function returning a dependency that:
1. Extracts client IP from `request.client.host`
2. Removes timestamps older than `window_seconds`
3. If count >= `max_requests`, raises `HTTPException(429)`
4. Otherwise, appends current timestamp

### `POST /v1/auth/register`

**Request**: `RegisterRequest`
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "tenant_name": "My Organization"
}
```

**Response**: `TokenResponse` (201 Created)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "api_key": "tcu_xxxxxxxx..."
}
```

**Logic**:
1. Applies rate limiting (5 requests/minute per IP)
2. Creates `AuthService(db)`
3. Calls `auth_service.register(email, password, tenant_name)`
4. Catches `ValueError` and converts to `HTTPException(409 CONFLICT)`

**Business rules**:
- Password must be >= 8 characters (enforced by `RegisterRequest` schema)
- Password complexity: 1 uppercase, 1 lowercase, 1 digit, 1 special character
- Email+tenant_id must be unique (database `UniqueConstraint`)

### `POST /v1/auth/login`

**Request**: `LoginRequest`
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response**: `TokenResponse`

**Logic flow**:

1. **If `tenant_id` is provided**:
   ```python
   auth_service = AuthService(db)
   return auth_service.login(email, password, tenant_id)
   ```
   Direct lookup by email + tenant_id via `AuthService.login()`.

2. **If `tenant_id` is NOT provided**:
   ```python
   users = db.query(User).filter(User.email == request.email).all()
   ```
   Queries all users with this email across all tenants.

   - **No users found**: Runs `verify_password(request.password, DUMMY_HASH)` to consume the same time as a real verification, then returns `401 Unauthorized`
   - **Multiple users found**: Returns `400 Bad Request` with message "Multiple tenants found for this email. Please specify tenant_id."
   - **Single user found**: Verifies password, creates JWT token, returns `TokenResponse`

**Why the dummy hash?** To prevent timing attacks. Without it, an attacker could measure response times to determine if an email exists in the database.

### `GET /v1/auth/me`

**Response**: `CurrentUserResponse`
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440001",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com"
}
```

**Logic**:
1. Uses `get_current_tenant` dependency to authenticate
2. Looks up the user in the database by `current_tenant.user_id` and `current_tenant.tenant.id`
3. Returns 404 if user not found

---

## api/sessions.py — Session Endpoints

**Router prefix**: `/v1/sessions`
**Tags**: `["sessions"]`

### Pydantic Models

#### `SessionCreate`
```python
class SessionCreate(BaseModel):
    name: str | None = None
    parent_session_id: str | None = None
```

#### `SessionUpdate`
```python
class SessionUpdate(BaseModel):
    name: str | None = None
```

#### `SessionResponse`
```python
class SessionResponse(BaseModel):
    id: str
    name: str | None
    parent_session_id: str | None
    created_at: str
    updated_at: str
```

#### `_session_to_response(session)`
Converts a SessionStore session object to the API response model. Handles `parent_session_id` being optional.

### `POST /v1/sessions` — Create Session

**Request**: `SessionCreate`

**Response**: `SessionResponse` (201 Created)

**Logic**:
```python
store = get_store()
user_id = str(current.user_id) if current.user_id else str(current.tenant.id)
tenant_id = str(current.tenant.id)
parent_uuid = uuid.UUID(session_data.parent_session_id) if session_data.parent_session_id else None
session = store.create_session(
    name=session_data.name or "Session",
    user_id=user_id,
    tenant_id=tenant_id,
    parent_session_id=parent_uuid,
)
```

- Falls back to "Session" if no name provided
- Associates session with the authenticated user/tenant
- Supports parent-child session relationships via `parent_session_id`

### `GET /v1/sessions` — List Sessions

**Query params**: `limit=100`, `offset=0`

**Response**: `list[SessionResponse]`

**Logic**:
```python
if current.is_system:
    sessions = store.list_sessions()
else:
    user_id = str(current.user_id) if current.user_id else str(current.tenant.id)
    sessions = store.list_sessions(user_id=user_id)
```

- System tenant sees all sessions
- Regular tenants see only their own sessions (filtered by `user_id`, which is either the user ID or tenant ID)

### `GET /v1/sessions/{session_id}` — Get Session

**Response**: `SessionResponse`

Uses `get_session_or_404` dependency for validation and tenant verification.

### `PUT /v1/sessions/{session_id}` — Update Session

**Request**: `SessionUpdate`

**Response**: `SessionResponse`

**Logic**:
```python
kwargs = {}
if session_data.name is not None:
    kwargs["name"] = session_data.name
updated = get_store().update_session(session.id, **kwargs)
```

Only updates fields that are explicitly provided (not `None`).

### `DELETE /v1/sessions/{session_id}` — Delete Session

**Status**: 204 No Content

### `GET /v1/sessions/{session_id}/lineage` — Session Lineage

**Response**: `list[LineageResponse]`
```python
class LineageResponse(BaseModel):
    id: str
    name: str | None
    parent_session_id: str | None
    lineage_depth: int
    created_at: str
```

**Logic**:
```python
lineage = store.get_lineage(session.id)
for s in lineage:
    _verify_session_tenant(s, current)
```

Gets the parent chain from root to current session and verifies tenant access for each ancestor.

### `POST /v1/sessions/search` — Search Messages

**Request**: `SearchRequest`
```python
class SearchRequest(BaseModel):
    query: str
    limit: int = 10
```

**Response**: `list[SearchResult]`
```python
class SearchResult(BaseModel):
    message_id: str
    session_id: str
    content: str
    turn_index: int
    role: str
```

**Logic**:
1. Calls `SQLiteSearch().search()` to get matching message IDs
2. Queries the database for full message data, filtered by tenant:
   ```python
   stmt = (
       select(Message)
       .join(SessionModel, Message.session_id == SessionModel.id)
       .where(Message.id.in_(message_ids))
       .where(SessionModel.tenant_id == tenant_id)
   )
   ```
3. Returns up to 200 characters of content per message

**Note**: Currently hardcoded to `SQLiteSearch`. In a PostgreSQL deployment, this would need to use `PostgreSQLSearch` instead.

---

## api/messages.py — Message Endpoints

**Router prefix**: `/v1/sessions`
**Tags**: `["messages"]`

### Pydantic Models

#### `MessageCreate`
```python
class MessageCreate(BaseModel):
    role: str
    content: str
```

#### `MessageResponse`
```python
class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    turn_index: int
    created_at: str
```

### `GET /v1/sessions/{session_id}/messages` — List Messages

**Query params**: `limit=100`, `offset=0`

**Response**: `list[MessageResponse]`

**Logic**:
```python
uuid_session_id = uuid.UUID(session_id)
store = get_store()
messages = store.get_messages(uuid_session_id, limit=limit)
messages = messages[offset : offset + limit]
```

Note: `offset` slicing happens in Python after fetching from the database. For large offsets, this is inefficient but acceptable for typical chat message volumes.

### `POST /v1/sessions/{session_id}/messages` — Create Message

**Request**: `MessageCreate`

**Response**: `MessageResponse` (201 Created)

**Logic**:
```python
message = store.add_message(
    session_id=uuid_session_id,
    role=message_data.role,
    content=message_data.content,
)
```

The `turn_index` is auto-incremented by `SessionStore`.

---

## api/tenant.py — Tenant Management Endpoints

**Router prefix**: `/v1/tenants`
**Tags**: `["tenants"]`

### Pydantic Models

#### `TenantResponse`
```python
class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    tenant_type: str
```

#### `TenantUpdateRequest`
```python
class TenantUpdateRequest(BaseModel):
    name: str
```

### `GET /v1/tenants/{tenant_id}` — Get Tenant

**Response**: `TenantResponse`

**Access control**:
```python
if not current_tenant.is_system and current_tenant.tenant.id != tenant.id:
    raise HTTPException(status_code=403, detail="Not authorized to access this tenant")
```

System tenants can view any tenant; regular tenants can only view themselves.

### `GET /v1/tenants/` — List Tenants

**Response**: `list[TenantResponse]`

**Access control**: Only system tenants allowed.
```python
if not current_tenant.is_system:
    raise HTTPException(status_code=403, detail="Only system tenant can list all tenants")
```

### `PATCH /v1/tenants/{tenant_id}` — Update Tenant

**Request**: `TenantUpdateRequest`

**Response**: `TenantResponse`

**Access control**: System tenants can update any tenant; regular tenants can only update themselves.

### `DELETE /v1/tenants/{tenant_id}` — Delete Tenant

**Status**: 204 No Content

**Access control**: Only system tenants can delete tenants.

---

## Endpoint Summary Table

| Method | Endpoint | Auth Required | Purpose |
|--------|----------|---------------|---------|
| GET | `/health` | No | Health check |
| POST | `/v1/auth/register` | No | Register new user/tenant |
| POST | `/v1/auth/login` | No | Login with email/password |
| GET | `/v1/auth/me` | Yes | Get current user |
| POST | `/v1/sessions` | Yes | Create session |
| GET | `/v1/sessions` | Yes | List sessions |
| GET | `/v1/sessions/{id}` | Yes | Get session |
| PUT | `/v1/sessions/{id}` | Yes | Update session |
| DELETE | `/v1/sessions/{id}` | Yes | Delete session |
| GET | `/v1/sessions/{id}/messages` | Yes | List messages |
| POST | `/v1/sessions/{id}/messages` | Yes | Add message |
| GET | `/v1/sessions/{id}/lineage` | Yes | Get parent chain |
| POST | `/v1/sessions/search` | Yes | Search messages |
| GET | `/v1/tenants/{id}` | Yes | Get tenant |
| GET | `/v1/tenants/` | Yes (system) | List tenants |
| PATCH | `/v1/tenants/{id}` | Yes | Update tenant |
| DELETE | `/v1/tenants/{id}` | Yes (system) | Delete tenant |
| POST | `/v1/sync/sessions` | Yes | Sync sessions |
| POST | `/v1/sync/memory` | Yes | Sync memory |
| GET | `/v1/sync/pull` | Yes | Pull updates |
