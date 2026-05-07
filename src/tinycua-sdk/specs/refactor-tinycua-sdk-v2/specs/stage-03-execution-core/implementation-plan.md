# Implementation: Stage 3 — LLM Client & Basic Execution Loop

Implement the real LLM client (OpenAI-compatible via httpx), the full `BaseLoop.run()` execution flow with tool calling, `ToolExecutor` with permission/approval checks, a redesigned `ApprovalWorkflow` ABC, and `Agent.run()` with cancellation support. Non-streaming only.

## Context

- **Spec Reference**: `spec.md`
- **Design Reference**: `design.md`
- **Priority**: P0
- **Estimated Effort**: L

## Proposed Changes

### 1. New File: LLM Client (ABC + OpenAI Implementation)

#### [NEW] `tinycua_sdk/agent/llm_client.py`

- **LLMClient ABC**: Defines `async def chat(messages, tools, model_config) -> dict` returning normalized `{content, tool_calls, usage}`.
- **OpenAICompatibleClient**: Concrete implementation using `httpx.AsyncClient`.
  - Lazy `_get_client(model_config)` with `base_url` from `LanguageModel.base_url` (defaults to `https://api.openai.com/v1`), `Authorization` header from `api_key.get_secret_value()`.
  - `chat()` builds payload with `model`, `messages`, plus optional fields (`temperature`, `max_tokens`, `top_p`, `frequency_penalty`, `presence_penalty`, `stop`, `seed`, `response_format`, `tool_choice`, `logprobs`, `top_logprobs`, `user`).
  - Adds `tools` array and `tool_choice="auto"` default when tools present.
  - Parses response JSON into normalized dict.
  - Raises `httpx.HTTPStatusError` on non-2xx.

### 2. New File: ToolExecutor

#### [NEW] `tinycua_sdk/agent/executor.py` (rewrite)

- **ToolExecutor**: Static `execute(tool, arguments, agent)` method.
  - Permission check via `agent.tool_permissions.get(tool.name, "allow")`.
  - If `"deny"`: return `{"error": ...}`.
  - If `"ask"`: call `agent.approval_workflow.request_approval()`, return denial dict if not approved.
  - If `"allow"`: call `tool.invoke(**arguments)` and return result.
- **AgentExecutor**: Adds `_cancelled` flag, `is_cancelled` property, `cancel()` method, `_get_llm_client()` (lazy `OpenAICompatibleClient` instance), and `_call_llm(messages, tools)` protected helper.

### 3. New File: BaseLoop (Full Implementation)

#### [NEW] `tinycua_sdk/agent/loop.py` (rewrite)

- **BaseLoop**: `__init__(max_iterations=5)`.
  - `_build_system_message(agent, override_instructions=None)`: Builds system message from agent instructions + skill instructions.
  - `run(agent, messages, tools, override_instructions=None)`:
    1. Prepend system message.
    2. Iterate up to `max_iterations`.
    3. Check cancellation — raise `asyncio.CancelledError`.
    4. Check `tool_call_count >= agent.policy.max_tool_calls` — break.
    5. Call `agent._call_llm(messages, tools)`.
    6. Append assistant message (with tool_calls if present).
    7. If tool_calls: parse JSON args, look up tool, execute via `ToolExecutor`, append tool result messages, increment count, continue.
    8. If no tool_calls: return content string.
    9. After loop: return last content or `"[max iterations reached]"`.

### 4. New File: ApprovalWorkflow (Redesign)

#### [NEW] `tinycua_sdk/security/approval.py` (rewrite)

- **ApprovalWorkflow(ABC)**: `async def request_approval(tool_name, arguments) -> dict`.
- **DefaultApprovalWorkflow**: Returns `{"approved": True}`.
- Remove old `ApprovalRequest` dataclass and sync `ApprovalWorkflow` — replaced by the ABC design.

### 5. Modify: `tinycua_sdk/agent/agent.py`

#### [MODIFY] Agent class — Add `run()` method

- `async def run(query, messages=None, instructions=None, stream="off") -> str`:
  - Raise `NotImplementedError` if `stream != "off"`.
  - Build `loop = self.config.loop or BaseLoop()`.
  - Build message list: `(messages or []) + [{"role": "user", "content": query}]`.
  - Call `await loop.run(self, msgs, self.tools, instructions)`.
  - Return result string.

### 6. Modify: AgentExecutor — Remove stub run()

#### [MODIFY] `tinycua_sdk/agent/executor.py`

- Remove the existing stub `async def run()` that raises `NotImplementedError`.
- Instead, `AgentExecutor` becomes a mixin providing cancellation, LLM client, and `_call_llm()` — actual `run()` lives on `Agent`.

### 7. Update Exports

#### [MODIFY] `tinycua_sdk/agent/__init__.py`

- Add `LLMClient` export (from `llm_client` module).

#### [MODIFY] `tinycua_sdk/__init__.py`

- No changes needed — `Agent`, `BaseLoop`, etc. already exported.

#### [MODIFY] `tinycua_sdk/security/__init__.py`

- Update exports to include `DefaultApprovalWorkflow`.

### 8. Update Conftest Fixtures

#### [MODIFY] `tests/integration/conftest.py`

- Update `mock_llm_client` and `mock_llm_with_tool_calls` fixtures to patch `OpenAICompatibleClient` (instead of the old non-existent `LLMClient` on `executor`). The fixtures should mock `httpx.AsyncClient.post` to return fake `httpx.Response` objects with the correct normalized response format.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `LLMClient` | New | Abstract base for LLM API clients |
| `OpenAICompatibleClient` | New | httpx-based OpenAI-compatible implementation |
| `ToolExecutor` | New | Static tool execution with permission/approval checks |
| `BaseLoop.run()` | Modify | Full execution flow with tool calling, cancellation, max iterations |
| `ApprovalWorkflow` | Modify | Redesign from concrete class with sync methods to ABC with async `request_approval` |
| `DefaultApprovalWorkflow` | New | Always-approve implementation |
| `Agent.run()` | New | Public convenience wrapper calling BaseLoop |
| `AgentExecutor` | Modify | Add `_cancelled`, `_llm_client`, `_call_llm()`; remove stub `run()` |
| `AgentConfig` | Unchanged | Already has `loop`, `tool_permissions`, `approval_workflow` fields |

## Data Model Changes

```python
# Normalized LLM response dict
{
    "content": str | None,
    "tool_calls": list[dict] | None,  # OpenAI tool call format
    "usage": dict | None,
}

# Tool call item format
{
    "id": str,
    "type": "function",
    "function": {
        "name": str,
        "arguments": str,  # JSON string
    }
}

# Approval workflow return
{"approved": bool, ...}
```

## Verification Plan

### Automated Tests

- [ ] Unit tests for `OpenAICompatibleClient.chat()` with mocked httpx
- [ ] Unit tests for `ToolExecutor.execute()` covering allow/deny/ask paths
- [ ] Unit tests for `BaseLoop.run()` with mocked `_call_llm`
- [ ] Unit tests for `Agent.run()` with mocked loop
- [ ] Unit tests for `DefaultApprovalWorkflow.request_approval()`
- [ ] Integration tests: `test_gs_03_agent_calling.py` (6 success criteria)
- [ ] Integration tests: `test_int_03_agent_with_tools.py` (tool calling + dynamic tools)
- [ ] Un-skip existing loop execution tests in `test_loop_execution.py`

### Manual Verification

- [ ] Run target scripts against a real LM Studio / Ollama server
- [ ] Verify cancellation by running `targets/04_cancellation.py`

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| httpx | >=0.27.0 | Already in pyproject.toml — HTTP client for LLM API |

### Internal Dependencies

- [ ] Depends on: Stages 0–2 (Agent, AgentConfig, AgentPolicy, LanguageModel, Tool, BaseLoop stub)
- [ ] Blocks: Stages 4–9 (all subsequent stages build on working execution loop)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| httpx response parsing differs from OpenAI spec | High | Write resilient parser; integration tests against real server |
| Cancellation race condition | Medium | Check `is_cancelled` at start of each iteration, not mid-request |
| Permission/approval flow blocks execution | Low | Default "allow" preserves backward compatibility |
| Instruction override design ambiguity | Medium | Use `override_instructions` parameter on `BaseLoop.run()` (Option 1 from design) |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-06*
