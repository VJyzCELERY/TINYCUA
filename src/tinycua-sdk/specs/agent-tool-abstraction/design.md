# Design: SDK Agent and Tool Abstraction

## Overview

This document describes the internal architecture of `tinycua-sdk`. It translates spec
requirements into a concrete package layout, class hierarchy, sequence diagrams, and
implementation decisions for `ResponsesClient`, `Tool`/`@tool`, `Agent`, `CUAAgent`,
`AgentClient`, deploy helpers, and the `tinycua` CLI.

---

## Package Layout

```
src/tinycua-sdk/
├── pyproject.toml
└── tinycua_sdk/
    ├── __init__.py                 # re-exports: ResponsesClient, AgentClient,
    │                               #   Agent, CUAAgent, Tool, tool, AgentPolicy
    ├── clients/
    │   ├── __init__.py
    │   ├── client.py               # ResponsesClient
    │   ├── agent_client.py         # AgentClient (Mode A + Mode B)
    │   └── streaming.py            # SSE parser: parse_sse_stream()
    ├── models/
    │   ├── __init__.py             # re-exports all public types
    │   ├── request.py              # ResponseRequest, InputItem, ToolDefinition
    │   ├── response.py             # Response, OutputItem, Usage, StreamEvent, …
    │   ├── agent.py                # Agent (abstract base), AgentPolicy
    │   └── cua_agent.py            # CUAAgent
    ├── tools/
    │   ├── __init__.py             # re-exports: tool, ToolRegistry
    │   ├── decorators.py           # @tool decorator implementation
    │   ├── registry.py             # ToolRegistry
    │   └── cua/
    │       ├── __init__.py         # re-exports: BUILTIN_CUA_TOOLS
    │       ├── screenshot.py       # @tool def screenshot(...)
    │       ├── click_at.py         # @tool def click_at(...)
    │       ├── type_text.py        # @tool def type_text(...)
    │       ├── hotkey.py           # @tool def hotkey(...)
    │       └── find_element.py     # @tool def find_element(...)
    ├── deploy/
    │   ├── __init__.py             # re-exports nothing (internal only)
    │   └── _core.py                # _deploy_bundle(bundle, client) — internal helper
    ├── cli/
    │   ├── __init__.py
    │   ├── main.py                 # entry point: tinycua_main()
    │   ├── repl.py                 # interactive REPL (prompt_toolkit + rich)
    │   ├── commands.py             # non-interactive: run, deploy sub-commands
    │   └── config.py               # ~/.tinycua/config.yaml read/write
    └── utils/
        ├── __init__.py
        └── schema.py               # fn_to_json_schema() — pydantic-based helper
```

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                            tinycua-sdk                              │
│                                                                     │
│  Developer Code                                                     │
│      │                                                              │
│      │  @tool / @tool(dependencies=[…])                             │
│      ├──────────────────► Tool                                      │
│      │                      .to_config()  → tools[] descriptor      │
│      │                      .to_bundle()  → descriptor + source     │
│      │                      .deploy(client) → Runner registration   │
│      │                                                              │
│      │  Agent(tools=[…]) / CUAAgent(tools=[…])                      │
│      │    agent.deploy(client) → deploys user tools only            │
│      │                                                              │
│      │  AgentClient.run(agent, input)                               │
│      │    Mode A: local loop → tool.invoke(**args)                  │
│      │    Mode B: single POST /v1/responses (session_id set)        │
│      ▼                                                              │
│  AgentClient                                                        │
│      │  builds ResponseRequest                                      │
│      ▼                                                              │
│  ResponsesClient                                                    │
│      │  POST /v1/responses                                          │
│      │  SSE parsing (streaming.py)                                  │
│      │  retry + back-off                                            │
│      ▼                                                              │
│  tinycua-backend  (or any OpenAI Responses-compatible endpoint)     │
│                                                                     │
│  deploy/_core.py                                                    │
│      │  POST /internal/v1/tools  (bundle)                          │
│      ▼                                                              │
│  tinycua-runner (via backend proxy)                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Class Designs

### `models/tool.py` — Tool

```python
from __future__ import annotations
import inspect
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON Schema object
    _fn: Callable | None = field(default=None, repr=False)
    _source: str | None = field(default=None, repr=False)
    _dependencies: list[str] = field(default_factory=list, repr=False)
    _is_builtin: bool = field(default=False, repr=False)

    # ── Local execution ──────────────────────────────────────────────

    def invoke(self, **kwargs) -> object:
        """Call the underlying Python function directly (Mode A / testing)."""
        if self._fn is None:
            raise RuntimeError(
                f"Tool '{self.name}' has no local function (_fn is None). "
                "Did you reconstruct this tool with from_config()?"
            )
        return self._fn(**kwargs)

    # ── Serialisation ────────────────────────────────────────────────

    def to_config(self) -> dict:
        """
        Return the tool descriptor for the tools[] array in POST /v1/responses.
        Contains name, description, parameters only — no source code.
        """
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": False,
        }

    def to_bundle(self) -> dict:
        """
        Return the full deployment bundle: descriptor + source + dependencies.
        Sent to POST /internal/v1/tools during deploy().
        """
        if self._source is None:
            raise RuntimeError(
                f"Tool '{self.name}' has no source code. "
                "Only @tool-decorated functions can be deployed."
            )
        return {
            **self.to_config(),
            "source": self._source,
            "dependencies": self._dependencies,
        }

    @classmethod
    def from_config(cls, d: dict) -> "Tool":
        """
        Reconstruct a Tool from a descriptor dict (no _fn, no source).
        Used by the Runner after materialising the function from source.
        """
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            parameters=d.get("parameters", {}),
        )

    # ── Deployment ───────────────────────────────────────────────────

    def deploy(self, client: "ResponsesClient") -> None:
        """
        Register this tool with the Runner via POST /internal/v1/tools.
        Idempotent: no-op if schema unchanged; warns and re-registers if changed.
        Must not be called on built-in tools (_is_builtin=True).
        """
        from tinycua_sdk.deploy._core import _deploy_bundle
        if self._is_builtin:
            raise RuntimeError(
                f"Tool '{self.name}' is a built-in tool and cannot be manually deployed."
            )
        _deploy_bundle(self.to_bundle(), client)
```

### `tools/decorators.py` — @tool decorator

```python
import inspect
from tinycua_sdk.models.tool import Tool
from tinycua_sdk.utils.schema import fn_to_json_schema

def tool(_fn=None, *, dependencies: list[str] | None = None):
    """
    Convert a Python function into a Tool instance.

    Supports two call forms:
        @tool                              # zero dependencies
        @tool(dependencies=["requests"])   # with dependencies

    The decorated name is replaced by the Tool object.
    The original function is still callable via tool.invoke(**kwargs).
    """
    def _make_tool(fn) -> Tool:
        return Tool(
            name=fn.__name__,
            description=inspect.getdoc(fn) or "",
            parameters=fn_to_json_schema(fn),
            _fn=fn,
            _source=inspect.getsource(fn),
            _dependencies=list(dependencies or []),
        )

    if _fn is not None:
        # Called as @tool with no parentheses
        return _make_tool(_fn)
    # Called as @tool(dependencies=[…])
    return _make_tool
```

### `utils/schema.py` — Schema Derivation

```python
import inspect
from typing import Callable
from pydantic import create_model
from pydantic.fields import FieldInfo

def fn_to_json_schema(fn: Callable) -> dict:
    """
    Derive a JSON Schema 'object' from a function's type annotations.
    Uses pydantic to handle complex types (Optional, list, nested models).

    Steps:
    1. Inspect fn.__annotations__ (excluding 'return').
    2. Build a temporary pydantic model with those fields.
    3. Return { "type": "object", "properties": …, "required": […] }.
    """
    sig = inspect.signature(fn)
    fields: dict = {}
    for pname, param in sig.parameters.items():
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else object
        default = param.default if param.default is not inspect.Parameter.empty else ...
        fields[pname] = (annotation, FieldInfo(default=default))

    Model = create_model(f"_{fn.__name__}_schema", **fields)
    schema = Model.model_json_schema()
    return {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }
```

### Schema Derivation — Type Annotation Coverage

| Python type                | JSON Schema type         |
|----------------------------|--------------------------|
| `str`                      | `"string"`               |
| `int`                      | `"integer"`              |
| `float`                    | `"number"`               |
| `bool`                     | `"boolean"`              |
| `list[T]`                  | `"array"` with `items`   |
| `dict`                     | `"object"`               |
| `Optional[T]` / `T | None` | `anyOf: [T, null]`       |
| Pydantic `BaseModel`       | nested `"object"`        |

### `models/agent.py` — Agent (abstract base)

```python
from __future__ import annotations
import yaml
from abc import ABC
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tinycua_sdk.models.tool import Tool
    from tinycua_sdk.clients.client import ResponsesClient

@dataclass
class AgentPolicy:
    max_tool_calls: int = 10
    parallel_tool_calls: bool = True
    temperature: float = 1.0

class Agent(ABC):
    """
    Abstract base class for all TINYCUA agents.

    Domain-neutral: no preset instructions, no preset tools.

    Subclasses may override hook methods to implement:
      - context retrieval     (_build_context)
      - prompt/token pruning  (_prune_messages)
      - turn lifecycle        (_before_turn, _after_turn)

    All hooks are no-ops in this base class. They will be fleshed out once
    the architectural paper is delivered.
    """

    def __init__(
        self,
        name: str,
        instructions: str,
        tools: list["Tool"],
        model: str,
        policy: AgentPolicy | None = None,
    ) -> None:
        self.name = name
        self.instructions = instructions
        self.tools = list(tools)
        self.model = model
        self.policy = policy or AgentPolicy()

    # ── Lifecycle hooks (no-ops) ──────────────────────────────────────

    def _before_turn(self) -> None:
        """Called before each LLM turn. Override to prepare state."""

    def _after_turn(self) -> None:
        """Called after each LLM turn. Override to post-process state."""

    def _build_context(self) -> list[dict]:
        """
        Return additional context items to prepend to the input array.
        Override to inject memory / RAG results / session summaries.
        Returns empty list in base implementation.
        """
        return []

    def _prune_messages(self, messages: list[dict]) -> list[dict]:
        """
        Reduce the message list to fit within the model's context window.
        Override to implement summarisation or sliding-window truncation.
        Returns messages unchanged in base implementation.
        """
        return messages

    # ── Deployment ───────────────────────────────────────────────────

    def deploy(self, client: "ResponsesClient") -> None:
        """
        Deploy all user-added tools to the Runner.
        Built-in tools (_is_builtin=True) are skipped.
        """
        for t in self.tools:
            if not getattr(t, "_is_builtin", False):
                t.deploy(client)

    # ── Serialisation ────────────────────────────────────────────────

    def to_config(self) -> dict:
        return {
            "name": self.name,
            "instructions": self.instructions,
            "model": self.model,
            "tools": [t.to_config() for t in self.tools],
            "policy": {
                "max_tool_calls": self.policy.max_tool_calls,
                "parallel_tool_calls": self.policy.parallel_tool_calls,
                "temperature": self.policy.temperature,
            },
        }

    @classmethod
    def from_config(cls, d: dict) -> "Agent":
        from tinycua_sdk.models.tool import Tool
        return cls(
            name=d["name"],
            instructions=d["instructions"],
            tools=[Tool.from_config(t) for t in d.get("tools", [])],
            model=d["model"],
            policy=AgentPolicy(**d.get("policy", {})),
        )

    def to_yaml(self) -> str:
        return yaml.dump(self.to_config(), sort_keys=False)

    @classmethod
    def from_yaml(cls, s: str) -> "Agent":
        return cls.from_config(yaml.safe_load(s))
```

### `models/cua_agent.py` — CUAAgent

```python
from __future__ import annotations
from typing import ClassVar
from tinycua_sdk.models.agent import Agent, AgentPolicy
from tinycua_sdk.models.tool import Tool

class CUAAgent(Agent):
    """
    A Computer Use Agent with pre-built tools for screen interaction.

    Built-in tools (screenshot, click_at, type_text, hotkey, find_element)
    are loaded from tinycua_sdk.tools.cua and marked with _is_builtin=True.
    They are present in the Runner at startup and are never re-deployed.

    Usage:
        agent = CUAAgent(
            name="desktop-agent",
            tools=[my_custom_tool],          # merged with built-ins
            append_instructions="...",
            model="tinycua-gguf-7b",
        )
        agent.deploy(client)   # deploys my_custom_tool only
    """

    _BUILTIN_TOOLS: ClassVar[list[Tool]]
    _BASE_INSTRUCTIONS: ClassVar[str] = (
        "You are a computer use agent. You can take screenshots, click, type, "
        "send hotkeys, and find UI elements on the screen. "
        "Complete the user's task by interacting with the desktop."
    )

    def __init__(
        self,
        name: str,
        tools: list[Tool] | None = None,
        append_instructions: str = "",
        override_builtin_tools: list[Tool] | None = None,
        model: str = "",
        policy: AgentPolicy | None = None,
    ) -> None:
        from tinycua_sdk.tools.cua import BUILTIN_CUA_TOOLS

        # Lazily populate the class-level constant
        if not hasattr(CUAAgent, "_BUILTIN_TOOLS") or CUAAgent._BUILTIN_TOOLS is None:
            CUAAgent._BUILTIN_TOOLS = BUILTIN_CUA_TOOLS

        active_builtins = override_builtin_tools if override_builtin_tools is not None \
            else CUAAgent._BUILTIN_TOOLS

        instructions = CUAAgent._BASE_INSTRUCTIONS
        if append_instructions:
            instructions = f"{instructions}\n\n{append_instructions}"

        merged_tools = list(active_builtins) + list(tools or [])
        super().__init__(
            name=name,
            instructions=instructions,
            tools=merged_tools,
            model=model,
            policy=policy,
        )
```

### `tools/cua/__init__.py` — Built-in CUA tools

```python
from tinycua_sdk.tools.cua.screenshot import screenshot
from tinycua_sdk.tools.cua.click_at import click_at
from tinycua_sdk.tools.cua.type_text import type_text
from tinycua_sdk.tools.cua.hotkey import hotkey
from tinycua_sdk.tools.cua.find_element import find_element

BUILTIN_CUA_TOOLS = [screenshot, click_at, type_text, hotkey, find_element]

# Mark all built-in tools
for _t in BUILTIN_CUA_TOOLS:
    object.__setattr__(_t, "_is_builtin", True)
```

Each built-in tool file follows the same pattern:

```python
# tools/cua/screenshot.py
from tinycua_sdk.tools.decorators import tool

@tool
def screenshot() -> dict:
    """Capture the current screen and return it as a base64-encoded PNG."""
    import base64, mss
    with mss.mss() as sct:
        img = sct.shot(output="/tmp/_tinycua_screenshot.png")
    with open(img, "rb") as f:
        return {"image_b64": base64.b64encode(f.read()).decode()}
```

### `clients/client.py` — ResponsesClient

```python
import os, uuid, time
from typing import Iterator
import httpx
from tinycua_sdk.models.request import ResponseRequest
from tinycua_sdk.models.response import Response, StreamEvent
from tinycua_sdk.clients.streaming import parse_sse_stream

_DEFAULT_MAX_RETRIES = 3
_RETRY_STATUS_CODES = {500, 502, 503, 504}

class ResponsesClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = (base_url or os.environ["TINYCUA_API_URL"]).rstrip("/")
        self._api_key = api_key or os.environ["TINYCUA_API_KEY"]
        self._max_retries = max_retries
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "X-Trace-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }

    def create(self, request: ResponseRequest) -> Response:
        """Blocking non-streaming call. Retries on transient 5xx."""
        payload = _to_dict(request, stream=False)
        last_exc = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = httpx.post(
                    f"{self.base_url}/v1/responses",
                    json=payload,
                    headers=self._headers(),
                    timeout=self._timeout,
                )
                if resp.status_code not in _RETRY_STATUS_CODES:
                    resp.raise_for_status()
                    return Response(**resp.json())
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
            if attempt < self._max_retries:
                time.sleep(2 ** attempt + _jitter())
        raise last_exc or RuntimeError("Max retries exceeded")

    def stream(self, request: ResponseRequest) -> Iterator[StreamEvent]:
        """Streaming SSE call — yields StreamEvent objects."""
        payload = _to_dict(request, stream=True)
        with httpx.stream(
            "POST",
            f"{self.base_url}/v1/responses",
            json=payload,
            headers=self._headers(),
            timeout=self._timeout,
        ) as resp:
            resp.raise_for_status()
            yield from parse_sse_stream(resp.iter_lines())
```

### `clients/streaming.py` — SSE Parser

```python
import json
from typing import Iterable, Iterator
from tinycua_sdk.models.response import StreamEvent

def parse_sse_stream(lines: Iterable[str]) -> Iterator[StreamEvent]:
    """
    Parse raw SSE line stream into StreamEvent objects.
    Stops on 'data: [DONE]'.
    """
    event_type = ""
    data_buf: list[str] = []
    for line in lines:
        line = line.rstrip("\n")
        if line.startswith("event:"):
            event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            raw = line[len("data:"):].strip()
            if raw == "[DONE]":
                return
            data_buf.append(raw)
        elif line == "" and data_buf:
            data = json.loads("".join(data_buf))
            yield StreamEvent(type=event_type or data.get("type", ""), **data)
            event_type = ""
            data_buf = []
```

### `clients/agent_client.py` — AgentClient

```python
import json
from typing import Iterator
from tinycua_sdk.clients.client import ResponsesClient
from tinycua_sdk.models.agent import Agent
from tinycua_sdk.models.request import ResponseRequest
from tinycua_sdk.models.response import Response, StreamEvent

class AgentClient:
    """
    High-level client that drives an agent through one or more LLM turns.

    Mode A (default, server_orchestrated=False):
      Runs the function-calling loop locally. Tools are invoked in-process
      via tool.invoke(**args). Suitable for local development and testing.
      No session_id required.

    Mode B (server_orchestrated=True or session_id provided):
      Sends a single POST /v1/responses with session_id.
      Backend owns the orchestration loop and tool execution.
      Tools must be deployed to the Runner beforehand.
    """

    def __init__(
        self,
        client: ResponsesClient,
        server_orchestrated: bool = False,
    ) -> None:
        self._client = client
        self._server_orchestrated = server_orchestrated

    def run(
        self,
        agent: Agent,
        user_input: str,
        session_id: str | None = None,
    ) -> Response:
        if session_id or self._server_orchestrated:
            return self._run_mode_b(agent, user_input, session_id)
        return self._run_mode_a(agent, user_input)

    def stream(
        self,
        agent: Agent,
        user_input: str,
        session_id: str | None = None,
    ) -> Iterator[StreamEvent]:
        if session_id or self._server_orchestrated:
            yield from self._stream_mode_b(agent, user_input, session_id)
        else:
            yield from self._stream_mode_a(agent, user_input)

    # ── Mode A: local loop ────────────────────────────────────────────

    def _run_mode_a(self, agent: Agent, user_input: str) -> Response:
        registry = _build_registry(agent.tools)
        input_items = _build_input(agent, user_input)
        tool_calls_used = 0

        while True:
            agent._before_turn()
            request = _build_request(agent, input_items)
            response = self._client.create(request)
            agent._after_turn()

            func_calls = [i for i in response.output if i.get("type") == "function_call"]
            if not func_calls:
                return response

            if tool_calls_used + len(func_calls) > agent.policy.max_tool_calls:
                response["status"] = "incomplete"
                return response

            for call in func_calls:
                args = json.loads(call["arguments"])
                result = registry[call["name"]].invoke(**args)
                input_items.append({
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": json.dumps(result) if not isinstance(result, str) else result,
                })
            tool_calls_used += len(func_calls)

    def _stream_mode_a(self, agent: Agent, user_input: str) -> Iterator[StreamEvent]:
        registry = _build_registry(agent.tools)
        input_items = _build_input(agent, user_input)
        tool_calls_used = 0

        while True:
            agent._before_turn()
            request = _build_request(agent, input_items, stream=True)
            func_calls_buffer: list[dict] = []
            for event in self._client.stream(request):
                yield event
                _collect_function_calls(event, func_calls_buffer)
            agent._after_turn()

            if not func_calls_buffer:
                return
            if tool_calls_used + len(func_calls_buffer) > agent.policy.max_tool_calls:
                return

            for call in func_calls_buffer:
                args = json.loads(call["arguments"])
                result = registry[call["name"]].invoke(**args)
                input_items.append({
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": json.dumps(result) if not isinstance(result, str) else result,
                })
            tool_calls_used += len(func_calls_buffer)

    # ── Mode B: server orchestrated ───────────────────────────────────

    def _run_mode_b(
        self, agent: Agent, user_input: str, session_id: str | None
    ) -> Response:
        request = _build_request(agent, _build_input(agent, user_input))
        if session_id:
            request.session_id = session_id
        return self._client.create(request)

    def _stream_mode_b(
        self, agent: Agent, user_input: str, session_id: str | None
    ) -> Iterator[StreamEvent]:
        request = _build_request(agent, _build_input(agent, user_input), stream=True)
        if session_id:
            request.session_id = session_id
        yield from self._client.stream(request)
```

---

## Data-Flow: AgentClient.run() — Mode A

```
Developer
  │
  │  agent_client.run(agent, "What's the weather in NYC?")
  ▼
AgentClient._run_mode_a()
  │  agent._before_turn()
  │  build ResponseRequest (tools descriptors via to_config(), instructions, input items)
  ▼
ResponsesClient.create(request)
  │  POST /v1/responses  →  Backend  →  LLM
  ▼
Response { output: [ { type: "function_call", name: "get_weather", … } ] }
  │
  │  func_calls found → invoke locally
  │  registry["get_weather"].invoke(location="NYC")
  │      → calls get_weather(location="NYC")  →  { temp: 72, … }
  │
  │  agent._after_turn()
  │  inject function_call_output → loop back
  ▼
ResponsesClient.create(request)   ← second call
  │  POST /v1/responses  →  Backend  →  LLM
  ▼
Response { output: [ { type: "message", content: "It's 72°F…" } ] }
  │  no func_calls → return Response
  ▼
Developer receives final Response
```

## Data-Flow: AgentClient.run() — Mode B

```
Developer
  │
  │  agent_client.run(agent, user_input, session_id="sess_abc")
  ▼
AgentClient._run_mode_b()
  │  build single ResponseRequest with session_id field
  ▼
ResponsesClient.create(request)
  │  POST /v1/responses { …, session_id: "sess_abc" }
  ▼
Backend (owns full orchestration loop + tool execution + history)
  ▼
Response (final, after all tool calls resolved server-side)
  ▼
Developer receives final Response — only one HTTP call made
```

---

## `deploy/_core.py` — Internal Deploy Helper

```python
import httpx
import warnings

def _deploy_bundle(bundle: dict, client) -> None:
    """
    POST bundle to POST /internal/v1/tools.
    409 → warn + re-register (DELETE then POST).
    200/201 → no-op.
    Other errors → raise.
    """
    headers = {"Authorization": f"Bearer {client._api_key}"}
    base = client.base_url

    resp = httpx.post(f"{base}/internal/v1/tools", json=bundle, headers=headers)

    if resp.status_code == 409:
        warnings.warn(
            f"Tool '{bundle['name']}' already exists with a different schema. "
            "Re-registering.",
            stacklevel=4,
        )
        httpx.delete(
            f"{base}/internal/v1/tools/{bundle['name']}",
            headers=headers,
        ).raise_for_status()
        httpx.post(
            f"{base}/internal/v1/tools",
            json=bundle,
            headers=headers,
        ).raise_for_status()
    elif resp.status_code not in (200, 201):
        resp.raise_for_status()
```

---

## `models/request.py` and `models/response.py`

### Key request types

```python
from dataclasses import dataclass, field

@dataclass
class InputItem:
    role: str                       # "user" | "assistant" | "system" | "tool"
    content: str | list
    type: str | None = None         # "function_call_output" for tool results
    call_id: str | None = None

@dataclass
class ResponseRequest:
    model: str
    input: list[InputItem | dict]
    tools: list[dict] = field(default_factory=list)
    stream: bool = False
    temperature: float | None = None
    max_output_tokens: int | None = None
    tool_choice: str | dict = "auto"
    parallel_tool_calls: bool = True
    instructions: str | None = None
    session_id: str | None = None       # Mode B: backend loads + saves history
    metadata: dict = field(default_factory=dict)
```

### Key response types

```python
@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

@dataclass
class StreamEvent:
    type: str                   # e.g. "response.output_text.delta"
    delta: str | None = None
    response: dict | None = None
    output_index: int | None = None
    item: dict | None = None

@dataclass
class Response:
    id: str
    object: str                 # "response"
    created_at: int
    status: str                 # "completed" | "incomplete" | "in_progress"
    model: str
    output: list[dict]
    usage: Usage | None = None
    incomplete_details: dict | None = None
    error: dict | None = None
    metadata: dict = field(default_factory=dict)
```

---

## CLI Design

### Entry point

`pyproject.toml`:
```toml
[project.scripts]
tinycua = "tinycua_sdk.cli.main:tinycua_main"
```

### `cli/main.py`

```python
import sys
import click

@click.group(invoke_without_command=True)
@click.pass_context
def tinycua_main(ctx):
    """TINYCUA — Computer Use Agent SDK CLI."""
    if ctx.invoked_subcommand is None:
        from tinycua_sdk.cli.repl import start_repl
        start_repl()

@tinycua_main.command()
@click.argument("file", type=click.Path(exists=True))
def run(file: str):
    """Execute a Python script using the SDK."""
    ...

@tinycua_main.command()
@click.argument("file", type=click.Path(exists=True))
def deploy(file: str):
    """Deploy all @tool-decorated functions from a Python file."""
    ...
```

### `cli/repl.py` — Interactive REPL structure

```python
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console

COMMANDS = {
    "/help":    cmd_help,
    "/connect": cmd_connect,
    "/status":  cmd_status,
    "/agents":  cmd_agents,
    "/run":     cmd_run,
    "/chat":    cmd_chat,
    "/deploy":  cmd_deploy,
    "/quit":    cmd_quit,
}

def start_repl():
    console = Console()
    session = PromptSession(history=FileHistory("~/.tinycua/history"))
    config = load_config()       # from ~/.tinycua/config.yaml
    state = ReplState(config)

    console.print("[bold]TINYCUA[/bold]  Type /help for commands.")
    while True:
        try:
            line = session.prompt("> ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not line:
            continue
        cmd, *args = line.split(None, 1)
        handler = COMMANDS.get(cmd)
        if handler:
            handler(state, console, args[0] if args else "")
        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
```

### `cli/config.py` — Persistent config

```python
# Location: ~/.tinycua/config.yaml
# Shape:
#   base_url: http://localhost:8000
#   api_key: sk-…

import yaml
from pathlib import Path

CONFIG_PATH = Path.home() / ".tinycua" / "config.yaml"

def load_config() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return {}

def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(cfg, sort_keys=False))
```

---

## Retry Strategy

`ResponsesClient` uses exponential back-off with jitter:

```
attempt 0: immediate
attempt 1: sleep 1s + jitter(0–0.5s)
attempt 2: sleep 2s + jitter(0–0.5s)
attempt 3: sleep 4s + jitter(0–0.5s)
(max_retries=3 default, configurable in constructor)
```

Retried on: `500`, `502`, `503`, `504`, `httpx.TimeoutException`,
`httpx.NetworkError`.

Not retried on: `4xx` (client errors).

---

## Phases

### Phase 1 (MVP)

- `ResponsesClient.create()` (blocking) and `.stream()` (SSE generator).
- `@tool` / `@tool(dependencies=[])` decorator with pydantic schema derivation.
- `Tool.to_config()`, `to_bundle()`, `from_config()`, `deploy()`.
- `Agent` abstract base with hook placeholders and serialisation.
- `CUAAgent` with 5 built-in tools.
- `AgentClient.run()` and `.stream()` — both Mode A and Mode B.
- `deploy/_core.py` internal helper.
- `tinycua` CLI: REPL, `run`, `deploy` sub-commands.
- `X-Trace-Id` header on every request.
- Retry with exponential back-off.

### Phase 2

- `AgentMemory` interface + `InMemoryMemory` and `PersistentMemory` implementations.
- Async variants: `AsyncResponsesClient`, `AsyncAgentClient`.
- Structured output support (`response_format`).
- `Agent._build_context()` and `_prune_messages()` implementations (once paper MD arrives).
- Additional CUA tools (browser automation, file system operations).

---

## Open Questions Resolved

- **OQ-001** (Schema derivation library): `pydantic` chosen.
- **OQ-002** (Hook methods): Named explicitly as no-ops (`_before_turn`, `_after_turn`,
  `_build_context`, `_prune_messages`). Implementations deferred to Phase 2.
- **OQ-003** (`to_yaml()` library): PyYAML for MVP.
