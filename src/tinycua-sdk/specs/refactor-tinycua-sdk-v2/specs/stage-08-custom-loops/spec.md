# Stage 8: Extensibility — Custom Loops — Specification

## Objective
`BaseLoop` is a clean extension point for consumers. Custom loops can override execution behavior without modifying SDK internals.

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
        stream: str = "off",
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
async def _call_llm(self, messages: list[dict], tools: list[Tool] | None = None) -> dict:
    """Call LLM with agent's configuration. Available to custom loops."""
```

Custom loops call this instead of reimplementing HTTP transport.

### R-8.3: Custom Loop Examples

**ReActLoop:**
```python
class ReActLoop(BaseLoop):
    def __init__(self, max_iterations=5, format_hint="ReAct"):
        super().__init__(max_iterations)
        self.format_hint = format_hint

    async def run(self, agent, messages, tools, override_instructions=None, stream="off"):
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

    async def run(self, agent, messages, tools, override_instructions=None, stream="off"):
        # Phase 1: Get plan
        # Phase 2: Execute plan
        pass
```

### R-8.4: Loop Assignment

```python
agent = Agent(
    name="react_assistant",
    llm_model=LanguageModel(...),
    loop=ReActLoop(max_iterations=5, format_hint="ReAct"),
)
```

The agent stores the loop instance and calls `loop.run()` on each `run()`.

## Success Criteria

### SC-8.1: Custom Loop Overrides Default
**What:** Subclassing `BaseLoop` and passing to `Agent` uses the custom loop.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop

class MyLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream='off'):
        return 'custom result'

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), loop=MyLoop())
r = asyncio.run(a.run('Hello'))
assert r == 'custom result'
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-8.2: Custom Loop Accesses LLM
**What:** Custom loop can call `agent._call_llm()`.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop

class LLMLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream='off'):
        resp = await agent._call_llm(messages)
        return resp.get('content', '')

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), loop=LLMLoop())
r = asyncio.run(a.run('Say hi.'))
assert isinstance(r, str)
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-8.3: Cancellation Respected
**What:** Custom loop respects `agent.is_cancelled`.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop

class SlowLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream='off'):
        for i in range(100):
            if agent.is_cancelled:
                return '[cancelled]'
            await asyncio.sleep(0.01)
        return 'done'

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), loop=SlowLoop())
task = asyncio.create_task(a.run('Wait'))
await asyncio.sleep(0.05)
a.cancel()
r = await task
assert r == '[cancelled]'
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-8.4: max_iterations Respected
**What:** Custom loop respects `self.max_iterations`.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop

class CountingLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream='off'):
        for i in range(self.max_iterations):
            pass
        return f'ran {self.max_iterations} times'

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), loop=CountingLoop(max_iterations=3))
r = asyncio.run(a.run('Hello'))
assert r == 'ran 3 times'
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-8.5: ReActLoop Example Works
**What:** The ReActLoop example from goals runs.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, BaseLoop, tool

class ReActLoop(BaseLoop):
    async def run(self, agent, messages, tools, override_instructions=None, stream='off'):
        resp = await agent._call_llm(messages, tools)
        return resp.get('content', '')

@tool
def weather(city: str) -> str:
    return f'Sunny in {city}.'

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), tools=[weather], loop=ReActLoop())
r = asyncio.run(a.run('What is the weather in Tokyo?'))
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-8.6: Integration Test Pass
**What:** `test_adv_01_custom_agent_loop.py` passes.  
**How to check:**
```bash
cd src/tinycua-sdk && pytest tests/integration/goals/test_adv_01_custom_agent_loop.py -v
```
**Pass if:** 1 passed, 0 failed.

## Integration Test File
- `tests/integration/goals/test_adv_01_custom_agent_loop.py`
