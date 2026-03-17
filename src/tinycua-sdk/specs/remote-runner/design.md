# Design Document: Remote Runner SDK

**Spec**: `specs/remote-runner/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-16

---

## Overview

The Remote Runner SDK provides a framework for building custom runners that can execute agent tasks remotely. This enables:
- Custom execution environments (e.g., Docker, VMs)
- Distributed agent execution
- Offloading resource-intensive tools

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        SDK                                │
│  ┌─────────────┐    ┌────────────────────────────────┐ │
│  │   Agent     │───▶│  RemoteRunner (abstract)        │ │
│  └─────────────┘    └────────────────────────────────┘ │
│                           │                              │
└───────────────────────────│──────────────────────────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │  Custom Runner      │
                 │  (user-defined)    │
                 └─────────────────────┘
```

---

## Runner Interface

### Base Class

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class RemoteRunner(ABC):
    """Abstract base class for remote runners."""

    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key

    @abstractmethod
    async def execute(
        self,
        messages: list[dict],
        tools: list[dict],
        options: RunnerOptions,
    ) -> AsyncIterator[StreamEvent]:
        """Execute agent task on remote runner."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if runner is healthy."""
        pass

    async def close(self) -> None:
        """Clean up resources."""
        pass
```

### Runner Options

```python
@dataclass
class RunnerOptions:
    """Options for runner execution."""

    model: str
    temperature: float = 1.0
    max_tokens: int | None = None
    stream: bool = True
```

---

## Implementation Patterns

### HTTP Runner

```python
import httpx
import json

class HTTPRunner(RemoteRunner):
    """HTTP-based remote runner."""

    async def execute(
        self,
        messages: list[dict],
        tools: list[dict],
        options: RunnerOptions,
    ) -> AsyncIterator[StreamEvent]:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/execute",
                json={
                    "messages": messages,
                    "tools": tools,
                    "options": asdict(options),
                },
                headers=self._get_headers(),
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        yield StreamEvent(**data)

    async def health_check(self) -> bool:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
            except:
                return False

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
```

### Docker Runner (Example)

```python
import docker
import asyncio

class DockerRunner(RemoteRunner):
    """Runner that executes tools in Docker containers."""

    def __init__(self, base_url: str = "http://localhost:2375"):
        super().__init__(base_url)
        self.client = docker.DockerClient(base_url)

    async def execute(self, messages, tools, options):
        # Execute tools in isolated containers
        pass

    async def health_check(self):
        try:
            self.client.ping()
            return True
        except:
            return False
```

---

## SDK Integration

### Agent with Runner

```python
class Agent:
    def __init__(
        self,
        name: str = "assistant",
        # ... existing params
        runner: RemoteRunner | None = None,
    ):
        # ... existing setup
        self.runner = runner

    async def run(self, user_input: str, ...):
        if self.runner:
            return await self._run_remote(user_input, ...)
        return await self._run_local(user_input, ...)

    async def _run_remote(self, user_input: str, ...):
        # Use runner to execute
        async for event in self.runner.execute(
            messages=self.messages,
            tools=[t.to_config() for t in self.tools],
            options=RunnerOptions(...),
        ):
            yield event

    async def stream(self, user_input: str, ...):
        if self.runner:
            return self.runner.execute_stream(user_input, ...)
        return self._stream_local(user_input, ...)
```

---

## Use Cases

1. **Tool Isolation**: Run dangerous tools in Docker containers
2. **Resource Management**: Offload heavy computations to remote servers
3. **Environment Control**: Ensure consistent tool environments
4. **Multi-Tenant Isolation**: Run each user's tools in separate environments

---

## Future Considerations

- Runner registration/discovery
- Runner pooling
- Tool caching
- Result caching
