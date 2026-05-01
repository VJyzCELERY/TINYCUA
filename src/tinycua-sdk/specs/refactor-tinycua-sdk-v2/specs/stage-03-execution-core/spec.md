# Stage 3: LLM Client & Basic Execution Loop — Specification

## Objective
The agent can actually call an LLM and return a response. This includes:
1. A real LLM client implementation (not a stub).
2. A working execution loop that handles tool calls.
3. Tool execution with permission/approval checks.
4. Cancellation support.

Non-streaming only. Streaming is Stage 5.

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

### SC-3.1: Agent.run Returns String
**What:** `agent.run("What is the capital of France?")` returns a `str`.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
r = asyncio.run(a.run('Say hello.'))
assert isinstance(r, str)
print('PASS')
"
```
**Pass if:** prints `PASS`. Requires local LLM server running.

### SC-3.2: Agent.run with History
**What:** `messages` parameter is respected.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
r = asyncio.run(a.run('What is my name?', messages=[{'role': 'user', 'content': 'My name is Alice.'}, {'role': 'assistant', 'content': 'Hello Alice.'}]))
assert 'Alice' in r
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-3.3: Agent.run with Instruction Override
**What:** Runtime instruction override works.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
r = asyncio.run(a.run('Tell me a joke.', instructions='You are a pirate.'))
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-3.4: Cancellation
**What:** `agent.cancel()` cancels an in-flight run.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
task = asyncio.create_task(a.run('Write a long essay.'))
await asyncio.sleep(0.1)
a.cancel()
try:
    await task
except asyncio.CancelledError:
    print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-3.5: Tool Calling Loop
**What:** Agent with tools correctly invokes them.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, tool

@tool
def calculator(expression: str) -> str:
    return str(eval(expression, {'__builtins__': {}}, {}))

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), tools=[calculator], instructions='You have a calculator.')
r = asyncio.run(a.run('What is 135 * 42?'))
assert '5670' in r
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-3.6: Dynamic add_tools
**What:** Tools added after creation work.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, tool

@tool
def convert(amount: float, from_c: str, to_c: str) -> str:
    return f'{amount} {from_c} = {amount} {to_c}'

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
a.add_tools(convert)
r = asyncio.run(a.run('Convert 100 USD to EUR.'))
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-3.7: Integration Tests Pass
**What:** Both Stage 3 integration tests pass.  
**How to check:**
```bash
cd src/tinycua-sdk && pytest tests/integration/goals/test_gs_03_agent_calling.py tests/integration/goals/test_int_03_agent_with_tools.py -v
```
**Pass if:** 2 passed, 0 failed.

## Integration Test Files
- `tests/integration/goals/test_gs_03_agent_calling.py`
- `tests/integration/goals/test_int_03_agent_with_tools.py`
