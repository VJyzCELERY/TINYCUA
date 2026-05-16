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

Each success criterion must be validated by running the specified test file(s).

### Contract Tests (always run, no LLM server required)

These tests use deterministic stubs or no LLM calls at all. They validate the BaseLoop
subclassing contract and are always run.

- [ ] Custom Loop Overrides Default - tests/integration/goals/test_adv_01_custom_agent_loop.py - PASS - `print('PASS')`
  Description: Subclassing `BaseLoop` and passing to `Agent` uses the custom loop.

- [ ] Cancellation Respected - tests/integration/goals/test_adv_01_custom_agent_loop.py - PASS - `print('PASS')`
  Description: Custom loop respects `agent.is_cancelled`.

- [ ] max_iterations Respected - tests/integration/goals/test_adv_01_custom_agent_loop.py - PASS - `print('PASS')`
  Description: Custom loop respects `self.max_iterations`.

- [ ] Custom Loop Accesses LLM (contract) - tests/unit/test_loop_custom.py - PASS - `print('PASS')`
  Description: Custom loop can call `agent._call_llm()` (deterministic fake response).

- [ ] ReActLoop Contract - tests/unit/test_loop_custom.py - PASS - `print('PASS')`
  Description: ReAct-style loop with fake LLM executes tool and continues.

- [ ] PlanThenExecuteLoop Contract - tests/unit/test_loop_custom.py - PASS - `print('PASS')`
  Description: PlanThenExecuteLoop with fake LLM runs plan phase and execution phase.

- [ ] Streaming Events Contract - tests/unit/test_loop_custom.py - PASS - `print('PASS')`
  Description: Default streaming loop emits lifecycle events with fake stream.

- [ ] Guardrail Propagation Contract - tests/unit/test_agent_guardrail_propagation.py - PASS - `print('PASS')`
  Description: Denied tool results propagate through Agent.run() with fake LLM.

### Real Integration Tests (require local LLM server, marked @pytest.mark.integration)

These tests use the SDK's actual `LanguageModel` transport without monkeypatching
`_call_llm()`. They are skipped when no LLM server is available.

- [ ] Custom Loop Real LLM - tests/integration/goals/test_adv_01_custom_agent_loop.py (test_integration_custom_loop_calls_real_llm) - string response - `uv run pytest tests/integration/goals/test_adv_01_custom_agent_loop.py -v -m integration`
  Description: Custom loop calls `agent._call_llm()` against the configured endpoint.

- [ ] ReActLoop Real LLM - tests/integration/goals/test_adv_01_custom_agent_loop.py (test_integration_react_loop_real_llm) - string response - same command
  Description: ReAct-style loop with real model transport and tool support.

- [ ] Streaming Real LLM - tests/integration/goals/test_adv_01_custom_agent_loop.py (test_integration_streaming_lifecycle_real_llm) - lifecycle events - same command
  Description: Streaming run verifies provider/SDK lifecycle events through real transport.

- [ ] PlanThenExecuteLoop Real LLM - tests/integration/goals/test_adv_01_custom_agent_loop.py (test_integration_plan_then_execute_real_llm) - string response - same command
  Description: PlanThenExecute loop passes a copied LanguageModel through `_call_llm(llm_model=...)`.

## Test Files

### Unit / Contract Tests
- `tests/unit/test_loop_custom.py` — BaseLoop contract tests with fake LLM responses
- `tests/unit/test_agent_guardrail_propagation.py` — Guardrail propagation contract test

### Integration Tests (contract, always run)
- `tests/integration/goals/test_adv_01_custom_agent_loop.py` — subset without LLM dependency

### Integration Tests (real LLM, @pytest.mark.integration)
- `tests/integration/goals/test_adv_01_custom_agent_loop.py` — tests with `@pytest.mark.integration`

### Optional Manual Verification
- `targets/06_streaming_events.py` — standalone target script (uses deterministic fake stream)
