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
from tinycua.constants.prompts import TASK_EXECUTOR_PROMPT
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
        self.state.last_query = {"task": task}
        self.state.accumulated_text = []

        input_msg = json.dumps(task)

        agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*TASK_EXECUTOR_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(state=self.state),
        )

        async for event in agent.run(query=input_msg, stream=True):
            if event["type"] == "response.output_text.delta":
                self.state.accumulated_text.append(event["delta"])
            elif event["type"] == "response.usage":
                self.state.token_usage = event["usage"]
            yield event

        raw = "".join(self.state.accumulated_text)
        result = json.loads(raw)
        self.state.task_result = TaskResult(**result)
        self.state.execution_attempts += 1
        self.state.last_result = result
```

---

## Config

`TaskExecutorConfig` — `name="task-executor"`, `instructions=TASK_EXECUTOR_PROMPT`.
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
