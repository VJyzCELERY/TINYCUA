# Specification: SDK Agent and Tool Abstraction

## Problem Statement

Developers building agents with TINYCUA need three things:

1. A low-level client that speaks the OpenAI Responses API so they can send requests and
   receive streaming or non-streaming responses without writing HTTP boilerplate.
2. High-level `Tool` and `Agent` abstractions so they can define tools as Python functions,
   compose them into agents, and deploy them to the backend — without knowing the internal
   wire format.
3. A CLI entry point (`tinycua`) for interactive and scripted agent usage.

Although TINYCUA's primary use case is Computer Use Agents (CUA), the abstractions must be
generic enough to support any tool-using agent. CUA-specific behaviour (screen capture,
mouse/keyboard actions, element finding) is implemented as a specialised subclass of the
general `Agent` and as pre-built `Tool` implementations — not baked into the core SDK.

---

## Scope

Included in this spec:
- Low-level `ResponsesClient`: wraps `POST /v1/responses`, handles auth, retries, and
  SSE streaming.
- `Tool` model: dataclass capturing name, description, JSON Schema for parameters, source
  code, and dependencies. Class methods `to_config()`, `to_bundle()`, `from_config()`,
  `deploy(client)`.
- `@tool(dependencies=[])` decorator: converts a Python function into a `Tool` automatically.
- `Agent` base class: architectural skeleton with hook placeholders for context retrieval,
  prompt/token management, and serialisation — no domain-specific defaults.
- `CUAAgent` subclass: extends `Agent` with built-in CUA tools and base instructions for
  computer use.
- `AgentClient`: high-level helper that runs a multi-turn function-calling loop. Supports
  both Mode A (client-orchestrated, local function execution) and Mode B
  (server-orchestrated, backend owns the loop).
- `agent.deploy(client)`: class method that uploads user-added tool bundles to the Runner.
- `types.py`: shared dataclasses and type aliases used across the SDK.
- `tinycua` CLI: interactive REPL and non-interactive commands.

Excluded from this spec:
- Backend implementation — see `openai-responses` spec.
- Runner implementation — see `runner-integration` spec.
- Auth and session endpoints — see `auth-session` spec.
- Fine-tuning pipeline — see `tinycua-finetune` spec.

---

## Requirements

### Low-level client (`clients/client.py`)

- **FR-001**: `ResponsesClient` must accept `base_url` and `api_key` in its constructor
  and fall back to `TINYCUA_API_URL` / `TINYCUA_API_KEY` environment variables.
- **FR-002**: `ResponsesClient.create(request: ResponseRequest) -> Response` must call
  `POST /v1/responses` and return a parsed `Response` dataclass.
- **FR-003**: `ResponsesClient.stream(request: ResponseRequest) -> Iterator[StreamEvent]`
  must return a generator that yields parsed SSE events. The generator must close the
  connection on `StopIteration` or if the caller breaks early.
- **FR-004**: The client must retry on transient errors (5xx, network timeout) with
  exponential back-off (max 3 retries by default, configurable).
- **FR-005**: The client must attach a `X-Trace-Id` header (UUID v4) on every request.

### Tool model and decorator (`models/tool.py`, `tools/decorators.py`)

- **FR-006**: `Tool` is a dataclass with fields: `name: str`, `description: str`,
  `parameters: dict` (JSON Schema object), `_fn: Callable | None`,
  `_source: str | None`, `_dependencies: list[str]`.
- **FR-007**: `Tool.to_config() -> dict` must return the tool descriptor in the `tools[]`
  array format expected by `POST /v1/responses` (name, description, parameters only — no
  source code).
- **FR-008**: `Tool.to_bundle() -> dict` must return the full deployment bundle:
  descriptor + source code string + dependencies list. Used by `deploy()`.
- **FR-009**: `Tool.from_config(d: dict) -> Tool` must reconstruct a `Tool` from a
  descriptor dict (no `_fn`, no source). Used by the Runner to deserialise registered tools.
- **FR-010**: `Tool.invoke(**kwargs) -> object` must call `_fn` if present, or raise
  `RuntimeError` if `_fn` is `None` (Runner-side reconstructed tools call via materialised
  function, not `_fn`).
- **FR-011**: `Tool.deploy(client: ResponsesClient) -> None` must call
  `POST /internal/v1/tools` with the tool bundle. Idempotent: same schema → no-op;
  schema changed → warn and re-register.
- **FR-012**: The `@tool` decorator signature is `@tool(dependencies: list[str] = [])`.
  Applied to a Python function, it must:
  - Extract the function name and docstring as `name` and `description`.
  - Derive the JSON Schema from Python type annotations using `pydantic`.
  - Capture source code via `inspect.getsource()` and store it in `_source`.
  - Store `dependencies` in `_dependencies`.
  - Return a `Tool` instance.

  ```python
  @tool(dependencies=["requests"])
  def get_weather(location: str) -> dict:
      """Return current weather for a location."""
      import requests
      ...

  # get_weather is now a Tool; calling get_weather.invoke(location="NYC")
  # still calls the original function.
  ```

  The `@tool` form without parentheses (i.e. `@tool` directly on a function) must also
  be supported for the zero-dependencies case.

### Agent base class (`models/agent.py`)

- **FR-013**: `Agent` is an abstract base class with:
  - Constructor fields: `name: str`, `instructions: str`, `tools: list[Tool]`,
    `model: str`, `policy: AgentPolicy`.
  - Hook methods (all no-ops/placeholders in the base): `_before_turn()`, `_after_turn()`,
    `_build_context() -> list[dict]`, `_prune_messages(messages: list[dict]) -> list[dict]`.
  - Serialisation class methods: `to_config() -> dict`, `from_config(d: dict) -> Agent`,
    `to_yaml() -> str`, `from_yaml(s: str) -> Agent`.
  - `Agent` itself is not domain-specific: it has no preset instructions and no preset
    tools. All defaults are empty or neutral.
- **FR-014**: `AgentPolicy` is a dataclass with fields: `max_tool_calls: int` (default 10),
  `parallel_tool_calls: bool` (default True), `temperature: float` (default 1.0).
- **FR-015**: `Agent.deploy(client: ResponsesClient) -> None` must call `tool.deploy(client)`
  for every tool in `self.tools`. Built-in tools (tools that came from the Agent subclass,
  identified by `_is_builtin = True`) must be skipped — they are already present in the
  Runner at startup.

### CUAAgent subclass (`models/cua_agent.py`)

- **FR-016**: `CUAAgent` extends `Agent` with:
  - `_BUILTIN_TOOLS: ClassVar[list[Tool]]` — the five CUA tools: `screenshot`,
    `click_at`, `type_text`, `hotkey`, `find_element`. Each has `_is_builtin = True`.
  - `_BASE_INSTRUCTIONS: ClassVar[str]` — base system prompt for computer use tasks.
  - Constructor: `__init__(tools: list[Tool] = [], append_instructions: str = "",
    override_builtin_tools: list[Tool] | None = None, **kwargs)`. User-provided `tools`
    are merged with (or replaced by) built-in tools depending on
    `override_builtin_tools`.
  - `CUAAgent` passes the merged tool list and combined instructions to `super().__init__`.
- **FR-017**: The five built-in CUA tools must be implemented in `tools/cua/`. Each is
  decorated with `@tool` and has `_is_builtin = True`. They must be importable from
  `tinycua_sdk.tools.cua`.

### AgentClient (`clients/agent_client.py`)

- **FR-018**: `AgentClient` accepts a `ResponsesClient` and operates in two modes:

  **Mode A — client-orchestrated** (default when no `session_id` is provided and
  `server_orchestrated=False`):
  - `AgentClient.run(agent, user_input) -> Response`: runs the multi-turn
    function-calling loop locally. Calls `tool.invoke(**args)` directly in-process.
    No Runner involvement from the client side.
  - Suitable for local development and testing.

  **Mode B — server-orchestrated** (`server_orchestrated=True` or `session_id` is set):
  - `AgentClient.run(agent, user_input, session_id=...) -> Response`: sends a single
    `POST /v1/responses` with `session_id` in the request and does not run a local
    loop. The backend owns orchestration, tool execution, and history persistence.
  - Tools used in Mode B must be deployed to the Runner beforehand via `agent.deploy()`.

- **FR-019**: `AgentClient.stream(agent, user_input, ...) -> Iterator[StreamEvent]`
  must mirror `run()` for both modes, yielding SSE events.

### CLI (`cli/`)

- **FR-020**: The package must install a `tinycua` entry point (via `pyproject.toml
  [project.scripts]`).
- **FR-021**: `tinycua` invoked with no arguments must launch an interactive REPL built
  with `prompt_toolkit` and `rich`.
- **FR-022**: Non-interactive commands:
  - `tinycua run <file>` — execute a Python script that uses the SDK.
  - `tinycua deploy <file>` — load and deploy all `@tool`-decorated objects from a file.
- **FR-023**: REPL commands:
  - `/help` — list available commands.
  - `/connect <url> [--api-key <key>]` — connect to a backend instance.
  - `/status` — show connection status and authenticated user.
  - `/agents` — list agents available on the connected backend.
  - `/run <file>` — run a script in the current REPL context.
  - `/chat <agent-name>` — start a chat session with an agent.
  - `/deploy <file>` — deploy tools from a file to the connected Runner.
  - `/quit` — exit the REPL.
- **FR-024**: REPL `/chat` behaviour:
  - Without a backend connection: Mode A (local loop, ephemeral, dev only).
  - With a backend connection: Mode B (backend handles session and persistence).
- **FR-025**: Persistent config stored at `~/.tinycua/config.yaml` (last `base_url`,
  last `api_key`). Config loaded at REPL startup.

### Types (`models/`)

- **FR-026**: All request/response dataclasses must be importable from `tinycua_sdk.models`.
  Key types: `ResponseRequest`, `Response`, `OutputItem`, `FunctionCallItem`,
  `FunctionCallOutputItem`, `MessageItem`, `StreamEvent`, `Usage`, `Tool`, `Agent`,
  `CUAAgent`, `AgentPolicy`.
- **FR-027**: All types must be serialisable to/from JSON (use `pydantic` models or
  `dataclasses` + `dacite`; to be decided before implementation).

---

## Example Usage (expected developer experience)

### Define and run a simple tool-using agent (Mode A)

```python
from tinycua_sdk.tools import tool
from tinycua_sdk.models.agent import Agent, AgentPolicy
from tinycua_sdk.clients.agent_client import AgentClient
from tinycua_sdk.clients.client import ResponsesClient

@tool
def get_weather(location: str) -> dict:
    """Return current weather for a location."""
    return {"temp": 72, "unit": "F", "condition": "sunny"}

client = ResponsesClient(base_url="http://localhost:8000", api_key="my-key")

agent = Agent(
    name="weather-agent",
    instructions="You are a weather assistant.",
    tools=[get_weather],
    model="tinycua-gguf-7b",
    policy=AgentPolicy(max_tool_calls=5),
)

agent_client = AgentClient(client)
response = agent_client.run(agent, user_input="What's the weather in NYC?")
print(response.output_text)
```

### Deploy tools and run server-orchestrated (Mode B)

```python
agent.deploy(client)   # uploads get_weather bundle to Runner

response = agent_client.run(
    agent,
    user_input="What's the weather in NYC?",
    session_id="sess_abc123",   # backend owns the loop + saves history
)
print(response.output_text)
```

### CUAAgent with extra tools

```python
from tinycua_sdk.models.cua_agent import CUAAgent

@tool
def open_app(name: str) -> dict:
    """Open a desktop application by name."""
    ...

cua_agent = CUAAgent(
    name="desktop-agent",
    tools=[open_app],                  # merged with built-in CUA tools
    append_instructions="Focus on productivity apps.",
    model="tinycua-gguf-7b",
)

cua_agent.deploy(client)   # deploys open_app only; built-ins already in Runner
```

### Streaming

```python
for event in agent_client.stream(agent, user_input="What's the weather in NYC?"):
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
```

---

## Acceptance Scenarios

### Scenario 1 — Non-streaming single-turn call
```
Given ResponsesClient pointed at a MockBackend
When client.create(ResponseRequest(model="m", input=[user_msg]))
Then returns Response with output[0].type = "message"
And output[0].role = "assistant"
And usage.total_tokens > 0
```

### Scenario 2 — Streaming single-turn call
```
Given stream=True
When client.stream(request)
Then yields StreamEvent(type="response.created") first
Then yields one or more StreamEvent(type="response.output_text.delta")
Then yields StreamEvent(type="response.completed") last
```

### Scenario 3 — Mode A local function-calling loop
```
Given AgentClient with get_weather tool, server_orchestrated=False
And MockBackend returns function_call for "get_weather" on first call
And MockBackend returns final text message on second call
When agent_client.run(agent, "Weather in NYC?")
Then get_weather was called exactly once with location="NYC"
And final Response.output_text contains weather info
And no deploy() call was made
```

### Scenario 4 — Mode B server-orchestrated
```
Given agent deployed to Runner (get_weather bundle uploaded)
And session_id="sess_abc123" provided
When agent_client.run(agent, "Weather in NYC?", session_id="sess_abc123")
Then exactly one POST /v1/responses is made (with session_id in body)
And no local tool.invoke() is called
And final Response.output_text contains weather info
```

### Scenario 5 — @tool decorator extracts schema and source
```
Given:
  @tool
  def add(a: int, b: int) -> int:
      """Add two numbers."""
      return a + b
Then add.name == "add"
And add.description == "Add two numbers."
And add.parameters == {
  "type": "object",
  "properties": { "a": {"type":"integer"}, "b": {"type":"integer"} },
  "required": ["a", "b"]
}
And add._source contains the source code of the function
And add._dependencies == []
```

### Scenario 6 — @tool with dependencies
```
Given:
  @tool(dependencies=["requests"])
  def fetch_url(url: str) -> str:
      """Fetch a URL and return the response body."""
      import requests
      return requests.get(url).text
Then fetch_url._dependencies == ["requests"]
And fetch_url.to_bundle() contains { "source": "...", "dependencies": ["requests"] }
```

### Scenario 7 — tool.deploy() is idempotent
```
Given tool "get_weather" already deployed (same schema)
When get_weather.deploy(client) called again
Then no exception raised
And no duplicate registration on Runner
```

### Scenario 8 — CUAAgent tool list
```
Given CUAAgent(tools=[open_app])
Then agent.tools contains open_app AND all 5 built-in CUA tools
And open_app._is_builtin is False (or absent)
And screenshot._is_builtin is True
```

### Scenario 9 — agent.deploy() skips built-ins
```
Given CUAAgent(tools=[open_app])
When cua_agent.deploy(client)
Then only open_app.deploy(client) is called
And none of the 5 built-in tools trigger a deploy call
```

### Scenario 10 — CLI REPL starts
```
When `tinycua` is invoked with no arguments
Then an interactive REPL is displayed
And typing /help lists all REPL commands
And typing /quit exits cleanly
```

---

## Testing Plan

- **Unit**: `@tool` schema extraction (various type annotations), `@tool(dependencies=[])`
  form, `Tool.to_config()` / `to_bundle()` / `from_config()`, `AgentPolicy` defaults,
  `ResponsesClient` retry logic (mock HTTP), SSE event parsing, `CUAAgent` tool merge logic,
  `agent.deploy()` skips built-ins.
- **Integration**: `AgentClient.run()` Mode A with a MockBackend that returns a
  `function_call` followed by a final message — assert the loop ran correctly end-to-end.
  `AgentClient.run()` Mode B — assert exactly one HTTP call is made.
- **Contract**: assert `ResponseRequest` and `Response` dataclasses round-trip through JSON
  without data loss.
- **CLI**: smoke-test `tinycua --help`, `tinycua run <script>`, REPL `/help` output.

---

## Open Questions

- **OQ-001**: Schema derivation library — `pydantic` (heavier, more features) or
  `inspect`+manual (lighter)? Recommendation: `pydantic` for correctness and future
  compatibility with structured outputs.
- **OQ-002**: `Agent` base class architectural hooks (`_build_context`, `_prune_messages`)
  will be no-ops until the paper MD is delivered. Should the spec name these hooks
  explicitly or leave them as a TBD extension point? Recommendation: name them explicitly
  as no-ops so the class hierarchy is stable.
- **OQ-003**: Should `to_yaml()` / `from_yaml()` use PyYAML or `ruamel.yaml`?
  Recommendation: PyYAML for simplicity in MVP; ruamel.yaml only if round-trip comment
  preservation is needed.
