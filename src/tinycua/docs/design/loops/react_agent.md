# ReActAgentLoop

> **File:** `docs/design/loops/react_agent.md`
> **Package:** `tinycua.loops.react_agent`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`ReActAgentLoop` is the shared execution loop for simple single-input/single-output agents.
It extends SDK `BaseLoop` with no additional control flow — just inherits all ReAct
behavior (think → tool call → observe → repeat). Used directly by TaskAnalyzer,
TaskAssessor, TaskExecutor, and PrimaryAgent.

---

## Class Contract

**File:** `tinycua/loops/react_agent.py`

```python
from tinycua_sdk.agent.loop import BaseLoop


class ReActAgentLoop(BaseLoop):
    """Shared ReAct loop — extends SDK BaseLoop with no additional control flow.

    Used directly by TaskAnalyzer, TaskAssessor, TaskExecutor, and PrimaryAgent.
    The wrapper class provides agent identity; the loop provides execution strategy.
    Pre-processing and post-processing happen in the wrapper's run() method.
    """
    pass  # Inherits all BaseLoop behavior; no override needed
```

---

## Why Not Use SDK `BaseLoop` Directly?

`ReActAgentLoop` gives TinyCUA a single point to add common behavior across all simple
agents without touching each wrapper or depending on SDK `BaseLoop` internals:

- Logging hooks (log every tool call, every ReAct iteration)
- Telemetry (track token usage, iteration count, latency)
- Common overrides (custom streaming behavior, cancellation handling)

Without `ReActAgentLoop`, these would need to be duplicated across four wrappers.

---

## Usage in Wrapper

```python
class TaskAnalyzer(BaseAgentWrapper[TaskAnalyzerState]):
    def _build_agent(self):
        self.agent = Agent(
            ...
            tools=[*TASK_ANALYZER_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(),
        )

    async def run(self, digested_information: dict) -> dict:
        # Pre-processing: build messages from domain objects
        input_msg = f"Analyze: {json.dumps(digested_information)}"
        # Execute
        raw = await self.agent.run(query=input_msg)
        # Post-processing: validate and store
        result = SchemaValidator(...).validate(raw)
        self.state.task_tree = Task(**result)
        return result
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Shared, not per-agent | One `ReActAgentLoop` class | No behavioral difference between simple agents; wrapper provides identity |
| Thin BaseLoop extension | `pass` body | All behavior inherited from SDK; override point available for future needs |
