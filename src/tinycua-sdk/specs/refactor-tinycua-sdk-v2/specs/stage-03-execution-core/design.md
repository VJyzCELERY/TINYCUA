# Stage 3: LLM Client & Basic Execution Loop — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-03-execution-core/spec.md`

## New Files

### `tinycua_sdk/agent/llm_client.py`

```python
"""LLM client ABC and OpenAI-compatible implementation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from tinycua_sdk.agent.llm_model import LanguageModel


class LLMClient(ABC):
    """Abstract base for LLM API clients."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
    ) -> dict[str, Any]:
        """Send chat request and return normalized response.

        Returns:
            {
                "content": str | None,
                "tool_calls": list[dict] | None,
                "usage": dict | None,
            }
        """


class OpenAICompatibleClient(LLMClient):
    """Client for OpenAI-compatible endpoints."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self, model_config: LanguageModel) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Authorization": f"Bearer {model_config.api_key.get_secret_value()}"}
            base_url = model_config.base_url or "https://api.openai.com/v1"
            self._client = httpx.AsyncClient(
                base_url=base_url,
                headers=headers,
                timeout=60.0,
            )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
    ) -> dict[str, Any]:
        client = self._get_client(model_config)

        payload: dict[str, Any] = {
            "model": model_config.model_name,
            "messages": messages,
        }

        # Forward optional params
        for field in (
            "temperature", "max_tokens", "top_p", "frequency_penalty",
            "presence_penalty", "stop", "seed", "response_format",
            "tool_choice", "logprobs", "top_logprobs", "user",
        ):
            value = getattr(model_config, field)
            if value is not None:
                payload[field] = value

        if tools:
            payload["tools"] = tools
            if "tool_choice" not in payload:
                payload["tool_choice"] = "auto"

        response = await client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]
        message = choice["message"]

        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = [
                {
                    "id": tc["id"],
                    "type": tc["type"],
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in message["tool_calls"]
            ]

        return {
            "content": message.get("content"),
            "tool_calls": tool_calls,
            "usage": data.get("usage"),
        }
```

### `tinycua_sdk/agent/executor.py`

```python
"""Agent executor with tool execution."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from tinycua_sdk.agent.config import AgentConfig
from tinycua_sdk.agent.llm_client import LLMClient, OpenAICompatibleClient
from tinycua_sdk.tools.decorators import Tool


class ToolExecutor:
    """Canonical tool execution path with permission and approval checks."""

    @staticmethod
    async def execute(tool: Tool, arguments: dict, agent: Agent) -> Any:
        # Permission check
        permission = agent.tool_permissions.get(tool.name, "allow")
        if permission == "deny":
            return {"error": f"Tool '{tool.name}' is denied by permission map."}

        # Approval check
        if permission == "ask" and agent.approval_workflow:
            approval = await agent.approval_workflow.request_approval(tool.name, arguments)
            if not approval.get("approved"):
                return approval

        # Execute
        return tool.invoke(**arguments)


class AgentExecutor:
    """Base executor with config storage and LLM client management."""

    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self._cancelled = False
        self._llm_client: LLMClient | None = None

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True

    def _get_llm_client(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = OpenAICompatibleClient()
        return self._llm_client

    async def _call_llm(
        self,
        messages: list[dict],
        tools: list[Tool] | None = None,
    ) -> dict[str, Any]:
        client = self._get_llm_client()
        tool_schemas = [t.to_config() for t in tools] if tools else None
        return await client.chat(messages, tool_schemas, self.config.llm_model)

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        # Implemented by Agent (subclass)
        raise NotImplementedError
```

### `tinycua_sdk/agent/loop.py`

```python
"""Agent execution loop."""
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from tinycua_sdk.agent.executor import ToolExecutor

if TYPE_CHECKING:
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool


class BaseLoop:
    """Standard tool-calling execution loop."""

    def __init__(self, max_iterations: int = 5) -> None:
        self.max_iterations = max_iterations

    def _build_system_message(self, agent: Agent, override_instructions: str | None = None) -> dict:
        parts = []
        instructions = override_instructions or agent.instructions
        if instructions:
            parts.append(instructions)
        for skill in agent.skills:
            parts.append(f"[{skill.name}]\n{skill.instructions}")
        return {"role": "system", "content": "\n\n".join(parts)}

    async def run(self, agent: Agent, messages: list[dict], tools: list[Tool]) -> str:
        system_msg = self._build_system_message(agent)
        messages = [system_msg] + messages

        tool_call_count = 0

        for _ in range(self.max_iterations):
            if agent.is_cancelled:
                raise asyncio.CancelledError()

            if tool_call_count >= agent.policy.max_tool_calls:
                break

            response = await agent._call_llm(messages, tools)

            # Append assistant message
            assistant_msg = {"role": "assistant", "content": response.get("content") or ""}
            if response.get("tool_calls"):
                assistant_msg["tool_calls"] = response["tool_calls"]
            messages.append(assistant_msg)

            # Handle tool calls
            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    tool_name = tc["function"]["name"]
                    arguments = json.loads(tc["function"]["arguments"])

                    tool = next((t for t in tools if t.name == tool_name), None)
                    if tool is None:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    else:
                        result = await ToolExecutor.execute(tool, arguments, agent)
                        tool_call_count += 1

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tool_name,
                        "content": str(result),
                    })
            else:
                # No tool calls — return final content
                return response.get("content") or ""

        return messages[-1].get("content") or "[max iterations reached]"
```

### `tinycua_sdk/security/approval.py`

```python
"""Approval workflow for tool execution guardrails."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ApprovalWorkflow(ABC):
    """Abstract base for approval workflows."""

    @abstractmethod
    async def request_approval(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Request approval for a tool call.

        Must return {"approved": bool, ...}.
        """


class DefaultApprovalWorkflow(ApprovalWorkflow):
    """Always approves."""

    async def request_approval(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"approved": True}
```

### `tinycua_sdk/agent/agent.py` (run method addition)

```python
class Agent(AgentExecutor):
    # ... constructor from Stage 2 ...

    async def run(
        self,
        query: str,
        messages: list[dict] | None = None,
        instructions: str | None = None,
        stream: Literal["off", "event", "token", "all"] = "off",
    ) -> str:
        if stream != "off":
            raise NotImplementedError("Streaming implemented in Stage 5")

        loop = self.config.loop or BaseLoop()

        # Build message list
        msgs = (messages or []) + [{"role": "user", "content": query}]

        # Override instructions for this run only
        if instructions:
            # Inject override into first system message in loop
            # The loop's _build_system_message handles this
            loop._override_instructions = instructions  # type: ignore

        return await loop.run(self, msgs, self.tools)
```

**Note:** The instruction override needs a cleaner design. Options:
1. Pass override to `loop.run()` as a parameter.
2. Store override temporarily on the agent and clear after run.

Preferred: Option 1 — add `override_instructions` parameter to `BaseLoop.run()`.

### Updated `BaseLoop.run()` signature:
```python
async def run(
    self,
    agent: Agent,
    messages: list[dict],
    tools: list[Tool],
    override_instructions: str | None = None,
) -> str:
    system_msg = self._build_system_message(agent, override_instructions)
    ...
```

### Updated `Agent.run()`:
```python
async def run(self, query, messages=None, instructions=None, stream: bool = False):
    loop = self.config.loop or BaseLoop()
    msgs = (messages or []) + [{"role": "user", "content": query}]
    return await loop.run(self, msgs, self.tools, instructions, stream=stream)
```

## Data Flow

```
Agent.run("What is 2+2?")
    │
    ▼
BaseLoop.run(agent, messages, tools)
    │
    ├──► _build_system_message() ──► system prompt + skill instructions
    │
    ├──► agent._call_llm(messages, tools)
    │       │
    │       ├──► OpenAICompatibleClient.chat()
    │       │       ├──► httpx POST /chat/completions
    │       │       └──► normalized response dict
    │       │
    │       └──► {content, tool_calls, usage}
    │
    ├──► If tool_calls:
    │       ├──► Parse JSON arguments
    │       ├──► ToolExecutor.execute(tool, args, agent)
    │       │       ├──► Check tool_permissions
    │       │       ├──► Check ApprovalWorkflow (if ask)
    │       │       └──► tool.invoke(**args)
    │       └──► Append result to messages
    │       Loop continues
    │
    └──► If no tool_calls:
            Return content string
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Tool not found | Append `{"error": "Unknown tool: X"}` to messages |
| Tool invoke fails | Exception caught, error message appended to tool result for LLM recovery |
| LLM request fails | `httpx.HTTPStatusError` propagates |
| Cancelled | `asyncio.CancelledError` raised |
| Max tool calls reached | Return last content with `[max iterations reached]` hint |
| Streaming requested in Stage 3 | `NotImplementedError` |

## Testing Strategy

- Mock `httpx.AsyncClient.post` to return fake OpenAI responses.
- Test tool-calling loop with mock LLM responses that include `tool_calls`.
- Test cancellation by cancelling the task mid-run.
- Test permission checks with mock `ApprovalWorkflow`.
