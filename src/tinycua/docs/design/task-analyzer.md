# Task Analyzer

> **File:** `docs/design/task-analyzer.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **Architecture reference:** [`../architecture/task-analysis.md`](../architecture/task-analysis.md)
> **See also:** [`overview.md`](overview.md), [`loop-strategies.md`](loop-strategies.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Role

The Task Analyzer produces a `Task` tree from `DigestedInformation` — a sequential
roadmap of tasks with root and child nodes. Uses `ReActAgentLoop` (no custom control flow).

---

## Wrapper Class

**File:** `tinycua/agents/task_analyzer.py`

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import TaskAnalyzerConfig
from tinycua.constants.tools import TASK_ANALYZER_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.loops.schema_validator import SchemaValidator
from tinycua.state.information import TaskAnalyzerState
from tinycua.state import Task


class TaskAnalyzer(BaseAgentWrapper[TaskAnalyzerState]):
    """Task decomposition agent — ReActAgentLoop."""

    state: TaskAnalyzerState

    def __init__(self, config: TaskAnalyzerConfig):
        super().__init__(config, state_factory=TaskAnalyzerState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*TASK_ANALYZER_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(),
        )

    async def run(self, digested_information: dict) -> dict:
        self.state.last_query = {"digested_information": digested_information}
        input_msg = f"Analyze the following information:\n{json.dumps(digested_information)}"
        raw = await self.agent.run(query=input_msg)
        result = SchemaValidator(validation_fn=validate_task_tree).validate(raw)
        self.state.task_tree = Task(**result)
        self.state.last_result = result
        return result
```

---

## Config

**File:** `tinycua/config/agents.py`

```python
@dataclass
class TaskAnalyzerConfig(AgentConfigBase):
    name: str = "task-analyzer"
    instructions: str = TASK_ANALYZER_PROMPT
```

---

## State

**File:** `tinycua/state/information.py`

```python
@dataclass
class TaskAnalyzerState(StateInformation):
    task_tree: Task | None = None
```

---

## Loop

`ReActAgentLoop` — shared loop used by all simple agents. No custom control flow.
See [`loop-strategies.md`](loop-strategies.md#reactagentloop).

---

## Tools

**File:** `tinycua/constants/tools.py`

```python
TASK_ANALYZER_BASE_TOOLS: list[Tool] = []
```

No inherent tools. Optional information tools can be injected via `config.extra_tools`.

---

## Prompt Contract

**File:** `tinycua/agents/prompts.py`

The prompt must include:
- **Role**: Task decomposition agent — produces a sequential task roadmap
- **Input contract**: `DigestedInformation`
- **Output schema**: `Task` tree with `task_id`, `task_name`, `task_description`, `task_context`, `success_criteria`, `confidence`, `child_tasks`
- **Constraints**: Each leaf must have all required fields; `child_tasks: None` = leaf
- **Guardrails**: Tasks must be sequential and decomposable

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Single input → single output; ReAct handles internal tool iteration |
| Pre/post in wrapper | Wrapper `run()` validates and stores result | Loop stays focused on execution |
