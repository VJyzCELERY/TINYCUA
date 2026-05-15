# Stage 8: Extensibility — Custom Loops — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-08-custom-loops/spec.md`

## Why No Hook System?

The previous codebase had a hook system (`add_pre_hook()`, `add_post_hook()`) that was completely unwired — hooks could be registered but never executed. Instead of fixing this complex system, we remove it entirely.

**Customization path:**
```python
class MyLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        # Full control over execution
        # Can call agent._call_llm() when needed
        # Can modify messages
        # Can add custom iteration logic
        return "result"
```

This is simpler, more powerful, and has zero hidden behavior.

## BaseLoop Implementation

```python
# tinycua_sdk/agent/loop.py

from typing import AsyncIterator

class BaseLoop:
    """Standard tool-calling execution loop. Subclass to customize."""

    def __init__(self, max_iterations: int = 5) -> None:
        self.max_iterations = max_iterations

    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict]:
        """Default implementation.

        When stream=False: returns str.
        When stream=True: returns AsyncIterator[dict].
        """
        if not stream:
            return await self._run_sync(agent, messages, tools, override_instructions)
        return self._run_stream(agent, messages, tools, override_instructions)

    async def _run_sync(self, agent, messages, tools, override_instructions):
        # Full implementation from Stage 3 + Stage 4 + Stage 5
        ...

    async def _run_stream(self, agent, messages, tools, override_instructions):
        # Full implementation from Stage 5
        ...
```

## agent._call_llm()

```python
# On Agent class (in agent.py)

async def _call_llm(
    self,
    messages: list[dict],
    tools: list[Tool] | None = None,
) -> dict[str, Any]:
    """Protected helper for custom loops.

    Calls the LLM with the agent's configuration and returns
    a normalized response dict.
    """
    client = self._get_llm_client()
    tool_schemas = [t.to_config() for t in tools] if tools else None
    return await client.chat(messages, tool_schemas, self.llm_model)
```

**Why protected?**
- It's part of the subclassing contract.
- It's not in the public consumer API.
- Single underscore signals "internal but stable for subclasses".

## Custom Loop Example: ReActLoop

```python
import json
from tinycua_sdk import BaseLoop, ToolExecutor

class ReActLoop(BaseLoop):
    """ReAct-style loop: forces reasoning before acting."""

    def __init__(self, max_iterations: int = 5, format_hint: str = "ReAct"):
        super().__init__(max_iterations=max_iterations)
        self.format_hint = format_hint

    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        if stream:
            raise NotImplementedError("ReActLoop does not support streaming yet")

        # Inject ReAct formatting hint
        hint = self.format_hint
        if not any(m.get("role") == "system" and f"{hint} format" in m.get("content", "") for m in messages):
            messages.insert(0, {
                "role": "system",
                "content": f"You must follow {hint} format. First reason with 'Think: ...' then act with 'Act: ...'.",
            })

        for iteration in range(self.max_iterations):
            if agent.is_cancelled:
                return "[cancelled]"

            response = await agent._call_llm(messages, tools)
            content = response.get("content", "")

            # Parse ReAct format
            if "Act:" in content:
                think_part, act_part = content.split("Act:", 1)
                action = act_part.strip()

                if action.startswith("{"):
                    # Tool call
                    call = json.loads(action)
                    tool_name = call["name"]
                    arguments = call.get("arguments", {})

                    # Find and execute tool
                    for t in tools:
                        if t.name == tool_name:
                            result = await ToolExecutor.execute(t, arguments, agent)
                            messages.append({"role": "assistant", "content": content})
                            messages.append({"role": "tool", "content": str(result), "name": tool_name})
                            break
                    else:
                        return f"Unknown tool: {tool_name}"
                else:
                    return action
            else:
                return content

        return "[max iterations reached]"
```

## Custom Loop Example: PlanThenExecuteLoop

```python
from tinycua_sdk import BaseLoop, ToolExecutor

class PlanThenExecuteLoop(BaseLoop):
    """Two-phase loop: plan first, then execute."""

    def __init__(self, max_iterations: int = 5, plan_temperature: float = 0.3):
        super().__init__(max_iterations=max_iterations)
        self.plan_temperature = plan_temperature

    async def run(self, agent, messages, tools, override_instructions=None, stream: bool = False):
        if stream:
            raise NotImplementedError("PlanThenExecuteLoop does not support streaming yet")

        # Phase 1: Planning
        plan_messages = messages + [{
            "role": "system",
            "content": "First, outline a step-by-step plan. Do not execute yet.",
        }]

        # Temporarily lower temperature for planning
        original_temp = agent.llm_model.temperature
        # Note: modifying agent.llm_model directly won't work (frozen Pydantic model)
        # Custom loops should create a copy if they need to modify model config
        # For now, this example shows intent; actual implementation uses model_copy()

        plan_response = await agent._call_llm(plan_messages)
        plan = plan_response.get("content", "")

        # Phase 2: Execution
        exec_messages = messages + [
            {"role": "assistant", "content": plan},
            {"role": "system", "content": "Now execute the plan above step by step."},
        ]

        for _ in range(self.max_iterations):
            if agent.is_cancelled:
                return "[cancelled]"

            response = await agent._call_llm(exec_messages, tools)
            content = response.get("content", "")
            exec_messages.append({"role": "assistant", "content": content})

            if not response.get("tool_calls"):
                return content

            # Handle tool calls (simplified)
            for tc in response["tool_calls"]:
                tool_name = tc["function"]["name"]
                arguments = json.loads(tc["function"]["arguments"])
                for t in tools:
                    if t.name == tool_name:
                        result = await ToolExecutor.execute(t, arguments, agent)
                        exec_messages.append({"role": "tool", "content": str(result), "name": tool_name})
                        break

        return "[max iterations reached]"
```

## Design Decision: Model Config Copying

Since `LanguageModel` is frozen, custom loops that need to temporarily change model parameters (like temperature) must create a copy:

```python
# Inside custom loop:
plan_model = agent.llm_model.model_copy(update={"temperature": self.plan_temperature})
# Use plan_model for the planning call
# But agent._call_llm() uses agent.llm_model, so the loop needs to either:
#   a) Call the LLM client directly (more control)
#   b) Temporarily swap agent.llm_model (not recommended)
```

For option (a), custom loops can import `OpenAICompatibleClient` and call it directly:
```python
from tinycua_sdk.agent.llm_client import OpenAICompatibleClient

client = OpenAICompatibleClient()
response = await client.chat(plan_messages, None, plan_model)
```

This is acceptable because custom loops are advanced use cases.

## File Changes

| File | Change |
|------|--------|
| `agent/loop.py` | Ensure `BaseLoop` has clean `run()` signature, no hooks |
| `agent/agent.py` | Ensure `_call_llm()` is accessible, `loop` param wired |

## Testing Strategy

- Unit test custom loop subclassing:
  - Minimal loop that returns a fixed string.
  - Loop that calls `_call_llm()` once.
  - Loop that checks `agent.is_cancelled`.
  - Loop that reads `self.max_iterations`.
- Integration test with ReActLoop and PlanThenExecuteLoop examples.
