# Design Document: Backend Client SDK

**Spec**: `specs/remote-backend/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-17

---

## Overview

The Backend Client SDK provides:
1. **Agent class** (user-facing) - Deploy, run, load, delete agents
2. **Standalone functions** - get_agent, list_agents, health_check

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     User Code                            │
│                                                          │
│  from tinycua_sdk import Agent, get_agent, list_agents │
│                                                          │
│  agent = Agent(...)                                      │
│  await agent.deploy()                                    │
│  await agent.run("Hello")  # Automatically remote        │
│                                                          │
│  agent_data = await get_agent(agent_id="...")           │
│  agents = await list_agents(backend_url="...")          │
└─────────────────────────────────────────────────────────┘
```

---

## Standalone Functions

### get_agent()

```python
async def get_agent(
    agent_id: str,
    backend_url: str,
    backend_api_key: str | None = None,
    backend_headers: dict[str, str] | None = None,
) -> dict:
    """Get agent details from backend by ID.

    Args:
        agent_id: ID of the agent
        backend_url: Backend server URL
        backend_api_key: API key for authentication
        backend_headers: Custom headers (including multi-tenancy)

    Returns:
        Agent configuration dict from backend

    """
    client = Client(
        base_url=backend_url,
        api_key=backend_api_key,
        headers=backend_headers,
    )
    return await client.get_agent(agent_id)
```

### list_agents()

```python
async def list_agents(
    backend_url: str,
    backend_api_key: str | None = None,
    backend_headers: dict[str, str] | None = None,
    user_id: str | None = None,
) -> list[dict]:
    """List all agents in backend.

    Args:
        backend_url: Backend server URL
        backend_api_key: API key for authentication
        backend_headers: Custom headers for auth
        user_id: User ID for multi-tenancy (filters by user)

    Returns:
        List of agent configuration dicts

    """
    client = Client(
        base_url=backend_url,
        api_key=backend_api_key,
        headers=backend_headers,
    )
    return await client.list_agents(user_id)
```

### health_check()

```python
async def health_check(
    backend_url: str,
    backend_api_key: str | None = None,
    backend_headers: dict[str, str] | None = None,
) -> bool:
    """Check if backend is healthy.

    Args:
        backend_url: Backend server URL
        backend_api_key: API key for authentication
        backend_headers: Custom headers for auth

    Returns:
        True if backend is healthy, False otherwise

    """
    client = Client(
        base_url=backend_url,
        api_key=backend_api_key,
        headers=backend_headers,
    )
    return await client.health_check()
```

---

## Configuration Priority

Backend settings follow this priority:

1. **Per-agent** (highest priority)
   - `agent.backend_url`
   - `agent.backend_api_key`
   - `agent.backend_headers`

2. **Global config** (medium priority)
   - `Config.BACKEND_URL`
   - `Config.API_KEY`

3. **Default** (lowest priority)
   - `http://localhost:8000`

### Getting Backend Config

Helper method to get backend config with fallback:

```python
def _get_backend_config(self) -> tuple[str, str | None, dict[str, str] | None]:
    """Get backend configuration with priority.

    Returns:
        Tuple of (backend_url, api_key, headers)

    """
    from tinycua_sdk.config import config

    # Priority: agent config > global config > default
    backend_url = self.config.backend_url or config.BACKEND_URL
    api_key = self.config.backend_api_key or config.API_KEY
    headers = self.config.backend_headers

    return backend_url, api_key, headers
```

---

## Agent Methods

### deploy()

After deployment, `agent.agent_id` is set from the backend response:

```python
async def deploy(self) -> dict[str, Any]:
    """Deploy the agent to the backend.

    Returns:
        Deployment result with agent_id and status

    """
    client = Client(
        base_url=self.config.backend_url,
        api_key=self.config.backend_api_key,
        headers=self.config.backend_headers,
    )

    response = await client.deploy_agent(
        agent_config=self.to_config(),
        user_id=self.config.user_id,
    )

    # Set agent_id from backend response
    self.config.agent_id = response["agent_id"]
    self.config.mode = "deployed"

    return response
```

### load_agent()

Class method to load an existing agent from backend:

```python
@classmethod
async def load_agent(
    cls,
    agent_id: str,
    backend_url: str,
    backend_api_key: str | None = None,
    backend_headers: dict[str, str] | None = None,
) -> "Agent":
    """Load an existing agent from the backend.

    Args:
        agent_id: ID of the agent to load
        backend_url: Backend server URL
        backend_api_key: API key for authentication
        backend_headers: Custom headers (including multi-tenancy)

    Returns:
        Agent instance with configuration from backend

    """
    client = Client(
        base_url=backend_url,
        api_key=backend_api_key,
        headers=backend_headers,
    )

    agent_data = await client.get_agent(agent_id)

    return cls.from_config(agent_data)
```

### delete()

```python
async def delete(self) -> None:
    """Delete the agent from the backend.

    """
    if not self.config.agent_id:
        raise RuntimeError("Agent not deployed")

    client = Client(
        base_url=self.config.backend_url,
        api_key=self.config.backend_api_key,
        headers=self.config.backend_headers,
    )

    await client.delete_agent(
        agent_id=self.config.agent_id,
        user_id=self.config.user_id,
    )

    self.config.agent_id = None
    self.config.mode = "local"
```

### __str__()

Formatted output of agent information:

```python
def __str__(self) -> str:
    """Return formatted string representation of the agent.

    Returns:
        Formatted string with agent details

    """
    lines = [
        f"Agent: {self.config.name}",
        f"  Mode: {self.config.mode}",
        f"  Model: {self.config.model}",
        f"  Provider: {self.config.provider}",
    ]

    if self.config.agent_id:
        lines.append(f"  Agent ID: {self.config.agent_id}")
        lines.append(f"  Backend: {self.config.backend_url}")

    if self.config.backend_headers:
        lines.append(f"  Headers: {list(self.config.backend_headers.keys())}")

    lines.append(f"  Tools: {len(self.config.tools)}")
    lines.append(f"  Sub-agents: {len(self.config.sub_agents)}")

    return "\n".join(lines)
```

---

## AgentConfig Updates

```python
@dataclass
class AgentConfig:
    # ... existing fields ...

    # Backend (deployed mode)
    backend_url: str | None = None
    backend_api_key: str | None = None
    backend_headers: dict[str, str] | None = None  # Includes multi-tenancy headers
```

---

## Client Class (Internal)

Used internally by Agent and standalone functions:

```python
class Client:
    """Internal client for backend communication."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = headers or {}
        self.timeout = timeout

    def _get_headers(self, user_id: str | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self.headers)
        if user_id:
            headers["X-User-ID"] = user_id
        return headers

    async def deploy_agent(self, agent_config: dict, user_id: str | None = None) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/v1/agents",
                json=agent_config,
                headers=self._get_headers(user_id),
            )
            response.raise_for_status()
            return response.json()

    async def get_agent(self, agent_id: str, user_id: str | None = None) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/agents/{agent_id}",
                headers=self._get_headers(user_id),
            )
            response.raise_for_status()
            return response.json()

    async def delete_agent(self, agent_id: str, user_id: str | None = None) -> None:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                f"{self.base_url}/v1/agents/{agent_id}",
                headers=self._get_headers(user_id),
            )
            response.raise_for_status()

    async def list_agents(self, user_id: str | None = None) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/v1/agents",
                headers=self._get_headers(user_id),
            )
            response.raise_for_status()
            return response.json()

    async def execute(self, agent_id: str, messages: list[dict], tools: list[dict] | None = None, user_id: str | None = None, stream: bool = True) -> AsyncIterator[dict]:
        payload = {"messages": messages}
        if tools:
            payload["tools"] = tools
        if stream:
            payload["stream"] = True

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/agents/{agent_id}/run",
                json=payload,
                headers=self._get_headers(user_id),
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield json.loads(line[6:])
                    elif line:
                        yield line

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False
```

---

## Usage Examples

### Deploy and Run

```python
from tinycua_sdk import Agent

agent = Agent(
    name="my-agent",
    model="qwen/qwen3.5-9b",
    tools=[get_weather],
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
    backend_headers={"X-User-ID": "user-123"},  # Multi-tenancy via custom headers
)

await agent.deploy()
print(agent)  # Shows agent details including agent_id

response = await agent.run("What's the weather in Tokyo?")
```

### Load Existing Agent

```python
from tinycua_sdk import Agent

agent = await Agent.load_agent(
    agent_id="agent-123",
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
    backend_headers={"X-User-ID": "user-123"},
)

response = await agent.run("Hello")
```

### Standalone Functions

```python
from tinycua_sdk import get_agent, list_agents, health_check

# Get agent details
agent_data = await get_agent(
    agent_id="agent-123",
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
)

# List all agents (with multi-tenancy)
agents = await list_agents(
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
    backend_headers={"X-User-ID": "user-123"},
)

# Check health
is_healthy = await health_check(
    backend_url="http://localhost:8000",
)
```

### Load Existing Agent

```python
from tinycua_sdk import Agent

agent = await Agent.load_agent(
    agent_id="agent-123",
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
)

response = await agent.run("Hello")
```

### Standalone Functions

```python
from tinycua_sdk import get_agent, list_agents, health_check

# Get agent details from backend by ID (requires auth)
agent_data = await get_agent(
    agent_id="agent-123",
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
)

# List all agents in backend (requires auth, with multi-tenancy)
agents = await list_agents(
    backend_url="http://localhost:8000",
    backend_api_key="my-key",
    backend_headers={"X-User-ID": "user-123"},
)

# Check if backend is healthy (no auth required)
is_healthy = await health_check(
    backend_url="http://localhost:8000",
)
```

### list_agents()

```python
async def list_agents(
    backend_url: str,
    backend_api_key: str | None = None,
    backend_headers: dict[str, str] | None = None,
) -> list[dict]:
    """List all agents in backend.

    Args:
        backend_url: Backend server URL
        backend_api_key: API key for authentication
        backend_headers: Custom headers (including multi-tenancy headers like X-User-ID)

    Returns:
        List of agent configuration dicts

    """
    client = Client(
        base_url=backend_url,
        api_key=backend_api_key,
        headers=backend_headers,
    )
    return await client.list_agents()
```

---

## Error Handling

| Exception | Description |
|-----------|-------------|
| httpx.ConnectError | Cannot connect to backend |
| httpx.TimeoutException | Request timed out |
| httpx.HTTPStatusError | 4xx/5xx response |
| RuntimeError | Agent not deployed when required |

---

## Future Considerations

- Retry logic with exponential backoff
- Connection pooling
- Automatic re-deployment on config change
