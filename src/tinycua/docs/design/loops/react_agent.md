# ReActAgentLoop

> **File:** `docs/design/loops/react_agent.md`
> **Package:** `tinycua.loops.react_agent`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`ReActAgentLoop` is the shared execution loop for simple single-input/single-output agents.
It extends SDK `BaseLoop` with no additional control flow — just inherits all ReAct
behavior (think → tool call → observe → repeat). It receives the orchestrator's state
by reference for telemetry and logging.

---

## Class Contract

**File:** `tinycua/loops/react_agent.py`

```python
from tinycua_sdk.agent.loop import BaseLoop
from tinycua.state.base import StateObject


class ReActAgentLoop(BaseLoop):
    """Shared ReAct loop — extends SDK BaseLoop.

    Receives state by reference for logging/telemetry. No additional control
    flow — SDK BaseLoop handles ReAct iteration, tool execution, and streaming.
    """

    def __init__(self, state: StateObject):
        super().__init__()
        self.state = state  # direct reference to orchestrator state

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        """Delegates entirely to SDK BaseLoop. State can be read/written here."""
        async for event in super().run(agent, messages, tools, override_instructions, stream=True):
            yield event  # transparent passthrough
```

---

## Why Not Use SDK `BaseLoop` Directly?

`ReActAgentLoop` gives TinyCUA a single point to add common behavior across all simple
agents without touching each orchestrator or depending on SDK `BaseLoop` internals:

- **Logging hooks** — log every tool call, every ReAct iteration
- **Telemetry** — track token usage, iteration count, latency via `self.state`
- **Common overrides** — custom streaming behavior, cancellation handling

Without `ReActAgentLoop`, these would need to be duplicated across four orchestrators.

---

## Usage in Orchestrator

```python
class TaskAnalyzer(BaseAgentOrchestrator[TaskAnalyzerState]):
    async def run(self, digested_information: dict):
        agent = Agent(
            ...,
            loop=ReActAgentLoop(state=self.state),
        )
        text_parts: list[str] = []
        async for event in agent.run(query=input_msg, stream=True):
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event

        raw = "".join(text_parts)
        result = json.loads(raw)
        self.state.task_tree = Task(**result)
        self.state.last_result = result
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Shared, not per-agent | One `ReActAgentLoop` class | No behavioral difference between simple agents |
| Thin BaseLoop extension | Delegates entirely to `super().run()` | All behavior inherited from SDK; override for future needs |
| State via constructor | `ReActAgentLoop(state=self.state)` | Direct reference for telemetry and logging |
| No custom termination | SDK default ReAct termination | Simple agents produce one output and stop |


---

## See also

Prev : [Loop Strategies Overview](overview.md) | Next : [`QueryAnalystLoop`](query_analyst_loop.md)
