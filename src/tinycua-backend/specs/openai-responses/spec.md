# Specification: OpenAI Responses API Compatibility Layer

## Problem Statement

TINYCUA backend must expose a single, stable HTTP API that clients (SDK, external tools) can
use to converse with any supported LLM provider (Ollama, LM Studio, and optionally OpenAI
itself). Clients should not have to know or care which provider backs a model. The public
surface must be wire-compatible with the OpenAI Responses API so that any OpenAI-compatible
SDK can be pointed at the backend without modification.

The backend also owns the function-calling orchestration loop: when a provider response
contains a `function_call` output item, the backend must invoke the appropriate tool via
the Runner (see `runner-integration` spec), inject the result back into the conversation,
and continue calling the provider until a final assistant message or the max-call depth is
reached.

---

## Scope

Included in this spec:
- Public `POST /v1/responses` endpoint (non-streaming and SSE streaming).
- Provider adapter layer (Ollama, LM Studio, OpenAI pass-through).
- Model registry: mapping `model` name → provider type + endpoint + options.
- Function/tool-calling orchestration loop.
- Request validation, error handling, auth middleware.
- Structured logging and `trace_id` propagation.

Excluded from this spec (separate specs):
- Backend ↔ Runner internal API — see `runner-integration` spec.
- SDK client — see `agent-tool-abstraction` spec.
- Fine-tuning pipeline — see `tinycua-finetune` spec.

---

## Requirements

### Public API surface

- **FR-001**: Expose `POST /v1/responses` accepting a JSON body that is a strict subset of
  the OpenAI Responses API request schema (fields: `model`, `input`, `tools`, `stream`,
  `temperature`, `max_output_tokens`, `tool_choice`, `metadata`, `previous_response_id`,
  `instructions`).
- **FR-002**: Return a Response object whose shape matches the OpenAI Responses API response
  schema (fields: `id`, `object`, `created_at`, `status`, `model`, `output`, `usage`,
  `incomplete_details`, `error`).
- **FR-003**: Support SSE streaming when `stream: true`. Emit the standard streaming events:
  `response.created`, `response.output_item.added`, `response.output_text.delta`,
  `response.output_text.done`, `response.output_item.done`, `response.completed`.
- **FR-004**: Accept `Authorization: Bearer <token>` header where `<token>` is either a
  JWT access token or a user-scoped API key. Reject requests without a valid credential
  with `401 Unauthorized`. Auth validation is delegated to the auth middleware defined in
  the `auth-session` spec.
- **FR-005**: Return standard OpenAI-compatible error bodies on 4xx/5xx:
  ```json
  { "error": { "code": "invalid_request", "message": "..." } }
  ```

### Model registry

- **FR-006**: Maintain a model registry (config file or environment) that maps model names
  to provider type, endpoint URL, and optional per-model parameters (temperature default,
  context length, etc.).
- **FR-007**: Return `404` with a clear error message if the requested model is not found in
  the registry.

### Provider adapters

- **FR-008**: Implement a provider adapter for **Ollama** that translates the canonical
  request to Ollama's `/api/chat` (or `/api/generate`) format and normalises the response
  back to the OpenAI Responses shape.
- **FR-009**: Implement a provider adapter for **LM Studio** that uses LM Studio's
  OpenAI-compatible `/v1/chat/completions` endpoint and maps `choices[0]` → `output[]`.
- **FR-010**: Implement a **pass-through adapter** for OpenAI that forwards the request
  directly to `https://api.openai.com/v1/responses` (for when a real OpenAI model is
  configured).
- **FR-011**: Each adapter must handle streaming from its upstream and re-emit SSE chunks
  in the canonical streaming event format before sending them to the client.

### Session handling

- **FR-012**: `POST /v1/responses` must accept an optional `session_id` field in the
  request body. When `session_id` is present:
  - Load the full message history for that session from the database (via session service
    defined in the `auth-session` spec).
  - Prepend history to the `input[]` array before calling the provider.
  - After the final response is assembled, save the new turn (user input + assistant output)
    to the session.
  - Sessions are user-scoped: a session belonging to another user returns `404`.
- **FR-013**: When `session_id` is active, the `get_context` native tool must be
  automatically appended to the `tools[]` array sent to the provider. This tool has no
  source — it is handled directly by the backend's orchestration loop, not the Runner.
  The `get_context` tool allows the LLM to request additional context (e.g. a summary of
  earlier turns) from the session service.
- **FR-014**: When `session_id` is absent, the backend is stateless: the full conversation
  must be supplied in `input[]` on every request.

### CUA access control

- **FR-015**: Before executing any tool whose name appears in the Runner's built-in CUA
  tool list (`screenshot`, `click_at`, `type_text`, `hotkey`, `find_element`), the backend
  must verify that the authenticated user has `is_master = true`. If not, the orchestration
  loop must return `status: "incomplete"` with
  `incomplete_details.reason: "cua_access_denied"` and must not call the Runner for that
  tool.

### Function-calling orchestration

- **FR-016**: After receiving a provider response, if `output[]` contains one or more items
  of `type: "function_call"`, the backend must call the Runner's
  `POST /internal/v1/toolcall` for each call (sequentially or in parallel according to
  `parallel_tool_calls`). CUA tools require `is_master` check per FR-015.
- **FR-017**: Inject tool results back into the conversation as `function_call_output` input
  items and re-invoke the provider (continuation call).
- **FR-018**: Repeat the orchestration loop until the provider returns no further
  `function_call` items or `max_tool_calls` is exhausted. If `max_tool_calls` is exceeded,
  set `status: "incomplete"` and `incomplete_details.reason: "max_tool_calls"`.
- **FR-019**: Propagate a `trace_id` (UUID v4, generated per request) to all Runner calls
  and include it in response `metadata`.

### Observability

- **FR-020**: Log every request/response pair as a structured JSON log entry including:
  `trace_id`, `model`, `provider`, `status`, `input_tokens`, `output_tokens`,
  `latency_ms`, `tool_calls_count`. Redact `metadata` values and tool `arguments` before
  persisting.
- **FR-021**: Expose `GET /health` returning `{ "status": "ok" }` with HTTP 200.

---

## Acceptance Scenarios

### Scenario 1 — Non-streaming text response
```
Given a valid API key
And a registered model "tinycua-gguf-7b" mapped to Ollama
When POST /v1/responses with:
  { "model": "tinycua-gguf-7b",
    "input": [{"role":"user","content":"Hello"}],
    "stream": false }
Then HTTP 200
And body has "object": "response"
And body has "output[0].type": "message"
And body has "output[0].role": "assistant"
And body has "usage.input_tokens" > 0
And body has "usage.output_tokens" > 0
```

### Scenario 2 — SSE streaming response
```
Given stream: true
When the same request as Scenario 1
Then Content-Type: text/event-stream
And first event is "response.created" with status "in_progress"
And one or more "response.output_text.delta" events with non-empty "delta"
And final event is "response.completed" with status "completed" and usage populated
And "data: [DONE]" terminates the stream
```

### Scenario 3 — Function calling roundtrip
```
Given model "tinycua-gguf-7b" and a registered tool "get_weather"
When POST /v1/responses with tool in tools[] and user asks for weather
Then provider returns function_call output item
And backend calls Runner POST /internal/v1/toolcall for "get_weather"
And Runner returns { status: "success", result: { temp: 72 } }
And backend re-calls provider with function_call_output injected
And final response output contains assistant message with weather info
And response status is "completed"
```

### Scenario 4 — Unknown model
```
When POST /v1/responses with model "unknown-xyz"
Then HTTP 404
And body.error.code = "model_not_found"
```

### Scenario 5 — Auth failure
```
When POST /v1/responses without Authorization header
Then HTTP 401
And body.error.code = "unauthorized"
```

### Scenario 6 — max_tool_calls exceeded
```
Given max_tool_calls: 2
And provider keeps returning function_call items
When orchestration loop hits 2 tool calls without a final message
Then response status = "incomplete"
And incomplete_details.reason = "max_tool_calls"
```

### Scenario 7 — Session history loaded and saved
```
Given session_id = "sess_abc" with 3 prior turns in the database
And user sends POST /v1/responses with session_id = "sess_abc"
When request is processed
Then the 3 prior turns are prepended to input[] before the LLM call
And after the response is assembled, the new turn is appended to the session
And the response is returned to the client
```

### Scenario 8 — get_context tool auto-injected with session
```
Given session_id is present in the request
When POST /v1/responses is processed
Then the tools[] array sent to the provider includes "get_context"
And if the provider calls get_context, the backend handles it directly
And no Runner call is made for get_context
```

### Scenario 9 — CUA tool blocked for non-master user
```
Given authenticated user with is_master = false
And provider returns function_call for "screenshot"
When orchestration loop processes the function_call
Then Runner is NOT called
And response status = "incomplete"
And incomplete_details.reason = "cua_access_denied"
```

### Scenario 10 — CUA tool allowed for master user
```
Given authenticated user with is_master = true
And provider returns function_call for "screenshot"
When orchestration loop processes the function_call
Then Runner is called: POST /internal/v1/toolcall { tool_name: "screenshot" }
And result is injected and loop continues normally
```

---

## Testing Plan

- **Unit**: provider adapter input→output mapping (Ollama, LM Studio, pass-through), SSE
  chunk assembly/forwarding, orchestration loop logic, model registry lookup, auth
  middleware (JWT + API key), session load/save, `get_context` auto-injection,
  `is_master` CUA guard, error serialisation.
- **Integration**: end-to-end request against a MockProvider (no real LLM), asserting
  canonical response shapes (non-stream and stream). MockRunner for tool-call roundtrip.
  Session persistence (SQLite in-memory).
- **Contract**: a dedicated contract test suite asserting that every response field in
  FR-001/FR-002 is present and correctly typed regardless of provider.
- **Security**: missing credential → 401, expired JWT → 401, oversized input → 413,
  non-master user attempting CUA tool → `cua_access_denied`.

---

## Open Questions

- **OQ-001**: `previous_response_id` (OpenAI's stateful response chaining) is not
  supported. Session continuity is handled via `session_id` instead. `previous_response_id`
  in a request body must be ignored with a logged warning.
- **OQ-002**: Rate limiting strategy — per user, per model, or global? To be decided
  before implementation. Deferred to Phase 2.
- **OQ-003**: The backend is no longer stateless in MVP: it reads and writes session data
  via SQLite (delegated to the session service in `auth-session`). This is intentional.
  The `store: false` behaviour from OQ-003 original is superseded by the session design.
