# Task Executor

> **File:** `docs/design/agents/task_executor.md`
> **Package:** `tinycua.agents.task_executor`

---

## Wrapper Class

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import TaskExecutorConfig
from tinycua.constants.tools import TASK_EXECUTOR_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.utility.schema_validator import SchemaValidator
from tinycua.state.information import TaskExecutorState
from tinycua.state import TaskResult


class TaskExecutor(BaseAgentWrapper[TaskExecutorState]):
    """Task execution agent — ReActAgentLoop with native tools."""

    state: TaskExecutorState

    def __init__(self, config: TaskExecutorConfig):
        super().__init__(config, state_factory=TaskExecutorState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*TASK_EXECUTOR_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(),
        )

    async def run(self, task: dict) -> dict:
        self.state.last_query = {"task": task}
        raw = await self.agent.run(query=json.dumps(task))
        result = SchemaValidator(validation_fn=validate_task_result).validate(raw)
        self.state.task_result = TaskResult(**result)
        self.state.execution_attempts += 1
        self.state.last_result = result
        return result
```

## Config

`TaskExecutorConfig` — `name="task-executor"`, `instructions=TASK_EXECUTOR_PROMPT`.
See [`config/agents.md`](../config/agents.md#taskexecutorconfig).

## State

`TaskExecutorState` — `task_result: TaskResult | None`, `execution_attempts: int`, `tool_results: list[dict]`.
See [`state/information.md`](../state/information.md#taskexecutorstate).

## Loop

`ReActAgentLoop` — shared. Native tools drive internal ReAct iteration.
See [`loops/react_agent.md`](../loops/react_agent.md).

## Tools

`TASK_EXECUTOR_BASE_TOOLS = [*native_benchmark_tools]`.
See [`constants/tools.md`](../constants/tools.md).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Native tools drive internal iteration |
| Native tools in constant | `TASK_EXECUTOR_BASE_TOOLS` | Always available |
| Execution attempts tracked | `self.state.execution_attempts` | Retry logic and diagnostics |
