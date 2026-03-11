# Specification: Backend ↔ Runner Integration (Internal API)

## Problem Statement

When a provider response contains a `function_call` output item, the backend must invoke
the actual tool implementation and inject a structured result back into the conversation.
The Runner is the dedicated service that owns tool registration and execution. It imports
`tinycua-sdk` directly, so tool execution is simply `tool.invoke(**args)` — no separate
executor class hierarchy is needed.

Tools are registered by deploying a **bundle** (source code + dependencies +
descriptor). The Runner performs a static AST check on the bundle source before accepting
it, then materialises the function in a restricted namespace. All dynamically deployed
tools run inside a subprocess with OS-level resource limits. Built-in CUA tools are loaded
from the SDK at startup and are never subject to sandboxing.

---

## Scope

Included in this spec:
- Internal HTTP/JSON API between backend and Runner.
- Tool bundle registration, listing, and deregistration.
- Synchronous tool invocation with sandboxed subprocess execution.
- Built-in CUA tool loading at startup.
- Static AST security check on bundle source.
- Auth between backend and Runner (service token).
- Timeout handling and structured error responses.
- Observability (`trace_id` propagation).

Excluded:
- Public-facing API — that is the `openai-responses` spec.
- SDK tool/agent abstractions — that is the `agent-tool-abstraction` spec.
- Auth and session endpoints — that is the `auth-session` spec.

---

## Requirements

### Startup

- **FR-001**: At startup, the Runner must load all five built-in CUA tools from
  `tinycua_sdk.tools.cua` (`screenshot`, `click_at`, `type_text`, `hotkey`,
  `find_element`) and register them in the in-memory tool registry. These tools are
  **never** subject to AST checks or subprocess sandboxing — they are trusted SDK code.

### Tool bundle registration

- **FR-002**: The Runner must expose `POST /internal/v1/tools` to accept a tool bundle.
  Bundle shape:
  ```json
  {
    "type": "function",
    "name": "get_weather",
    "description": "Return current weather for a location.",
    "parameters": { "type": "object", "properties": { … }, "required": […] },
    "source": "def get_weather(location: str) -> dict:\n    ...",
    "dependencies": ["requests"]
  }
  ```
- **FR-003**: Before storing the bundle, the Runner must run a **static AST check** on
  the `source` field. The following constructs must be **rejected** with `422`:
  - `import subprocess` or any use of `subprocess`
  - `os.system`, `os.popen`, `os.execv` and related `os` execution calls
  - `eval(...)`, `exec(...)`
  - `__import__(...)` used to bypass the import check
  - Unrestricted `socket` usage (binding to arbitrary ports)
  If any forbidden construct is found, the bundle is rejected with a clear error message
  naming the offending construct.
- **FR-004**: After passing the AST check, the Runner must materialise the function by
  executing the source in a restricted namespace (`exec()` with a controlled `globals`
  dict) and storing the resulting callable in the registry.
- **FR-005**: The Runner must expose `GET /internal/v1/tools` to list all registered tools
  (name, description, parameters — no source code in list response). Paginated:
  cursor-based, `limit` + `after` query params.
- **FR-006**: The Runner must expose `DELETE /internal/v1/tools/{name}` to deregister a
  tool. Returns `404` if the tool does not exist. Built-in tools cannot be deregistered
  (returns `403`).
- **FR-007**: Tool names are globally unique within the Runner instance. Re-registering an
  existing name with a different bundle returns `409 Conflict`.
- **FR-008**: All `/internal/` endpoints require `Authorization: Bearer <service_token>`.
  Requests without a valid service token return `401`.

### Tool invocation

- **FR-009**: The Runner must expose `POST /internal/v1/toolcall` for synchronous tool
  invocation. Request body:
  ```json
  {
    "call_id":    "call_abc123",
    "request_id": "resp_xyz",
    "tool_name":  "get_weather",
    "arguments":  { "location": "NYC" },
    "timeout_ms": 5000,
    "trace_id":   "uuid-v4"
  }
  ```
- **FR-010**: The Runner must execute the tool via `tool.invoke(**arguments)`. Execution
  must run in a **subprocess** with the following resource limits:
  - CPU time: configurable cap (default 10 s, `TINYCUA_RUNNER_CPU_LIMIT_S`)
  - Address space: configurable cap (default 512 MB, `TINYCUA_RUNNER_AS_LIMIT_MB`)
  - Open file descriptors: configurable cap (default 64, `TINYCUA_RUNNER_FD_LIMIT`)
  Resource limits are set via `resource.setrlimit` in the child process before invoking
  the function.
- **FR-011**: Built-in CUA tools are **exempt** from subprocess sandboxing — they are
  invoked directly in the Runner process via `tool.invoke(**arguments)`.
- **FR-012**: The Runner must return the result synchronously:
  ```json
  {
    "call_id":     "call_abc123",
    "status":      "success" | "failure" | "timeout",
    "result": {
      "structured":  { "temp": 72, "unit": "F" },
      "output_text": "72°F in NYC",
      "logs":        "..."
    },
    "duration_ms": 123,
    "trace_id":    "uuid-v4"
  }
  ```
- **FR-013**: If execution exceeds `timeout_ms`, the subprocess is terminated and the
  Runner returns `status: "timeout"` (HTTP 200 — not a 5xx error).
- **FR-014**: If the tool raises an unhandled exception, the Runner returns
  `status: "failure"` with a human-readable message in `result.output_text` and
  sanitised stack trace in `result.logs`.
- **FR-015**: The `trace_id` from the request must be echoed in every response.

### Health

- **FR-016**: The Runner must expose `GET /internal/health` returning `{ "status": "ok" }`
  with HTTP 200. This endpoint is exempt from auth.

---

## Tool Bundle Shape (full reference)

```json
{
  "type": "function",
  "name": "get_weather",
  "description": "Return current weather for a location.",
  "parameters": {
    "type": "object",
    "properties": {
      "location": { "type": "string", "description": "City name or coordinates." }
    },
    "required": ["location"]
  },
  "source": "@tool(dependencies=[\"requests\"])\ndef get_weather(location: str) -> dict:\n    ...",
  "dependencies": ["requests"]
}
```

Note: `dependencies` are recorded but the Runner does not auto-install them in MVP. The
Runner process is expected to have all commonly used packages available. Auto-install
(via `pip` in a venv) is a Phase 2 feature.

---

## AST Check — Forbidden Constructs (reference)

| Pattern | Reason blocked |
|---|---|
| `import subprocess` | Arbitrary subprocess execution |
| `subprocess.run(...)`, `subprocess.Popen(...)` | Same |
| `os.system(...)`, `os.popen(...)`, `os.execv(...)` | Shell execution via os |
| `eval(...)` | Arbitrary code evaluation |
| `exec(...)` | Arbitrary code execution |
| `__import__(...)` | Import bypass |
| `socket.bind(...)` at top level | Unrestricted network binding |

The AST check walks the `ast.parse(source)` tree using a `NodeVisitor`. It does not
attempt to execute the code.

---

## Acceptance Scenarios

### Scenario 1 — Built-in CUA tools available at startup
```
When the Runner starts
Then GET /internal/v1/tools returns at least:
  screenshot, click_at, type_text, hotkey, find_element
And all five have description populated
```

### Scenario 2 — Successful bundle registration
```
Given valid service token
When POST /internal/v1/tools with a valid bundle (clean source)
Then HTTP 201
And GET /internal/v1/tools returns the new tool
```

### Scenario 3 — AST check rejects forbidden construct
```
Given bundle source contains: "import subprocess"
When POST /internal/v1/tools
Then HTTP 422
And error message names "subprocess" as the forbidden construct
And tool is NOT added to registry
```

### Scenario 4 — Successful synchronous invocation
```
Given tool "get_weather" registered
When POST /internal/v1/toolcall with tool_name "get_weather", arguments { location: "NYC" }
Then HTTP 200
And response.status = "success"
And response.result.structured contains weather data
And response.call_id matches request call_id
And response.trace_id matches request trace_id
```

### Scenario 5 — Sandboxed tool timeout
```
Given tool "slow_tool" registered (source: "import time; time.sleep(60)")
When POST /internal/v1/toolcall with timeout_ms 500
Then HTTP 200
And response.status = "timeout"
And subprocess was terminated
```

### Scenario 6 — Sandboxed tool resource limit hit
```
Given tool "mem_hog" registered (source: allocates > 512 MB)
When POST /internal/v1/toolcall
Then HTTP 200
And response.status = "failure"
And response.result.logs contains MemoryError or SIGKILL indication
```

### Scenario 7 — Built-in tool invocation (no sandbox)
```
When POST /internal/v1/toolcall with tool_name "screenshot"
Then HTTP 200
And response.status = "success"
And response.result.structured contains "image_b64"
And no subprocess was spawned
```

### Scenario 8 — Tool not found
```
When POST /internal/v1/toolcall with tool_name "nonexistent"
Then HTTP 404
And error body contains "tool not found"
```

### Scenario 9 — Duplicate registration (schema conflict)
```
Given tool "get_weather" already registered
When POST /internal/v1/tools with same name but different parameters schema
Then HTTP 409 Conflict
```

### Scenario 10 — Cannot deregister built-in tool
```
When DELETE /internal/v1/tools/screenshot
Then HTTP 403
And error body contains "built-in tool cannot be deregistered"
```

### Scenario 11 — Unauthorized
```
When any /internal/ endpoint called without service token
Then HTTP 401
```

---

## Testing Plan

- **Unit**: AST check rejects each forbidden construct individually; AST check passes clean
  source; bundle materialisation (`exec()` + callable retrieved); timeout enforcement;
  subprocess resource limit setup; error serialisation.
- **Integration**: register a real tool bundle, invoke it from the backend's orchestration
  loop, assert `function_call_output` is correctly injected back into the conversation.
  CUA tool invocation (mocked screen, no real display).
- **Security**: missing service token → 401; oversized argument payload → 413; all six
  AST-forbidden patterns → 422.

---

## Open Questions

- **OQ-001**: Should `dependencies` be auto-installed in the Runner process at registration
  time (using `pip` in an isolated venv)?
  Recommendation: defer to Phase 2. In MVP, the Runner's Python environment is expected to
  have necessary packages. Document this limitation clearly.
- **OQ-002**: Should tool results be persisted by the Runner for audit/replay?
  Recommendation: defer to Phase 2; stateless invocation in MVP.
- **OQ-003**: For parallel tool calls, the backend fires multiple
  `POST /internal/v1/toolcall` in parallel via `asyncio.gather`. Should the Runner also
  expose a batch endpoint to reduce HTTP overhead?
  Recommendation: no batch endpoint in MVP. Evaluate in Phase 2 if latency is a concern.
