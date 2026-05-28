# Design: Backend ↔ Runner Integration (Internal API)

## Overview

This document describes the internal architecture of `tinycua-runner` and the
backend-to-Runner communication layer. It translates spec requirements into concrete
module structure, class hierarchies, sequence diagrams, and implementation decisions.

Key architectural decision: the Runner depends on `tinycua-sdk`. Tool execution is
`tool.invoke(**args)` — no separate executor class hierarchy exists. The Runner's job is
HTTP routing, AST security checking, function materialisation, and subprocess sandboxing.

---

## Package Layout

### `tinycua-runner`

```
src/tinycua-runner/
├── pyproject.toml
└── tinycua_runner/
    ├── __init__.py
    ├── main.py                      # FastAPI application factory (create_app())
    ├── config.py                    # Settings (pydantic BaseSettings)
    ├── startup.py                   # load_builtin_tools() called at app startup
    ├── auth/
    │   ├── __init__.py
    │   └── middleware.py            # ServiceTokenMiddleware
    ├── models/
    │   ├── __init__.py
    │   ├── tool.py                  # RegisteredTool, ToolBundle
    │   ├── toolcall.py              # ToolCallRequest, ToolCallResponse, ToolCallResult
    │   └── errors.py                # ToolNotFoundError, DuplicateToolError, etc.
    ├── registry/
    │   ├── __init__.py
    │   └── tool_registry.py         # ToolRegistry (in-memory, thread-safe)
    ├── security/
    │   ├── __init__.py
    │   └── ast_check.py             # ASTChecker — static source analysis
    ├── sandbox/
    │   ├── __init__.py
    │   └── executor.py              # SandboxedExecutor — subprocess + resource limits
    ├── routes/
    │   ├── __init__.py
    │   ├── tools.py                 # POST/GET/DELETE /internal/v1/tools
    │   ├── toolcall.py              # POST /internal/v1/toolcall
    │   └── health.py                # GET /internal/health
    └── logging/
        ├── __init__.py
        └── structured.py            # JSON log formatter, argument hashing
```

### `tinycua-backend` additions (RunnerClient)

```
tinycua_backend/
└── runner/
    ├── __init__.py
    └── client.py      # RunnerClient — HTTP client for Runner's internal API
```

---

## Component Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                          tinycua-runner                              │
│                                                                      │
│  ServiceTokenMiddleware ──► POST /internal/v1/tools  (register)      │
│                        ──► GET /internal/v1/tools   (list)           │
│                        ──► DELETE /internal/v1/tools/{name}          │
│                        ──► POST /internal/v1/toolcall                │
│                        ──► GET /internal/health                      │
│                                      │                               │
│               ┌──────────────────────▼──────────────────────┐        │
│               │             ToolCallRoute                    │        │
│               │  registry.get(tool_name)                    │        │
│               │  if builtin → tool.invoke() directly        │        │
│               │  else       → SandboxedExecutor.run()       │        │
│               └──────────────────────┬──────────────────────┘        │
│                                      │                               │
│          ┌───────────────────────────┼──────────────────┐            │
│          ▼                           ▼                  ▼            │
│   ToolRegistry              SandboxedExecutor      tinycua_sdk       │
│   (in-memory)               (subprocess +          tool.invoke()     │
│                              resource limits)                        │
│                                      │                               │
│                          ┌───────────▼────────────┐                  │
│               ┌──────────┤  Startup               │                  │
│               │          │  load_builtin_tools()  │                  │
│               │          └────────────────────────┘                  │
│               ▼                                                      │
│       tinycua_sdk.tools.cua  (BUILTIN_CUA_TOOLS)                     │
└──────────────────────────────────────────────────────────────────────┘
         ▲
         │  POST /internal/v1/toolcall
         │  POST /internal/v1/tools
         │
┌────────┴──────────────┐
│   tinycua-backend      │
│   RunnerClient         │
└───────────────────────┘
```

---

## Class Designs

### `config.py` — Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    service_token: str               # TINYCUA_RUNNER_SERVICE_TOKEN
    host: str = "0.0.0.0"
    port: int = 8001
    default_timeout_ms: int = 5000
    max_payload_bytes: int = 1_048_576   # 1 MB
    cpu_limit_s: int = 10            # TINYCUA_RUNNER_CPU_LIMIT_S
    as_limit_mb: int = 512           # TINYCUA_RUNNER_AS_LIMIT_MB
    fd_limit: int = 64               # TINYCUA_RUNNER_FD_LIMIT
    log_level: str = "INFO"

    class Config:
        env_prefix = "TINYCUA_RUNNER_"
```

### `models/tool.py` — RegisteredTool and ToolBundle

```python
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class ToolBundle:
    """Wire shape received from POST /internal/v1/tools."""
    type: str           # "function"
    name: str
    description: str
    parameters: dict    # JSON Schema object
    source: str
    dependencies: list[str] = field(default_factory=list)

@dataclass
class RegisteredTool:
    """
    Internal representation stored in the registry after materialisation.
    _fn is the callable produced by exec() on the bundle source,
    or the SDK function for built-in tools.
    """
    name: str
    description: str
    parameters: dict
    _fn: Callable
    is_builtin: bool = False

    def invoke(self, **kwargs) -> object:
        return self._fn(**kwargs)
```

### `registry/tool_registry.py` — ToolRegistry

```python
import threading
from tinycua_runner.models.tool import RegisteredTool
from tinycua_runner.models.errors import ToolNotFoundError, DuplicateToolError

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._lock = threading.Lock()

    def register(self, tool: RegisteredTool) -> None:
        """
        Store a RegisteredTool.
        Raises DuplicateToolError if name exists with different parameters schema.
        Silently no-ops if name exists with identical schema.
        """
        with self._lock:
            existing = self._tools.get(tool.name)
            if existing is not None:
                if existing.parameters != tool.parameters:
                    raise DuplicateToolError(tool.name)
                return  # same schema — idempotent
            self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool:
        """Raises ToolNotFoundError if not found."""
        with self._lock:
            if name not in self._tools:
                raise ToolNotFoundError(name)
            return self._tools[name]

    def deregister(self, name: str) -> None:
        """Raises ToolNotFoundError if not found. Raises BuiltinToolError if built-in."""
        with self._lock:
            tool = self._tools.get(name)
            if tool is None:
                raise ToolNotFoundError(name)
            if tool.is_builtin:
                raise BuiltinToolError(name)
            del self._tools[name]

    def list(self, limit: int = 20, after: str | None = None) -> list[RegisteredTool]:
        """Cursor-based pagination. `after` is the last tool name seen."""
        with self._lock:
            names = sorted(self._tools.keys())
            if after:
                try:
                    idx = names.index(after)
                    names = names[idx + 1:]
                except ValueError:
                    pass
            return [self._tools[n] for n in names[:limit]]
```

### `security/ast_check.py` — ASTChecker

```python
import ast

_FORBIDDEN_IMPORTS = {"subprocess"}
_FORBIDDEN_ATTRIBUTES = {
    ("os", "system"), ("os", "popen"), ("os", "execv"), ("os", "execve"),
    ("os", "execvp"), ("os", "execvpe"), ("os", "spawnv"), ("os", "spawnve"),
}
_FORBIDDEN_BUILTINS = {"eval", "exec"}

class _ForbiddenVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in _FORBIDDEN_IMPORTS:
                self.violations.append(f"import {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module and node.module.split(".")[0] in _FORBIDDEN_IMPORTS:
            self.violations.append(f"from {node.module} import ...")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # eval(...) / exec(...)
        if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_BUILTINS:
            self.violations.append(f"{node.func.id}(...)")
        # __import__(...)
        if isinstance(node.func, ast.Name) and node.func.id == "__import__":
            self.violations.append("__import__(...)")
        # os.system(...) etc.
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                pair = (node.func.value.id, node.func.attr)
                if pair in _FORBIDDEN_ATTRIBUTES:
                    self.violations.append(f"{pair[0]}.{pair[1]}(...)")
        self.generic_visit(node)

def check_source(source: str) -> list[str]:
    """
    Parse and walk the source AST.
    Returns a list of violation descriptions (empty list = clean).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc}"]
    visitor = _ForbiddenVisitor()
    visitor.visit(tree)
    return visitor.violations
```

### `sandbox/executor.py` — SandboxedExecutor

```python
import json
import multiprocessing
import resource
import traceback
from tinycua_runner.models.toolcall import ToolCallResult
from tinycua_runner.config import get_settings

def _worker(fn_source: str, fn_name: str, arguments: dict, result_queue, settings):
    """
    Runs in a child process. Sets resource limits then calls the function.
    Puts ToolCallResult-compatible dict into result_queue.
    """
    try:
        # Set resource limits
        cpu_limit = settings.cpu_limit_s
        as_limit = settings.as_limit_mb * 1024 * 1024
        fd_limit = settings.fd_limit
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
        resource.setrlimit(resource.RLIMIT_AS,  (as_limit,  as_limit))
        resource.setrlimit(resource.RLIMIT_NOFILE, (fd_limit, fd_limit))

        # Materialise the function from source
        namespace: dict = {}
        exec(compile(fn_source, "<tool>", "exec"), namespace)
        fn = namespace[fn_name]

        result = fn(**arguments)
        structured = result if isinstance(result, dict) else None
        result_queue.put({
            "status": "success",
            "structured": structured,
            "output_text": str(result),
            "logs": "",
        })
    except Exception:
        result_queue.put({
            "status": "failure",
            "structured": None,
            "output_text": "tool raised an exception",
            "logs": traceback.format_exc(),
        })

class SandboxedExecutor:
    """
    Execute a dynamically deployed tool in a subprocess with resource limits.
    """

    def run(
        self,
        fn_source: str,
        fn_name: str,
        arguments: dict,
        timeout_ms: int,
    ) -> ToolCallResult:
        settings = get_settings()
        queue = multiprocessing.Queue()
        proc = multiprocessing.Process(
            target=_worker,
            args=(fn_source, fn_name, arguments, queue, settings),
            daemon=True,
        )
        proc.start()
        proc.join(timeout=timeout_ms / 1000)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1)
            if proc.is_alive():
                proc.kill()
            return ToolCallResult(
                structured=None,
                output_text="execution timed out",
                logs="",
            ), "timeout"

        if not queue.empty():
            data = queue.get_nowait()
            return ToolCallResult(
                structured=data.get("structured"),
                output_text=data.get("output_text", ""),
                logs=data.get("logs", ""),
            ), data.get("status", "failure")

        return ToolCallResult(
            structured=None,
            output_text="subprocess exited with no result",
            logs="",
        ), "failure"
```

### `startup.py` — Built-in Tool Loading

```python
from tinycua_sdk.tools.cua import BUILTIN_CUA_TOOLS
from tinycua_runner.registry.tool_registry import ToolRegistry
from tinycua_runner.models.tool import RegisteredTool

def load_builtin_tools(registry: ToolRegistry) -> None:
    """
    Load all built-in CUA tools from tinycua_sdk into the registry.
    These tools bypass AST checks and sandbox execution.
    Called once at application startup before the HTTP server accepts connections.
    """
    for sdk_tool in BUILTIN_CUA_TOOLS:
        registered = RegisteredTool(
            name=sdk_tool.name,
            description=sdk_tool.description,
            parameters=sdk_tool.parameters,
            _fn=sdk_tool._fn,
            is_builtin=True,
        )
        registry.register(registered)
```

---

## Sequence Diagram: Tool Bundle Registration

```
SDK / Developer (tool.deploy(client))
     │
     │  POST /internal/v1/tools
     │  Authorization: Bearer <service_token>
     │  { type, name, description, parameters, source, dependencies }
     ▼
ServiceTokenMiddleware
     │  reject → 401 if invalid token
     ▼
ToolsRoute.register()
     │  validate ToolBundle shape → 422
     │  security.ast_check.check_source(bundle.source)
     │      violations non-empty → 422 with violation list
     │
     │  materialise:
     │    namespace = {}
     │    exec(compile(source, "<tool>", "exec"), namespace)
     │    fn = namespace[bundle.name]   # or fn_name from source
     │
     │  build RegisteredTool(name, description, parameters, _fn=fn, is_builtin=False)
     ▼
ToolRegistry.register()
     │  name exists + same schema → 200 (no-op)
     │  name exists + diff schema → 409 Conflict
     │  new → store
     ▼
HTTP 201  { "name": "get_weather", "created": true }
```

---

## Sequence Diagram: Tool Invocation (deployed tool)

```
tinycua-backend (OrchestrationLoop)
     │
     │  POST /internal/v1/toolcall
     │  { call_id, request_id, tool_name, arguments, timeout_ms, trace_id }
     ▼
ServiceTokenMiddleware  (token check)
     ▼
ToolCallRoute.invoke()
     │  registry.get(tool_name) → 404 if not found
     │  if tool.is_builtin:
     │      result, status = tool.invoke(**arguments), "success"
     │  else:
     │      result, status = SandboxedExecutor.run(
     │          fn_source, fn_name, arguments, timeout_ms)
     │  stop timer → duration_ms
     ▼
HTTP 200  ToolCallResponse
     { call_id, status, result, duration_ms, trace_id }
```

## Sequence Diagram: Tool Invocation (built-in CUA tool)

```
tinycua-backend (OrchestrationLoop)
     │
     │  POST /internal/v1/toolcall  { tool_name: "screenshot", … }
     ▼
ToolCallRoute.invoke()
     │  registry.get("screenshot") → RegisteredTool(is_builtin=True)
     │  result = tool.invoke()    ← direct call, NO subprocess
     ▼
HTTP 200  { status: "success", result: { structured: { image_b64: "…" } } }
```

---

## `routes/toolcall.py` — Dispatcher

```python
import time
from fastapi import APIRouter, Depends
from tinycua_runner.models.toolcall import ToolCallRequest, ToolCallResponse, ToolCallResult
from tinycua_runner.registry.tool_registry import get_registry
from tinycua_runner.sandbox.executor import SandboxedExecutor

router = APIRouter()
_sandbox = SandboxedExecutor()

@router.post("/internal/v1/toolcall")
async def invoke_tool(
    body: ToolCallRequest,
    registry = Depends(get_registry),
) -> ToolCallResponse:
    tool = registry.get(body.tool_name)   # raises 404 via exception handler
    start = time.monotonic()

    if tool.is_builtin:
        try:
            raw = tool.invoke(**body.arguments)
            structured = raw if isinstance(raw, dict) else None
            result = ToolCallResult(structured=structured, output_text=str(raw))
            status = "success"
        except Exception as exc:
            import traceback
            result = ToolCallResult(output_text=str(exc), logs=traceback.format_exc())
            status = "failure"
    else:
        result, status = _sandbox.run(
            fn_source=tool._source,     # stored on RegisteredTool during materialisation
            fn_name=tool.name,
            arguments=body.arguments,
            timeout_ms=body.timeout_ms,
        )

    duration_ms = int((time.monotonic() - start) * 1000)
    return ToolCallResponse(
        call_id=body.call_id,
        status=status,
        result=result,
        duration_ms=duration_ms,
        trace_id=body.trace_id,
    )
```

Note: `RegisteredTool` stores `_source` (the original bundle source string) in addition
to `_fn` so that the sandbox worker can re-materialise the function without importing
the parent process's namespace.

---

## `routes/tools.py` — Registration Routes

```python
@router.post("/internal/v1/tools", status_code=201)
async def register_tool(body: ToolBundle, registry = Depends(get_registry)):
    violations = check_source(body.source)
    if violations:
        raise HTTPException(422, detail={
            "code": "forbidden_construct",
            "message": f"Source contains forbidden constructs: {', '.join(violations)}",
        })

    namespace: dict = {}
    exec(compile(body.source, "<tool>", "exec"), namespace)
    if body.name not in namespace:
        raise HTTPException(422, detail={
            "code": "invalid_source",
            "message": f"Source does not define a callable named '{body.name}'.",
        })

    fn = namespace[body.name]
    tool = RegisteredTool(
        name=body.name,
        description=body.description,
        parameters=body.parameters,
        _fn=fn,
        _source=body.source,
        is_builtin=False,
    )
    registry.register(tool)   # raises DuplicateToolError → 409 via exception handler
    return {"name": body.name, "created": True}

@router.get("/internal/v1/tools")
async def list_tools(
    limit: int = 20, after: str | None = None,
    registry = Depends(get_registry),
):
    tools = registry.list(limit=limit, after=after)
    return {"tools": [_to_descriptor(t) for t in tools]}

@router.delete("/internal/v1/tools/{name}", status_code=204)
async def deregister_tool(name: str, registry = Depends(get_registry)):
    registry.deregister(name)   # raises ToolNotFoundError → 404, BuiltinToolError → 403
```

---

## `runner/client.py` (in `tinycua-backend`) — RunnerClient

```python
import httpx
from tinycua_backend.models.response import FunctionCallItem, FunctionCallOutputItem

class RunnerError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(message)

class RunnerClient:
    def __init__(self, base_url: str, service_token: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {service_token}"}

    async def invoke(
        self,
        call: FunctionCallItem,
        trace_id: str,
        timeout_ms: int = 5000,
    ) -> FunctionCallOutputItem:
        """
        POST /internal/v1/toolcall.
        Returns FunctionCallOutputItem on success or failure (HTTP-level 200).
        Raises RunnerError on HTTP error (4xx/5xx from the Runner itself).
        """
        payload = {
            "call_id":    call.call_id,
            "request_id": trace_id,
            "tool_name":  call.name,
            "arguments":  _parse_arguments(call.arguments),
            "timeout_ms": timeout_ms,
            "trace_id":   trace_id,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/internal/v1/toolcall",
                json=payload,
                headers=self._headers,
                timeout=(timeout_ms / 1000) + 1.0,   # +1s buffer
            )
        if resp.status_code != 200:
            raise RunnerError(resp.status_code, resp.text)
        data = resp.json()
        return FunctionCallOutputItem(
            type="function_call_output",
            call_id=data["call_id"],
            output=data["result"].get("output_text", ""),
        )

    async def register_tool(self, bundle: dict) -> None:
        """
        POST /internal/v1/tools — used by SDK deploy helpers proxied through backend.
        409 (same schema) is treated as success. Other errors raise RunnerError.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/internal/v1/tools",
                json=bundle,
                headers=self._headers,
            )
        if resp.status_code not in (200, 201, 409):
            raise RunnerError(resp.status_code, resp.text)
```

---

## `models/toolcall.py` — Invocation Request/Response

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class ToolCallRequest:
    call_id: str
    request_id: str
    tool_name: str
    arguments: dict
    timeout_ms: int = 5000
    trace_id: str = ""

@dataclass
class ToolCallResult:
    structured: dict | None = None
    output_text: str = ""
    logs: str = ""

@dataclass
class ToolCallResponse:
    call_id: str
    status: Literal["success", "failure", "timeout"]
    result: ToolCallResult
    duration_ms: int
    trace_id: str
```

---

## Auth (`auth/middleware.py`)

`ServiceTokenMiddleware` is a Starlette `BaseHTTPMiddleware`:

- Reads `Authorization: Bearer <token>`.
- Compares against `Settings.service_token` using `hmac.compare_digest`.
- Exempts `GET /internal/health`.
- Returns 401 on failure:
  ```json
  { "error": { "code": "unauthorized", "message": "Invalid or missing service token." } }
  ```

---

## Error Handling

| Condition                            | HTTP | `error.code`             |
|--------------------------------------|------|--------------------------|
| Missing/invalid service token        | 401  | `unauthorized`           |
| Tool not found                       | 404  | `tool_not_found`         |
| Duplicate tool (schema conflict)     | 409  | `duplicate_tool`         |
| Deregister built-in tool             | 403  | `forbidden`              |
| Payload too large                    | 413  | `request_too_large`      |
| Bundle schema invalid                | 422  | `invalid_request`        |
| Forbidden construct in source        | 422  | `forbidden_construct`    |
| Source does not define named fn      | 422  | `invalid_source`         |
| Unexpected internal error            | 500  | `internal_error`         |

Note: tool execution errors/timeouts return **HTTP 200** with `status: "failure"/"timeout"`
in the body — this is by design.

---

## Structured Logging

Every toolcall request is logged:

```json
{
  "event": "toolcall",
  "trace_id": "uuid",
  "tool_name": "get_weather",
  "is_builtin": false,
  "status": "success",
  "duration_ms": 42,
  "timestamp": "2026-03-11T10:00:00Z"
}
```

`arguments` are **never** logged in full — only a SHA-256 hash of the serialised
arguments is stored to allow correlation without exposing sensitive data.

---

## Phases

### Phase 1 (MVP)

- `POST /internal/v1/toolcall` — synchronous invocation (subprocess sandbox + direct for built-ins).
- `POST /internal/v1/tools` — bundle registration with AST check + `exec()` materialisation.
- `GET /internal/v1/tools`, `DELETE /internal/v1/tools/{name}`.
- `ToolRegistry` (in-memory, thread-safe).
- Built-in CUA tool loading at startup.
- `ServiceTokenMiddleware`.
- `GET /internal/health`.
- `RegisteredTool._source` stored for sandbox re-materialisation.

### Phase 2

- Auto-install `dependencies` via `pip` in an isolated venv per tool.
- Persistent tool registry (SQLite or JSON file) — survives restart.
- Tool result audit log (append-only, per `trace_id`).
- Batch toolcall endpoint (`POST /internal/v1/toolcall/batch`).
- Plugin discovery: auto-scan a configured Python package for `@tool`-decorated functions
  at startup.

---

## Open Questions Resolved

- **OQ-001** (`dependencies` auto-install): Deferred to Phase 2. Document limitation.
- **OQ-002** (Tool result persistence): Deferred to Phase 2; stateless in MVP.
- **OQ-003** (Batch toolcall endpoint): Deferred to Phase 2; backend uses
  `asyncio.gather` with individual calls in MVP.
