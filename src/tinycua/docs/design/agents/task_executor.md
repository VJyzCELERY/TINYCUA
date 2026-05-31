# Task Executor

> **File:** `docs/design/agents/task_executor.md`
> **Package:** `tinycua.agents.task_executor`

---

## Orchestrator Class

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import TaskExecutorConfig
from tinycua.constants.tools import TASK_EXECUTOR_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.state.information import TaskExecutorState
from tinycua.state import TaskResult


class TaskExecutor(BaseAgentOrchestrator[TaskExecutorState]):
    """Task execution — ReActAgentLoop with native tools and direct state reference."""

    config: TaskExecutorConfig

    def __init__(self, config: TaskExecutorConfig | None = None):
        if config is None:
            config = TaskExecutorConfig()
        self.config = config
        self.state = TaskExecutorState()

    async def run(self, task: dict) -> AsyncIterator[dict]:
        # 1. Build instruction from base constant + dynamic context
        instructions = self.build_instruction({})

        # 2. Build query from domain input
        query = json.dumps(task)

        # 3. Build SDK Agent per-call — no self.agent, no _build_agent()
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=[*TASK_EXECUTOR_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(state=self.state),
        )

        # 4. Iterate stream — accumulate text, yield everything to caller
        text_parts: list[str] = []
        async for event in agent.run(query=query, stream=True):
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event

        # 5. After stream ends — parse and store typed state
        raw = "".join(text_parts)
        result = json.loads(raw)
        self.state.task_result = TaskResult(**result)
        self.state.execution_attempts += 1
        self.state.last_result = result
```

---

## Config

`TaskExecutorConfig` — `name="task-executor"`, `instructions=TASK_EXECUTOR_INSTRUCTION`.
See [`config/agents.md`](../config/agents.md#taskexecutorconfig).

---

## State

`TaskExecutorState` — `task_result: TaskResult | None`, `execution_attempts: int`,
`tool_results: list[dict]`.
See [`state/information.md`](../state/information.md#taskexecutorstate).

---

## Loop

`ReActAgentLoop(state=self.state)` — shared loop. Native tools drive internal ReAct iteration.
See [`loops/react_agent.md`](../loops/react_agent.md).

---

## Tools

`TASK_EXECUTOR_BASE_TOOLS = [*native_benchmark_tools]`.
See [`constants/tools.md`](../constants/tools.md).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Native tools in constant | `TASK_EXECUTOR_BASE_TOOLS` | Always available |
| Execution attempts tracked | `self.state.execution_attempts` | Retry logic and diagnostics |


---


---

## See also

Prev : [`TaskCreator`](task_creator.md) | Next : [`ResultReviewer`](result_reviewer.md)
