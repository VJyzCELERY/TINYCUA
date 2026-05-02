# Stage 3: LLM Client & Basic Execution Loop — Specification

## Objective
The agent can actually call an LLM and return a response. This includes:
1. A real LLM client implementation (not a stub).
2. A working execution loop that handles tool calls.
3. Tool execution with permission/approval checks.
4. Cancellation support.

Non-streaming only. Streaming is Stage 5.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

## References
- [`goals/getting-started/03_agent_calling.py`](../goals/getting-started/03_agent_calling.py)
- [`goals/intermediate/03_agent_with_tools.py`](../goals/intermediate/03_agent_with_tools.py)

## Requirements

### R-3.1: LLMClient ABC

```python
class LLMClient(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: LanguageModel,
    ) -> dict:
        """Send messages to LLM and return normalized response.

        Returns:
            {
                "content": str | None,
                "tool_calls": list[dict] | None,
                "usage": dict | None,
            }
        """
```

### R-3.2: OpenAICompatibleClient

Concrete implementation using `httpx` (not the `openai` package, to keep dependencies minimal):

- Builds a `chat/completions` request.
- Forwards `model_config` fields to request body:
  - `model`, `messages`, `temperature`, `max_tokens`, `top_p`, `frequency_penalty`, `presence_penalty`, `stop`, `seed`, `response_format`, `tool_choice`, `logprobs`, `top_logprobs`, `user`
- If `tools` is provided, adds `tools` array to request.
- If `tool_choice` is set on `LanguageModel`, uses that; otherwise defaults to `"auto"` when tools are present.
- Parses response into normalized dict:
  ```python
  {
      "content": choice.message.content,
      "tool_calls": [
          {
              "id": tc.id,
              "type": "function",
              "function": {
                  "name": tc.function.name,
                  "arguments": tc.function.arguments,  # JSON string
              }
          }
          for tc in (choice.message.tool_calls or [])
      ] or None,
      "usage": response.usage.model_dump() if response.usage else None,
  }
  ```
- Handles `base_url` for local servers (e.g., LM Studio, Ollama).
- Handles API key from `LanguageModel.api_key` (via `get_secret_value()`).

### R-3.3: BaseLoop.run() — Real Implementation

```python
async def run(
    self,
    agent: Agent,
    messages: list[dict],
    tools: list[Tool],
) -> str:
```

**Execution flow:**
1. Build system message from `agent.instructions` + skill instructions.
2. Prepend system message to `messages`.
3. For iteration in `range(self.max_iterations)`:
   a. If `agent.is_cancelled`: raise `asyncio.CancelledError`.
   b. If tool_call_count >= `agent.policy.max_tool_calls`: break.
   c. Call LLM via `agent._call_llm(messages, tools)`.
   d. If response has `content`: append assistant message to history.
   e. If response has `tool_calls`:
      - Parse each tool call JSON arguments.
      - Look up tool by name in `agent.tools`.
      - Execute via `ToolExecutor.execute(tool, args, agent)`.
      - Append tool results to messages.
      - Increment tool_call_count.
      - Continue loop.
   f. If no tool calls: return `content`.
4. If max iterations reached: return last `content` or a cancellation marker.

### R-3.4: ToolExecutor

```python
class ToolExecutor:
    @staticmethod
    async def execute(tool: Tool, arguments: dict, agent: Agent) -> Any:
        # 1. Permission check
        permission = agent.tool_permissions.get(tool.name, "allow")
        if permission == "deny":
            return {"error": f"Tool '{tool.name}' is denied by permission map."}

        # 2. Approval check
        if permission == "ask" and agent.approval_workflow:
            approval = await agent.approval_workflow.request_approval(tool.name, arguments)
            if not approval.get("approved"):
                return approval  # Return denial dict

        # 3. Execute
        return tool.invoke(**arguments)
```

### R-3.5: ApprovalWorkflow (Redesigned)

```python
class ApprovalWorkflow(ABC):
    @abstractmethod
    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        """Return {"approved": bool, ...}."""

class DefaultApprovalWorkflow(ApprovalWorkflow):
    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        return {"approved": True}
```

### R-3.6: Agent.run()

```python
async def run(
    self,
    query: str,
    messages: list[dict] | None = None,
    instructions: str | None = None,
    stream: Literal["off", "event", "token", "all"] = "off",
) -> str:
```

- `stream` must be `"off"` in this stage (streaming implemented in Stage 5).
- `messages` prepends conversation history before the query.
- `instructions` overrides the agent's default instructions for this run only.
- Returns the final response string.

### R-3.7: Agent._call_llm()

Protected helper for custom loops:
```python
async def _call_llm(self, messages: list[dict], tools: list[Tool] | None = None) -> dict:
    client = self._get_llm_client()  # lazily instantiated
    tool_schemas = [t.to_config() for t in tools] if tools else None
    return await client.chat(messages, tool_schemas, self.llm_model)
```

### R-3.8: Cancellation

```python
def cancel(self) -> None:
    self._cancelled = True
```

The loop checks `agent.is_cancelled` at the start of each iteration.

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] Agent.run Returns String - tests/integration/goals/test_gs_03_agent_calling.py - PASS - `print('PASS')`
  Description: `agent.run("What is the capital of France?")` returns a `str`.

- [ ] Agent.run with History - tests/integration/goals/test_gs_03_agent_calling.py - PASS - `print('PASS')`
  Description: `messages` parameter is respected.

- [ ] Agent.run with Instruction Override - tests/integration/goals/test_gs_03_agent_calling.py - PASS - `print('PASS')`
  Description: Runtime instruction override works.

- [ ] Cancellation - tests/integration/goals/test_gs_03_agent_calling.py - PASS - `print('PASS')`
  Description: `agent.cancel()` cancels an in-flight run.

- [ ] Tool Calling Loop - tests/integration/goals/test_int_03_agent_with_tools.py - PASS - `print('PASS')`
  Description: Agent with tools correctly invokes them.

- [ ] Dynamic add_tools - tests/integration/goals/test_int_03_agent_with_tools.py - PASS - `print('PASS')`
  Description: Tools added after creation work.

- [ ] Integration Tests Pass - tests/integration/goals/test_gs_03_agent_calling.py, tests/integration/goals/test_int_03_agent_with_tools.py - 2 passed, 0 failed - pytest -v

## Integration Test Files
- `tests/integration/goals/test_gs_03_agent_calling.py`
- `tests/integration/goals/test_int_03_agent_with_tools.py`
