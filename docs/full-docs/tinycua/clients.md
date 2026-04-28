# Clients Module Documentation

The clients module provides the HTTP client for communicating with remote backend servers.

---

## Module Structure

```
clients/
├── __init__.py      # Re-exports BackendClient
└── backend.py       # HTTP client for backend API
```

---

## `clients/__init__.py`

```python
from tinycua.clients.backend import BackendClient

__all__ = ["BackendClient"]
```

---

## `clients/backend.py`

### Purpose

`BackendClient` is an internal HTTP client for backend communication. It wraps `httpx.AsyncClient` and provides typed methods for all backend API endpoints.

**Key characteristics:**
- Uses `httpx.AsyncClient` for async HTTP with connection pooling
- Supports authenticated operations
- Handles streaming responses for agent execution
- Provides auth methods (login/register) with automatic token capture

### `BackendClient` Class

```python
class BackendClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        email: str | None = None,
        password: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ):
```

**Parameters:**
- `base_url` — Base URL of the backend server (trailing slash stripped)
- `api_key` — API key for Bearer token authentication
- `email` — Email for login-based authentication
- `password` — Password for login-based authentication
- `headers` — Custom headers (for auth, multi-tenancy, etc.)
- `timeout` — Request timeout in seconds (default 30)

**Internal state:**
```python
self._tenant_id: str | None = None
self._user_id: str | None = None
self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
```

**Why `httpx.AsyncClient`?**
- Native async/await support
- HTTP/2 support
- Connection pooling (reuses connections across requests)
- Timeout and retry built-in
- Streaming support

### `close()`

```python
async def close(self) -> None:
    await self._client.aclose()
```

**Important:** Always call `close()` when done to release connections. The client uses connection pooling, and unclosed clients can leak resources.

### Authentication

#### `login()`

```python
async def login(self, **kwargs: Any) -> dict[str, Any]:
```

**Endpoint:** `POST /v1/auth/login`

**Default fields:** `email`, `password`

**Additional fields:** Can pass custom auth fields like `username`, `totp`, etc.

**Automatic token capture:**
```python
response = await self._client.post("/v1/auth/login", json=kwargs)
response.raise_for_status()
data = response.json()
self.api_key = data.get("access_token")
self._tenant_id = data.get("tenant_id")
self._user_id = data.get("user_id")
```

After successful login, the client's `api_key` is automatically updated for subsequent requests.

#### `register()`

```python
async def register(self, **kwargs: Any) -> dict[str, Any]:
```

**Endpoint:** `POST /v1/auth/register`

**Default fields:** `email`, `password`, `tenant_name`

Also captures access token and tenant/user IDs on success.

#### Tenant/User Properties

```python
@property
def tenant_id(self) -> str | None:
    return self._tenant_id

@property
def user_id(self) -> str | None:
    return self._user_id
```

### Request Headers

```python
def _get_headers(self) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if self.api_key:
        headers["Authorization"] = f"Bearer {self.api_key}"
    headers.update(self.headers)
    return headers
```

**Header priority:**
1. Base `Content-Type: application/json`
2. `Authorization: Bearer {api_key}` (if set)
3. Custom headers from constructor

Custom headers can override the Content-Type but not the Authorization header (since `.update()` is called after).

### Agent Operations

#### `deploy_agent()`

```python
async def deploy_agent(self, agent_config: dict[str, Any]) -> dict[str, Any]:
```

**Endpoint:** `POST /v1/agents`

**Payload transformation:** The SDK sends `{ "agent": {...}, "tools": [...] }` but the backend expects `{ "name": str, "config": dict }`.

```python
if "agent" in agent_config:
    agent_data = agent_config["agent"]
    name = agent_data.get("name", "agent")
    config = {k: v for k, v in agent_data.items() if k != "name"}
else:
    name = agent_config.get("name", "agent")
    config = {k: v for k, v in agent_config.items() if k != "name"}

payload = {"name": name, "config": config}
```

**Why this transformation?** Maintains backward compatibility with both old format (direct config) and new format (nested under "agent" key).

#### `get_agent()`

```python
async def get_agent(self, agent_id: str) -> dict[str, Any]:
```

**Endpoint:** `GET /v1/agents/{agent_id}`

#### `delete_agent()`

```python
async def delete_agent(self, agent_id: str) -> None:
```

**Endpoint:** `DELETE /v1/agents/{agent_id}`

#### `list_agents()`

```python
async def list_agents(self) -> list[dict[str, Any]]:
```

**Endpoint:** `GET /v1/agents`

### Agent Execution

#### `execute()`

```python
async def execute(
    self,
    agent_id: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    stream: bool = True,
    plan_mode: bool = False,
) -> AsyncIterator[dict[str, Any]]:
```

**Endpoint:** `POST /v1/agents/{agent_id}/run`

**Features:**
- Extracts the most recent user message from `messages` list
- Supports streaming via `httpx.stream()`
- Supports plan mode (only plan-mode tools)
- Yields parsed JSON events from SSE stream

**Message extraction:**
```python
user_input = ""
for msg in reversed(messages):
    if msg.get("role") == "user":
        user_input = msg.get("content", "")
        break
```

**Streaming parsing:**
```python
async with self._client.stream("POST", f"/v1/agents/{agent_id}/run", json=payload, headers=self._get_headers()) as response:
    async for line in response.aiter_lines():
        line = line.strip()
        if line:
            if line.startswith("data:"):
                line = line[5:].strip()
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                pass
```

**Why SSE format?** The backend likely uses Server-Sent Events for streaming. Lines starting with `data:` are standard SSE format. The client strips this prefix and parses the JSON payload.

### Health Check

#### `health_check()`

```python
async def health_check(self) -> bool:
```

**Endpoint:** `GET /health`

**Timeout:** 5 seconds (hardcoded, shorter than default)

**Returns:** `True` if status code is 200, `False` otherwise.

### Tool Operations

#### `list_tools()`

```python
async def list_tools(self) -> list[dict[str, Any]]:
```

**Endpoint:** `GET /v1/tools`

#### `get_tool()`

```python
async def get_tool(self, tool_id: str) -> dict[str, Any]:
```

**Endpoint:** `GET /v1/tools/{tool_id}`

#### `deploy_tool()`

```python
async def deploy_tool(self, tool_bundle: dict[str, Any]) -> dict[str, Any]:
```

**Endpoint:** `POST /v1/tools`

### Session Operations

#### `create_session()`

```python
async def create_session(self, agent_id: str, name: str | None = None) -> dict[str, Any]:
```

**Endpoint:** `POST /v1/sessions`

#### `list_sessions()`

```python
async def list_sessions(self) -> list[dict[str, Any]]:
```

**Endpoint:** `GET /v1/sessions`

#### `update_session()`

```python
async def update_session(self, session_id: str, name: str | None = None) -> dict[str, Any]:
```

**Endpoint:** `PATCH /v1/sessions/{session_id}`

#### `get_messages()`

```python
async def get_messages(self, session_id: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
```

**Endpoint:** `GET /v1/sessions/{session_id}/messages`

**Query params:** `limit`, `offset`

#### `add_message()`

```python
async def add_message(self, session_id: str, role: str, content: str) -> dict[str, Any]:
```

**Endpoint:** `POST /v1/sessions/{session_id}/messages`

#### `get_session()`

```python
async def get_session(self, session_id: str) -> dict[str, Any]:
```

**Endpoint:** `GET /v1/sessions/{session_id}`

Returns complete session with messages.

### Memory Operations

#### `sync_memory()`

```python
async def sync_memory(self, agent_id: str, memory: dict[str, Any]) -> dict[str, Any]:
```

**Endpoint:** `POST /v1/agents/{agent_id}/memory`

#### `get_memory()`

```python
async def get_memory(self, agent_id: str) -> dict[str, Any]:
```

**Endpoint:** `GET /v1/agents/{agent_id}/memory`

#### `save_memory()`

```python
async def save_memory(self, agent_id: str, memory: dict[str, Any]) -> dict[str, Any]:
```

**Endpoint:** `PUT /v1/agents/{agent_id}/memory`

---

## API Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/auth/login` | Login with credentials |
| POST | `/v1/auth/register` | Register new user |
| POST | `/v1/agents` | Deploy agent |
| GET | `/v1/agents` | List agents |
| GET | `/v1/agents/{id}` | Get agent |
| DELETE | `/v1/agents/{id}` | Delete agent |
| POST | `/v1/agents/{id}/run` | Execute agent (streaming) |
| POST | `/v1/agents/{id}/memory` | Sync memory |
| GET | `/v1/agents/{id}/memory` | Get memory |
| PUT | `/v1/agents/{id}/memory` | Save memory |
| GET | `/v1/tools` | List tools |
| GET | `/v1/tools/{id}` | Get tool |
| POST | `/v1/tools` | Deploy tool |
| POST | `/v1/sessions` | Create session |
| GET | `/v1/sessions` | List sessions |
| PATCH | `/v1/sessions/{id}` | Update session |
| GET | `/v1/sessions/{id}` | Get session |
| GET | `/v1/sessions/{id}/messages` | Get messages |
| POST | `/v1/sessions/{id}/messages` | Add message |
| GET | `/health` | Health check |

---

## Error Handling

All methods use `response.raise_for_status()` which raises `httpx.HTTPStatusError` for 4xx/5xx responses.

**Common error patterns:**
- `401 Unauthorized` — Invalid or missing API key
- `403 Forbidden` — Valid auth but insufficient permissions
- `404 Not Found` — Agent/session/tool doesn't exist
- `409 Conflict` — Resource already exists
- `422 Unprocessable Entity` — Invalid request data
- `500 Internal Server Error` — Backend error

Callers should catch `httpx.HTTPStatusError` and handle appropriately.

---

## Design Decisions

1. **Single `AsyncClient` instance:** Reuses connections across all requests, improving performance.

2. **Bearer token auth:** Standard JWT/OAuth2 pattern. Token is automatically set after login.

3. **Custom headers support:** Allows multi-tenancy headers and other custom authentication.

4. **Streaming with `aiter_lines()`:** Parses SSE streams line by line, handling the `data:` prefix.

5. **Base URL normalization:** Strips trailing slash to avoid double slashes in paths.

7. **Timeout flexibility:** Default 30s for most operations, 5s for health checks.

8. **No retry logic:** Retries are handled by `RemoteConnectionManager`, not `BackendClient`. This keeps the client simple and focused.
