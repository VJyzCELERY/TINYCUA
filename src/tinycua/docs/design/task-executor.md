# Task Executor

> **File:** `docs/design/task-executor.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **Architecture reference:** [`../architecture/task-execution.md`](../architecture/task-execution.md)
> **See also:** [`overview.md`](overview.md), [`loop-strategies.md`](loop-strategies.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Role

The Task Executor executes a single task using native benchmark tools (code execution,
file operations, web search, etc.) and produces a `TaskResult`.

---

## Wrapper Class

**File:** `tinycua/agents/task_executor.py`

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import TaskExecutorConfig
from tinycua.constants.tools import TASK_EXECUTOR_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.loops.schema_validator import SchemaValidator
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

---

## Config

**File:** `tinycua/config/agents.py`

```python
@dataclass
class TaskExecutorConfig(AgentConfigBase):
    name: str = "task-executor"
    instructions: str = TASK_EXECUTOR_PROMPT
```

---

## State

**File:** `tinycua/state/information.py`

```python
@dataclass
class TaskExecutorState(StateInformation):
    task_result: TaskResult | None = None
    execution_attempts: int = 0
    tool_results: list[dict] = field(default_factory=list)
```

---

## Loop

`ReActAgentLoop` — shared loop with native tools providing internal tool-calling iteration.
See [`loop-strategies.md`](loop-strategies.md#reactagentloop).

---

## Tools

**File:** `tinycua/constants/tools.py`

```python
TASK_EXECUTOR_BASE_TOOLS: list[Tool] = [
    *native_benchmark_tools,   # code execution, file ops, web search, etc.
]
```

Native benchmark tools are defined as SDK `Tool` contracts. Full implementation belongs
to the Tools milestone. Stubs/mocks are acceptable for early tests.

Additional tools can be injected via `config.extra_tools`.

---

## Prompt Contract

**File:** `tinycua/agents/prompts.py`

The prompt must include:
- **Role**: Task execution agent — execute one task using available tools
- **Input contract**: `Task` (single task object)
- **Output schema**: `TaskResult` with `task_id`, `status`, `result`, optional `discovered_sequence_issues`, `uncertainty_notes`
- **Tool usage**: Use native benchmark tools as needed; report results factually
- **Guardrails**: Do not modify the task; execute as specified; record any issues discovered during execution

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Native tools drive internal iteration via ReAct |
| Native tools in constant | `TASK_EXECUTOR_BASE_TOOLS` | Always available; not configurable at runtime |
| Execution attempts tracked | `self.state.execution_attempts` | Useful for retry logic and diagnostics |
