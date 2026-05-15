# Stage 8: Extensibility — Custom Loops — Specification

**Status**: Draft | In Progress | Complete
**Created**: 2026-05-02
**Last Updated**: 2026-05-02
**Subproject(s) Affected**: tinycua-sdk

## Objective
`BaseLoop` is a clean extension point for consumers. Custom loops can override execution behavior without modifying SDK internals.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

## Reference
- [`goals/advanced/01_custom_agent_loop.py`](../goals/advanced/01_custom_agent_loop.py)

## Requirements

### R-8.1: BaseLoop Interface

```python
class BaseLoop:
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations

    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict]:
        """Default implementation: standard tool-calling loop.

        Subclasses override this for custom behavior.
        """
```

**Key design:**
- No hook system — customization is done by subclassing and overriding `run()` directly.
- `self.max_iterations` is the only built-in safety limit.
- Cancellation is checked via `agent.is_cancelled`.

### R-8.2: Protected Helper

```python
# On Agent class:
async def _call_llm(self, messages: list[dict], tools: list[Tool] | None = None, stream: bool = False, llm_model: LanguageModel | None = None) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
    """Call LLM with agent's configuration. Available to custom loops.

    When llm_model is provided it overrides the agent's default model,
    allowing custom loops to temporarily change model parameters
    (e.g., temperature) without modifying the agent's configuration.
    """
```

**Key design:**
- `llm_model` is optional; when omitted, the agent's default model is used.
- Custom loops like `PlanThenExecuteLoop` can pass a copied model with modified parameters via this parameter instead of calling the LLM client directly.

Custom loops call this instead of reimplementing HTTP transport.

### R-8.3: Custom Loop Examples

**ReActLoop:**
```python
class ReActLoop(BaseLoop):
    def __init__(self, max_iterations=5, format_hint="ReAct"):
        super().__init__(max_iterations)
        self.format_hint = format_hint

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        # Custom logic: inject ReAct format hint
        # Call agent._call_llm() when needed
        # Return final string
        pass
```

**PlanThenExecuteLoop:**
```python
class PlanThenExecuteLoop(BaseLoop):
    def __init__(self, max_iterations=5, plan_temperature=0.3):
        super().__init__(max_iterations)
        self.plan_temperature = plan_temperature

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        # Phase 1: Get plan
        # Phase 2: Execute plan
        pass
```

### R-8.4: Standard OpenAI Event Completeness

The default `BaseLoop._run_stream()` and `BaseLoop.run()` MUST emit these additional streaming events deferred from Stage 5, completing the OpenAI Responses API event coverage:

**R-8.4.1: response.in_progress Event**

Emitted when the response transitions to the "in progress" state (after `response.created`, before first content delta).

```python
{"type": "response.in_progress"}
```

**R-8.4.2: response.function_call_arguments Events (Implemented in Stage 5)**

The `response.function_call_arguments.delta` and `response.function_call_arguments.done` events are already implemented in Stage 5 as raw passthrough from the provider. Custom loops inheriting from `BaseLoop._run_stream()` receive these events automatically and can accumulate them from the chunk stream as needed.

```python
# Example: accumulating tool call arguments in a custom loop
for chunk in stream:
    yield chunk
    if chunk.get("type") == "response.function_call_arguments.delta":
        tool_buffers[chunk["item_id"]]["arguments"] += chunk.get("delta", "")
    elif chunk.get("type") == "response.function_call_arguments.done":
        tool_buffers[chunk["item_id"]]["arguments"] = chunk.get("arguments", "")
```

### R-8.5: Loop Assignment

```python
agent = Agent(
    name="react_assistant",
    llm_model=LanguageModel(...),
    loop=ReActLoop(max_iterations=5, format_hint="ReAct"),
)
```

The agent stores the loop instance and calls `loop.run()` on each `run()`.

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] Custom Loop Overrides Default - tests/integration/goals/test_adv_01_custom_agent_loop.py - PASS - `print('PASS')`
  Description: Subclassing `BaseLoop` and passing to `Agent` uses the custom loop.

- [ ] Custom Loop Accesses LLM - tests/integration/goals/test_adv_01_custom_agent_loop.py - PASS - `print('PASS')`
  Description: Custom loop can call `agent._call_llm()`.

- [ ] Cancellation Respected - tests/integration/goals/test_adv_01_custom_agent_loop.py - PASS - `print('PASS')`
  Description: Custom loop respects `agent.is_cancelled`.

- [ ] max_iterations Respected - tests/integration/goals/test_adv_01_custom_agent_loop.py - PASS - `print('PASS')`
  Description: Custom loop respects `self.max_iterations`.

- [ ] ReActLoop Example Works - tests/integration/goals/test_adv_01_custom_agent_loop.py - PASS - `print('PASS')`
  Description: The ReActLoop example from goals runs.

- [ ] Streaming Events Compliance - targets/06_streaming_events.py and tests/integration/goals/test_adv_01_custom_agent_loop.py - PASS - must not raise
  Description: Custom loop can collect streaming events (response.created, response.in_progress, response.usage, response.completed).

- [ ] Integration Test Pass - tests/integration/goals/test_adv_01_custom_agent_loop.py - 1 passed, 0 failed - pytest -v

## Integration Test File
- `tests/integration/goals/test_adv_01_custom_agent_loop.py`
