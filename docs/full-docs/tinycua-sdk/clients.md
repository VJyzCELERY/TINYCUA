# Clients Package Documentation

The `clients/` package provides HTTP clients for communicating with LLM APIs and the TINYCUA backend server.

**Package path:** `tinycua_sdk/clients/`

---

## client.py - ResponsesClient

### Purpose

`ResponsesClient` is the primary client for making API calls to LLM providers. It supports both the OpenAI "Responses API" format and standard "Chat Completions" format, with automatic fallback between them.

### Constructor

```python
class ResponsesClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = 3,
    )
```

**Configuration sources:**
- `base_url`: Parameter → `TINYCUA_API_URL` env var → `"http://localhost:8000"`
- `api_key`: Parameter → `TINYCUA_API_KEY` env var → `""`

**HTTP client setup:**
```python
self._client = httpx.AsyncClient(
    base_url=self.base_url,
    timeout=60.0,
    headers={"Authorization": f"Bearer {self.api_key}"} if api_key else {},
)
```

Uses `httpx.AsyncClient` for async HTTP. 60-second timeout accommodates slow LLM responses.

### create() - Non-Streaming Requests

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def create(self, request: ResponseRequest) -> Response
```

**Retry logic:** Uses `tenacity` with exponential backoff (1s to 10s) and up to 3 attempts.

**Request building:**
1. Extracts system prompt from `request.input` messages
2. Builds payload in Chat Completions format:
   ```python
   payload = {
       "model": request.model,
       "messages": messages,
       "temperature": request.temperature,
       "max_tokens": request.max_tokens,
   }
   ```
3. If tools present, adds them via `to_config()`

**API fallback strategy:**
```python
try:
    response = await self._client.post("/v1/responses", json=payload)
    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        # Try chat completions
        response = await self._client.post("/v1/chat/completions", json=payload)
except httpx.HTTPStatusError:
    # Fall back to chat completions
    response = await self._client.post("/v1/chat/completions", json=payload)
```

**Why two attempts?** Some OpenAI-compatible endpoints support `/v1/chat/completions` but not `/v1/responses`. The client tries the newer API first, then falls back.

**Usage extraction:**
```python
usage_data = data.get("usage", {})
if isinstance(usage_data, dict):
    usage = {
        "input_tokens": usage_data.get("prompt_tokens", 0),
        "output_tokens": usage_data.get("completion_tokens", 0),
        "total_tokens": usage_data.get("total_tokens", 0),
    }
```

Normalizes between responses format (`input_tokens`) and chat completions format (`prompt_tokens`).

### stream() - Streaming Requests

```python
async def stream(self, request: ResponseRequest) -> AsyncIterator[StreamEvent]
```

**Implementation:**
```python
async with self._client.stream("POST", "/v1/chat/completions", json=payload) as response:
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            data = line[6:]
            if data == "[DONE]":
                break
            event_data = json.loads(data)
            yield StreamEvent(type=StreamEventType.CONTENT, data=event_data)
```

Uses SSE (Server-Sent Events) format. Streams directly through `/v1/chat/completions` (more compatible with various providers).

**Why always chat completions for streaming?** Many OpenAI-compatible endpoints have better SSE support for chat completions than responses.

---

## backend.py - BackendClient

### Purpose

`BackendClient` communicates with the TINYCUA backend server for remote agent management, execution, and session handling.

### Constructor

```python
def __init__(
    self,
    base_url: str,
    api_key: str | None = None,
    email: str | None = None,
    password: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
)
```

Supports two authentication modes:
- **API Key**: Direct bearer token authentication
- **Email/Password**: For login-based authentication

Additional `headers` support multi-tenancy and custom auth schemes.

### Authentication Methods

**login():**
```python
async def login(self, **kwargs: Any) -> dict[str, Any]:
    response = await self._client.post(
        f"{self.base_url}/v1/auth/login",
        json=kwargs,  # e.g., {"email": "...", "password": "..."}
    )
    data = response.json()
    self.api_key = data.get("access_token")
    self._tenant_id = data.get("tenant_id")
    self._user_id = data.get("user_id")
    return data
```

**register():**
```python
async def register(self, **kwargs: Any) -> dict[str, Any]:
    response = await self._client.post(
        f"{self.base_url}/v1/auth/register",
        json=kwargs,
    )
```

**create_tenant():**
```python
async def create_tenant(self, tenant_name: str, **kwargs: Any) -> dict[str, Any]:
    payload = {"tenant_name": tenant_name}
    payload.update(kwargs)
    response = await self._client.post(
        f"{self.base_url}/v1/tenants",
        json=payload,
        headers=self._get_headers(),
    )
```

### Agent Management

```python
async def deploy_agent(self, agent_config: dict[str, Any]) -> dict[str, Any]
async def get_agent(self, agent_id: str) -> dict[str, Any]
async def delete_agent(self, agent_id: str) -> None
async def list_agents(self) -> list[dict[str, Any]]
```

**deploy_agent()** normalizes the payload:
```python
if "agent" in agent_config:
    agent_data = agent_config["agent"]
else:
    agent_data = agent_config

payload = {
    "name": agent_data.get("name", "agent"),
    "config": {k: v for k, v in agent_data.items() if k != "name"},
}
```

Supports both wrapped (`{"agent": {...}}`) and flat config formats.

### Agent Execution

```python
async def execute(
    self,
    agent_id: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    stream: bool = True,
) -> AsyncIterator[dict[str, Any]]
```

**Execution flow:**
1. Extracts the most recent user message from `messages` (reversed search)
2. Builds payload with `user_input` and optional `tools`
3. Streams POST to `/v1/agents/{agent_id}/run`
4. Yields parsed JSON from each SSE line

**Why extract user_input from messages?** The backend's run endpoint expects a single `user_input` string rather than the full message history. The backend manages session state server-side.

### Session Management

```python
async def create_session(self, agent_id: str, name: str | None = None) -> dict[str, Any]
async def get_messages(self, session_id: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]
async def add_message(self, session_id: str, role: str, content: str) -> dict[str, Any]
```

These wrap the backend's session REST API:
- `POST /v1/sessions` - Create session
- `GET /v1/sessions/{session_id}/messages` - Get messages
- `POST /v1/sessions/{session_id}/messages` - Add message

### Tool Management

```python
async def list_tools(self) -> list[dict[str, Any]]
async def get_tool(self, tool_id: str) -> dict[str, Any]
async def deploy_tool(self, tool_bundle: dict[str, Any]) -> dict[str, Any]
```

Wraps:
- `GET /v1/tools` - List all tools
- `GET /v1/tools/{tool_id}` - Get specific tool
- `POST /v1/tools` - Deploy tool bundle

### Health Check

```python
async def health_check(self) -> bool
async def test_connection(self) -> bool
```

Both check `GET /health` with 200 status. `test_connection()` catches more exception types.

### Header Building

```python
def _get_headers(self) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if self.api_key:
        headers["Authorization"] = f"Bearer {self.api_key}"
    headers.update(self.headers)
    return headers
```

Priority: Base headers → Authorization → Custom headers. Custom headers can override defaults.

---

## agent_client.py - AgentClient

### Purpose

`AgentClient` provides a higher-level interface for running agent interactions. It wraps `ResponsesClient` and manages the tool execution loop for client-orchestrated mode.

### Constructor

```python
class AgentClient:
    def __init__(self, client: ResponsesClient):
        self.client = client
```

Takes a `ResponsesClient` instance. This design allows sharing the HTTP client across multiple `AgentClient` operations.

### run() - Main Execution Method

```python
async def run(
    self,
    agent: Agent,
    user_input: str,
    session_id: str | None = None,
    server_orchestrated: bool = False,
) -> Response
```

**Mode selection:**
```python
if session_id or server_orchestrated:
    return await self._run_server_orchestrated(agent, user_input, session_id)
return await self._run_client_orchestrated(agent, user_input)
```

### Client-Orchestrated Mode

```python
async def _run_client_orchestrated(self, agent: Agent, user_input: str) -> Response:
    messages = agent._build_context()
    messages.append({"role": "user", "content": user_input})
    
    request = ResponseRequest(
        model=agent.model,
        input=messages,
        tools=agent.tools,
        temperature=agent.policy.temperature,
    )
    
    response = await self.client.create(request)
    
    for _ in range(agent.policy.max_tool_calls):
        tool_calls = self._extract_tool_calls(response)
        if not tool_calls:
            break
        
        for tool_call in tool_calls:
            result = await self._execute_tool(tool_call)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["call_id"],
                "content": str(result),
            })
        
        request = ResponseRequest(...)
        response = await self.client.create(request)
    
    return response
```

**Tool loop:**
1. Send user message to LLM
2. Extract tool calls from response
3. Execute each tool
4. Append tool results to messages
5. Send updated messages back to LLM
6. Repeat up to `max_tool_calls` times

**Why client-orchestrated?** The client manages the full conversation state and tool execution. This gives more control but requires the client to handle all tool logic.

### Server-Orchestrated Mode

```python
async def _run_server_orchestrated(self, agent: Agent, user_input: str, session_id: str | None = None) -> Response:
    messages = agent._build_context()
    messages.append({"role": "user", "content": user_input})
    
    request = ResponseRequest(
        model=agent.model,
        input=messages,
        tools=agent.tools,
        temperature=agent.policy.temperature,
        session_id=session_id,
    )
    
    return await self.client.create(request)
```

In server-orchestrated mode, the client sends the full context but the server handles tool execution. The `session_id` tells the server which session to use.

### stream() - Streaming Execution

```python
async def stream(
    self,
    agent: Agent,
    user_input: str,
    session_id: str | None = None,
) -> Iterator[StreamEvent]
```

Builds the request and delegates to `self.client.stream(request)`. Returns an async iterator of `StreamEvent` objects.

### Tool Execution

```python
async def _execute_tool(self, tool_call: dict[str, Any]) -> Any:
    tool_name = tool_call["name"]
    args = json.loads(tool_call.get("arguments", "{}"))
    
    for tool in self._get_tool_by_name(tool_name):
        return tool.invoke(**args)
    
    raise ValueError(f"Tool {tool_name} not found")
```

Note: `AgentClient` maintains its own tool list via `_set_tools()` / `_get_tool_by_name()`. This is separate from the agent's tool list.

---

## protocol.py - BackendProtocol

### Purpose

Defines a `Protocol` (type hint interface) for backend clients. Not actively used by SDK code but provided for future type-hint use and third-party implementations.

```python
@runtime_checkable
class BackendProtocol(Protocol):
    base_url: str
    
    async def deploy_agent(self, agent_config: dict) -> dict: ...
    async def get_agent(self, agent_id: str) -> dict: ...
    async def delete_agent(self, agent_id: str) -> None: ...
    async def list_agents(self) -> list[dict]: ...
    async def execute(self, agent_id: str, messages: list[dict], tools: list[dict] | None, stream: bool) -> AsyncIterator[dict]: ...
    async def health_check(self) -> bool: ...
    async def list_tools(self) -> list[dict]: ...
    async def deploy_tool(self, tool_bundle: dict) -> dict: ...
```

**Why a Protocol?** Allows duck typing - any class implementing these methods can be used as a backend client, without explicit inheritance.

---

## Inter-Module Data Flow

### LLM API Call Flow
```
Agent.run() → AgentExecutor.run()
  → if local: Runner.run()
    → Runner._chat_direct()
      → ResponsesClient.create(request)
        → httpx.AsyncClient.post("/v1/responses")
        → (fallback) httpx.AsyncClient.post("/v1/chat/completions")
        → Response pydantic model
```

### Backend Execution Flow
```
Agent.run() → AgentExecutor._run_deployed()
  → BackendClient.execute(agent_id, messages, tools)
    → httpx.AsyncClient.stream("POST", "/v1/agents/{agent_id}/run")
    → Yield SSE events
```

### AgentClient Execution Flow
```
AgentClient.run(agent, user_input)
  → _run_client_orchestrated()
    → ResponsesClient.create(request) → LLM response
    → _extract_tool_calls(response)
    → _execute_tool(tool_call) → Tool.invoke()
    → ResponsesClient.create(updated_request) → Next LLM response
```
