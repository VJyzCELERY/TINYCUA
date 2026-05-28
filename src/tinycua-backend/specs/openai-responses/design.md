# Design: OpenAI Responses API Compatibility Layer

## Overview

This document describes the internal architecture of the OpenAI Responses API compatibility
layer in `tinycua-backend`. It translates spec requirements into concrete module structure,
class hierarchies, data-flow diagrams, and implementation decisions.

---

## Package Layout

```
src/tinycua-backend/
└── tinycua_backend/
    ├── __init__.py
    ├── main.py                  # FastAPI application factory (create_app())
    ├── config.py                # Settings (pydantic BaseSettings) — reads env vars
    ├── auth/
    │   ├── __init__.py
    │   ├── middleware.py        # BearerAuthMiddleware (JWT + API key)
    │   ├── jwt.py               # encode_token(), decode_token()
    │   └── apikey.py            # hash_key(), verify_key()
    ├── database/
    │   ├── __init__.py
    │   ├── engine.py            # SQLAlchemy engine + session factory
    │   └── models.py            # ORM models: User, ApiKey, Session, SessionMessage
    ├── models/
    │   ├── __init__.py
    │   ├── request.py           # ResponseRequest, InputItem, ToolDefinition, …
    │   └── response.py          # Response, OutputItem, Usage, IncompleteDetails, …
    ├── registry/
    │   ├── __init__.py
    │   └── model_registry.py    # ModelRegistry, ModelEntry
    ├── providers/
    │   ├── __init__.py
    │   ├── base.py              # BaseProvider (abstract)
    │   ├── local_openai.py      # LocalOpenAIProvider (OpenAI-compatible endpoints)
    │   ├── anthropic.py         # AnthropicProvider (future)
    │   └── openai_passthrough.py# OpenAIPassthroughProvider
    ├── orchestration/
    │   ├── __init__.py
    │   └── loop.py              # OrchestrationLoop
    ├── runner/
    │   ├── __init__.py
    │   └── client.py            # RunnerClient — calls Runner's internal API
    ├── sessions/
    │   ├── __init__.py
    │   └── service.py           # SessionService: load_history(), save_turn(), get_context()
    ├── streaming/
    │   ├── __init__.py
    │   └── sse.py               # SSEEmitter, event builders
    ├── routes/
    │   ├── __init__.py
    │   ├── responses.py         # POST /v1/responses
    │   └── health.py            # GET /health
    └── logging/
        ├── __init__.py
        └── structured.py        # JSON log formatter, redaction helpers
```

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         FastAPI App                             │
│                                                                 │
│  BearerTokenMiddleware  ──►  POST /v1/responses                 │
│                                     │                           │
│                           ┌─────────▼──────────┐               │
│                           │  ResponsesRoute     │               │
│                           │  - validate request │               │
│                           │  - lookup model     │               │
│                           └─────────┬──────────┘               │
│                                     │                           │
│                           ┌─────────▼──────────┐               │
│                           │  OrchestrationLoop  │               │
│                           │  (loop.py)          │               │
│                           └──┬──────────────┬──┘               │
│                              │              │                   │
│                   ┌──────────▼───┐  ┌───────▼──────────┐       │
│                   │ BaseProvider │  │  RunnerClient     │       │
│                   │  (adapter)   │  │  (tool calls)     │       │
│                   └──────┬───────┘  └───────────────────┘       │
│                          │                                      │
│          ┌───────────────┼───────────────────┐                 │
│          ▼               ▼                   ▼                 │
│   LocalOpenAIProvider  AnthropicProvider  OpenAIPassthrough    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Class Designs

### `config.py` — Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str                # TINYCUA_JWT_SECRET
    database_url: str = "sqlite:///./tinycua.db"  # TINYCUA_DATABASE_URL
    model_registry_path: str       # path to models.yaml (or inline JSON)
    runner_base_url: str           # http://runner:8001
    runner_service_token: str      # shared secret
    max_tool_calls_default: int = 10
    log_level: str = "INFO"

    class Config:
        env_prefix = "TINYCUA_"
```

### `registry/model_registry.py` — Model Registry

```python
@dataclass
class ModelEntry:
    name: str
    provider: Literal["openai-compatible", "openai", "anthropic"]
    endpoint: str                  # e.g. "http://localhost:1234/v1"
    default_temperature: float = 1.0
    context_length: int | None = None
    extra: dict = field(default_factory=dict)

class ModelRegistry:
    def __init__(self, entries: list[ModelEntry]) -> None: ...
    def get(self, model_name: str) -> ModelEntry:
        """Raise ModelNotFoundError if not found."""
    @classmethod
    def from_yaml(cls, path: str) -> "ModelRegistry": ...
    @classmethod
    def from_env(cls, raw: str) -> "ModelRegistry":
        """Parse JSON/YAML from TINYCUA_MODEL_REGISTRY env var."""
```

`models.yaml` example:

```yaml
models:
  - name: local-qwen-7b
    provider: openai-compatible
    endpoint: http://localhost:1234/v1
    default_temperature: 0.7
    context_length: 8192
  - name: gpt-4o
    provider: openai
    endpoint: https://api.openai.com/v1
```

### `providers/base.py` — Provider Interface

```python
from abc import ABC, abstractmethod

class BaseProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        request: ResponseRequest,
        entry: ModelEntry,
    ) -> Response:
        """Non-streaming completion. Returns a full Response object."""

    @abstractmethod
    async def stream(
        self,
        request: ResponseRequest,
        entry: ModelEntry,
    ) -> AsyncIterator[StreamEvent]:
        """Streaming completion. Yields canonical StreamEvent objects."""
```

### Provider Implementations

#### `providers/local_openai.py`

- Uses OpenAI-compatible `/v1/chat/completions` endpoint.
- Maps `choices[0].message` → `output[]` items.
- Maps `choices[0].delta` to `response.output_text.delta` events for streaming.
- Works with any OpenAI-compatible server (local or remote).

#### `providers/anthropic.py` (future)

- Will translate `ResponseRequest` → Anthropic Messages API format.
- Stub for future native Anthropic API support.

#### `providers/openai_passthrough.py`

- Forwards the full request body to `https://api.openai.com/v1/responses` (or configured
  endpoint) with the client's API key replaced by the configured OpenAI key.
- Streams SSE chunks verbatim — no re-mapping needed since the upstream is already canonical.

---

## Data-Flow: Non-Streaming Request

```
Client
  │
  │  POST /v1/responses  { model, input, tools, stream: false }
  ▼
BearerTokenMiddleware
  │  reject → 401
  ▼
ResponsesRoute.handle()
  │  validate body → 422 on schema error
  │  registry.get(model) → 404 if not found
  │  generate trace_id (UUID v4)
  ▼
OrchestrationLoop.run(request, entry, trace_id)
  │
  │  ┌──────────────────────────────────────────────┐
  │  │  LOOP (up to max_tool_calls)                  │
  │  │                                               │
  │  │  provider.complete(request, entry)            │
  │  │       → Response                              │
  │  │                                               │
  │  │  if output has function_call items:           │
  │  │    for each call:                             │
  │  │      runner_client.invoke(call, trace_id)     │
  │  │    inject function_call_output into input[]   │
  │  │    continue loop                              │
  │  │                                               │
  │  │  else: break → final Response                 │
  │  └──────────────────────────────────────────────┘
  │
  │  if loop exhausted: set status="incomplete"
  ▼
structured_log(trace_id, model, latency_ms, tokens, …)
  ▼
HTTP 200  Response JSON
```

---

## Data-Flow: Streaming Request

```
Client
  │
  │  POST /v1/responses  { stream: true, … }
  ▼
ResponsesRoute.handle_stream()
  │
  │  returns StreamingResponse(media_type="text/event-stream")
  │
  ▼  (async generator)
OrchestrationLoop.stream(request, entry, trace_id)
  │
  │  yield SSEEmitter.created(response_id, trace_id)
  │
  │  ┌──── LOOP ─────────────────────────────────────┐
  │  │                                               │
  │  │  async for event in provider.stream(…):       │
  │  │    yield event   (delta, output_item events)  │
  │  │                                               │
  │  │  if final chunk contained function_calls:     │
  │  │    invoke runner (non-streaming HTTP calls)   │
  │  │    inject results, continue loop              │
  │  │                                               │
  │  └───────────────────────────────────────────────┘
  │
  │  yield SSEEmitter.completed(response, usage)
  │  yield "data: [DONE]\n\n"
  ▼
Connection closed
```

---

## `orchestration/loop.py` — OrchestrationLoop

```python
_CUA_TOOL_NAMES = {"screenshot", "click_at", "type_text", "hotkey", "find_element"}

_GET_CONTEXT_TOOL = {
    "type": "function",
    "name": "get_context",
    "description": "Retrieve additional context or summary from the current session.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What context to retrieve."}
        },
        "required": [],
    },
}

class OrchestrationLoop:
    def __init__(
        self,
        provider: BaseProvider,
        runner: RunnerClient,
        session_service: "SessionService | None",
        max_tool_calls: int,
        is_master: bool = False,
    ) -> None: ...

    async def run(
        self,
        request: ResponseRequest,
        entry: ModelEntry,
        trace_id: str,
    ) -> Response:
        # Inject get_context tool if session is active
        if request.session_id:
            request = _inject_get_context(request)

        tool_calls_used = 0
        while True:
            response = await self.provider.complete(request, entry)
            func_calls = [i for i in response.output if i.type == "function_call"]
            if not func_calls:
                return response
            if tool_calls_used + len(func_calls) > self.max_tool_calls:
                response.status = "incomplete"
                response.incomplete_details = IncompleteDetails(reason="max_tool_calls")
                return response

            results = await self._invoke_tools(func_calls, request, trace_id)
            tool_calls_used += len(func_calls)
            request = _inject_results(request, results)

    async def _invoke_tools(
        self,
        calls: list[FunctionCallItem],
        request: ResponseRequest,
        trace_id: str,
    ) -> list[FunctionCallOutputItem]:
        async def _invoke_one(call: FunctionCallItem):
            # get_context is handled locally — no Runner call
            if call.name == "get_context":
                return await self._handle_get_context(call, request.session_id)
            # CUA access guard
            if call.name in _CUA_TOOL_NAMES and not self.is_master:
                # Return an error result — orchestration loop will set incomplete
                raise CUAAccessDeniedError(call.name)
            return await self.runner.invoke(call, trace_id)

        if request.parallel_tool_calls:
            results = await asyncio.gather(*[_invoke_one(c) for c in calls])
        else:
            results = [await _invoke_one(c) for c in calls]
        return results

    async def _handle_get_context(
        self, call: FunctionCallItem, session_id: str | None
    ) -> FunctionCallOutputItem:
        if self.session_service and session_id:
            context = await self.session_service.get_context(session_id)
        else:
            context = "No session context available."
        return FunctionCallOutputItem(
            type="function_call_output",
            call_id=call.call_id,
            output=context,
        )

    async def stream(
        self,
        request: ResponseRequest,
        entry: ModelEntry,
        trace_id: str,
    ) -> AsyncIterator[StreamEvent]:
        if request.session_id:
            request = _inject_get_context(request)
        # Similar loop, yields events; buffers function_call items then invokes
        ...
```

---

## `runner/client.py` — RunnerClient

```python
class RunnerClient:
    def __init__(self, base_url: str, service_token: str) -> None: ...

    async def invoke(
        self,
        call: FunctionCallItem,
        trace_id: str,
        timeout_ms: int = 5000,
    ) -> FunctionCallOutputItem:
        """
        POST /internal/v1/toolcall
        Returns FunctionCallOutputItem on success.
        Raises RunnerError on HTTP error.
        """
```

---

## `streaming/sse.py` — SSE Event Builders

```python
def format_event(event_type: str, data: dict) -> str:
    """Returns 'event: <type>\ndata: <json>\n\n'."""

class SSEEmitter:
    @staticmethod
    def created(response_id: str, trace_id: str) -> str: ...

    @staticmethod
    def output_item_added(index: int, item: OutputItem) -> str: ...

    @staticmethod
    def output_text_delta(index: int, delta: str) -> str: ...

    @staticmethod
    def output_text_done(index: int, text: str) -> str: ...

    @staticmethod
    def output_item_done(index: int, item: OutputItem) -> str: ...

    @staticmethod
    def completed(response: Response) -> str: ...
```

---

## Auth Middleware

`auth/middleware.py` implements a Starlette `BaseHTTPMiddleware`:

- Reads `Authorization: Bearer <token>`.
- First attempts JWT verification via `jwt.decode_token(token)` (checks signature +
  expiry). On success, extracts `user_id` and `is_master` from claims and attaches a
  `request.state.user` object.
- On JWT failure (signature invalid, expired), falls back to API key lookup: queries the
  `ApiKey` table for a matching hash. On match, loads the associated `User` and attaches
  `request.state.user`.
- If both fail, returns 401.
- Exempts `GET /health` from auth.

Full JWT and API key implementation details are in the `auth-session` design.

---

## Session Handling

### `routes/responses.py` — session load + save

```python
@router.post("/v1/responses")
async def handle_responses(
    body: ResponseRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    user = request.state.user
    session_svc = SessionService(db)

    # Load session history if session_id provided
    if body.session_id:
        history = await session_svc.load_history(body.session_id, user.id)
        body = _prepend_history(body, history)

    # Build orchestration loop with is_master flag
    loop = OrchestrationLoop(
        provider=get_provider(body.model),
        runner=runner_client,
        session_service=session_svc if body.session_id else None,
        max_tool_calls=body.max_tool_calls or settings.max_tool_calls_default,
        is_master=user.is_master,
    )

    trace_id = str(uuid.uuid4())
    async with RequestLogger(trace_id, body.model) as log_ctx:
        response = await loop.run(body, registry.get(body.model), trace_id)
        log_ctx.finalize(response)

    # Save new turn to session
    if body.session_id:
        await session_svc.save_turn(
            session_id=body.session_id,
            user_id=user.id,
            user_input=_extract_user_input(body),
            assistant_output=_extract_assistant_output(response),
        )

    return response
```

### `sessions/service.py` — SessionService (interface summary)

Full implementation is in the `auth-session` design. The interface consumed here:

```python
class SessionService:
    async def load_history(self, session_id: str, user_id: int) -> list[dict]:
        """Return message history as list of input items. Raises 404 if not found or not owned."""

    async def save_turn(self, session_id: str, user_id: int,
                        user_input: str, assistant_output: str) -> None:
        """Append a turn to the session."""

    async def get_context(self, session_id: str) -> str:
        """Return a context summary string for the get_context native tool."""
```

---

## Error Handling

All error responses follow the OpenAI error shape:

```json
{ "error": { "code": "<code>", "message": "<human-readable>" } }
```

| Condition                          | HTTP | `error.code`        |
|------------------------------------|------|---------------------|
| Missing/invalid `Authorization`    | 401  | `unauthorized`      |
| Model not in registry              | 404  | `model_not_found`   |
| Request body fails schema          | 422  | `invalid_request`   |
| Request body too large             | 413  | `request_too_large` |
| Provider upstream error            | 502  | `provider_error`    |
| Internal unexpected error          | 500  | `internal_error`    |

FastAPI exception handlers are registered in `main.py` for each custom exception class:
`UnauthorizedError`, `ModelNotFoundError`, `ValidationError`, `ProviderError`.

---

## Structured Logging

`logging/structured.py` provides:

- A `structlog` (or `logging` + custom `JSONFormatter`) pipeline.
- A `redact()` helper that removes values from `metadata` keys and truncates `arguments`
  to a configurable byte limit before persisting.
- A `RequestLogger` context manager used in route handlers:

```python
async with RequestLogger(trace_id, model, provider) as log_ctx:
    response = await loop.run(request, entry, trace_id)
    log_ctx.finalize(response)   # records latency, tokens, tool_calls_count
```

---

## `models/request.py` and `models/response.py`

### Key request types

```python
@dataclass
class InputItem:
    role: Literal["user", "assistant", "system", "tool"]
    content: str | list[ContentPart]
    type: str | None = None         # "function_call_output" for tool results
    call_id: str | None = None

@dataclass
class ToolDefinition:
    type: Literal["function"] = "function"
    name: str = ""
    description: str = ""
    parameters: dict = field(default_factory=dict)
    strict: bool = False

@dataclass
class ResponseRequest:
    model: str
    input: list[InputItem]
    tools: list[ToolDefinition] = field(default_factory=list)
    stream: bool = False
    temperature: float | None = None
    max_output_tokens: int | None = None
    tool_choice: str | dict = "auto"
    parallel_tool_calls: bool = True
    max_tool_calls: int | None = None     # backend-level cap, not in OpenAI spec
    session_id: str | None = None         # stateful session; loads+saves history
    metadata: dict = field(default_factory=dict)
    instructions: str | None = None
```

### Key response types

```python
@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    total_tokens: int

@dataclass
class FunctionCallItem:
    type: Literal["function_call"] = "function_call"
    id: str = ""
    call_id: str = ""
    name: str = ""
    arguments: str = ""      # JSON string (matches OpenAI shape)

@dataclass
class MessageItem:
    type: Literal["message"] = "message"
    id: str = ""
    role: Literal["assistant"] = "assistant"
    content: list[ContentPart] = field(default_factory=list)

OutputItem = FunctionCallItem | MessageItem

@dataclass
class IncompleteDetails:
    reason: Literal["max_tool_calls", "max_output_tokens", "content_filter"]

@dataclass
class Response:
    id: str
    object: Literal["response"] = "response"
    created_at: int = 0          # Unix timestamp
    status: Literal["completed", "incomplete", "in_progress"] = "completed"
    model: str = ""
    output: list[OutputItem] = field(default_factory=list)
    usage: Usage | None = None
    incomplete_details: IncompleteDetails | None = None
    error: dict | None = None
    metadata: dict = field(default_factory=dict)
```

---

## Phases

### Phase 1 (MVP)

- `POST /v1/responses` non-streaming + SSE streaming.
- LocalOpenAIProvider, AnthropicProvider, OpenAIPassthroughProvider.
- `ModelRegistry` loaded from `models.yaml` or env var at startup.
- `OrchestrationLoop` with session loading/saving, `get_context` handling, `is_master`
  CUA guard.
- `BearerAuthMiddleware` (JWT + API key fallback).
- SQLite database via SQLAlchemy (`sessions/` + `database/` subpackages).
- Structured JSON logging.
- `GET /health`.

### Phase 2

- Rate limiting per user (pluggable middleware).
- Server-side agent storage (agent descriptor persistence).
- Metrics endpoint (`GET /metrics` — Prometheus format).
- Provider retry logic with circuit breakers.

---

## Open Questions Resolved

- **OQ-001** (`previous_response_id`): Not supported. `session_id` replaces it.
- **OQ-002** (Rate limiting): Deferred to Phase 2.
- **OQ-003** (Response storage / stateless): Backend is stateful in MVP for sessions.
  The session service (SQLite) is owned by `auth-session`; the orchestration layer
  consumes it via `SessionService`.
