# Task Analyzer

> **File:** `docs/design/agents/task_analyzer.md`
> **Package:** `tinycua.agents.task_analyzer`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`TaskAnalyzer` decomposes information into a task tree using the full task tool suite.
It can analyze a `DigestedInformation` to build a structured task plan, or process a
plain query to break down and modify existing tasks.

Called **through TaskCreator** — not directly by Worker orchestration. TaskCreator wraps
TaskAnalyzer → TaskAssessor and returns the aggregated result.

---

## Session

TaskAnalyzer is a **regular (non-transient) session** — it owns a session node in
the tree. Its operations (task creation, editing, deletion) modify the shared
`session.task` tree, which persists after termination.

---

## `run()` Method

### Signature

```python
async def run(self, query: str | dict) -> AsyncIterator[dict]:
```

Takes a single argument:
- `str`: A plain query to analyze and break down into tasks
- `dict`: Formatted `DigestedInformation` from InformationDigester

### Flow

```
run(query)
  │
  ├─ 1. Build instruction: base + task context display
  │
  ├─ 2. Build query from input (string or structured dict)
  │
  ├─ 3. Build SDK Agent (per-call)
  │     Tools: all read + write task tools EXCEPT TaskInit
  │     TaskInit only injected via config.extra_tools if needed
  │
  ├─ 4. Stream → accumulate text, yield all events
  │
  └─ 5. Parse result → store analysis summary in state
```

---

## Tools

TaskAnalyzer has the **widest tool set of any agent** — it can read, create, edit,
delete, and reorganize tasks:

```python
from tinycua.constants.tools import TASK_ANALYZER_BASE_TOOLS

# TASK_ANALYZER_BASE_TOOLS = [
#     *READ_ONLY_TASK_TOOLS,    # ReadActiveTask, ReadTask, ListTask
#     *WRITE_TASK_TOOLS,        # All write tools...
# ]
# MINUS TaskInit               # ...EXCEPT TaskInit
```

| Tool Set | Included | Purpose |
|----------|----------|---------|
| `ReadActiveTask` | Yes | Check what's currently being worked on |
| `ReadTask` | Yes | Inspect specific tasks by ID |
| `ListTask` | Yes | View the full task tree |
| `SetSubTask` | Yes | Replace children — can reset the tree |
| `AddSubTask` | Yes | Append new subtasks |
| `DeleteSubTask` | Yes | Remove obsolete tasks |
| `EditSubTask` | Yes | Update task metadata |
| `SwapTask` | Yes | Reorganize task order |
| `TaskInit` | **No (by default)** | Only provided via `extra_tools` on special occasions |

### Why Exclude TaskInit?

`TaskInit` replaces the **entire** task tree atomically. TaskAnalyzer should modify
the existing tree — not wholesale replace it. If a greenfield task creation is needed,
the caller (TaskCreator) can inject `TaskInit` via `config.extra_tools`.

TaskAnalyzer can still reset the tree using existing tools:
- `SetSubTask(root_id, [])` → clear all children
- `EditSubTask(root_id, {...})` → update root metadata
- `AddSubTask(root_id, new_tasks)` → build new subtrees

---

## Instruction

```python
def build_instruction(self, context: dict[str, Any]) -> str:
    """Build the full system prompt: base + current task state."""
    base = self.config.instructions  # TASK_ANALYZER_INSTRUCTION

    task = self.session.task
    if task is not None:
        task_display = f"---\n## Current Task Tree\n{task.display()}"
    else:
        task_display = "---\nNo active task tree."

    return f"{base}\n\n{task_display}"
```

The instruction includes:
1. **Base role** — from `TASK_ANALYZER_INSTRUCTION` constant
2. **Current task tree display** — so the agent knows what exists before modifying

---

## Output

The agent's final text response is an **analysis summary** — a markdown description
of what was done:

```
## Task Analysis Summary

### Created
- T-0.0: Install nginx
- T-0.1: Configure virtual hosts

### Modified
- T-0: Updated success criteria for "Set up nginx"

### Deleted
- T-0.0.1: Install from source (obsolete — using apt instead)

### Reasoning
The installation path was changed from source to apt because...
```

After the stream ends, the orchestrator extracts the summary and stores it in state:

```python
self.state.analysis_summary = raw  # the full markdown summary
self.state.last_result = {"summary": raw}
```

### Post-Condition

After TaskAnalyzer finishes, the **shared `session.task` tree** reflects all
mutations performed by the agent's tool calls. The analysis summary documents
what changed and why.

---

## Complete Orchestrator

```python
import json
from collections.abc import AsyncIterator

from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentOrchestrator
from tinycua.config.agents import TaskAnalyzerConfig
from tinycua.constants.tools import TASK_ANALYZER_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.state.information import TaskAnalyzerState
from tinycua.tools.task import TASK_INIT  # imported for optional injection


class TaskAnalyzer(BaseAgentOrchestrator[TaskAnalyzerState]):
    """Task decomposition with full read/write task tool suite.

    Can analyze DigestedInformation to build structured task plans,
    or process plain queries to break down and modify existing tasks.
    TaskInit is excluded by default — the agent modifies the existing
    tree rather than wholesale replacing it.
    """

    config: TaskAnalyzerConfig

    def __init__(self, config: TaskAnalyzerConfig | None = None):
        if config is None:
            config = TaskAnalyzerConfig()
        super().__init__(config=config, session=None)

    # ── Main entry point ─────────────────────────────────────────────

    async def run(self, query: str | dict) -> AsyncIterator[dict]:
        # 1. Build instruction: base + current task tree
        instructions = self.build_instruction({})

        # 2. Build query from input
        agent_query = self._build_query(query)

        # 3. Build tools: all read + write EXCEPT TaskInit (unless injected)
        tools = self._get_tools()

        # 4. Build SDK Agent per-call
        agent = Agent(
            name=self.config.name,
            instructions=instructions,
            llm_model=self.config.model,
            tools=tools,
            loop=ReActAgentLoop(state=self.state),
        )

        # 5. Stream — accumulate text, yield everything
        text_parts: list[str] = []
        async for event in agent.run(query=agent_query, stream=True):
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event

        # 6. Store analysis summary (NOT parsed JSON — natural language)
        raw = "".join(text_parts)
        self.state.analysis_summary = raw
        self.state.last_result = {"summary": raw}

    # ── Query construction ───────────────────────────────────────────

    def _build_query(self, query: str | dict) -> str:
        """Normalize input to a string query for the agent."""
        if isinstance(query, dict):
            return json.dumps({
                "instruction": "Analyze the following digested information "
                               "and produce a task tree.",
                "digested_information": query,
            })
        return query

    # ── Tools ────────────────────────────────────────────────────────

    def _get_tools(self) -> list:
        """Build tool list: all task tools EXCEPT TaskInit.

        TaskInit can be injected via config.extra_tools for greenfield
        task creation (e.g., when TaskCreator needs to start fresh).
        """
        from tinycua.constants.tools import (
            TASK_ANALYZER_BASE_TOOLS,
        )
        return [
            *TASK_ANALYZER_BASE_TOOLS,
            *self.config.extra_tools,  # may include TaskInit
        ]

    # ── Instruction ──────────────────────────────────────────────────

    def build_instruction(self, context: dict[str, Any]) -> str:
        base = self.config.instructions

        task = self.session.task
        if task is not None:
            task_display = (
                f"---\n## Current Task Tree\n{task.display()}"
            )
        else:
            task_display = "---\nNo active task tree."

        return f"{base}\n\n{task_display}"
```

---

## Config

`TaskAnalyzerConfig` — `name="task-analyzer"`, `instructions=TASK_ANALYZER_INSTRUCTION`.
See [`config/agents.md`](../config/agents.md#taskanalyzerconfig).

---

## State

`TaskAnalyzerState` — `analysis_summary: str | None`.
Captures the agent's markdown summary of what was created, modified, or deleted.

See [`state/information.md`](../state/information.md#taskanalyzerstate).

---

## Loop

`ReActAgentLoop(state=self.state)` — shared ReAct loop with state reference.
No custom iteration logic — the agent uses tool calls to build/edit tasks,
then produces a final summary.

See [`loops/react_agent.md`](../loops/react_agent.md).

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| All task tools except TaskInit | `TASK_ANALYZER_BASE_TOOLS` = read + write − TaskInit | Agent modifies existing tree; greenfield creation opt-in via extra_tools |
| Reset via tools | `SetSubTask` + `EditSubTask` on root | Same effect as TaskInit without wholesale replacement |
| Input flexible | `str | dict` | Works with DigestedInformation or plain queries |
| Markdown summary output | Agent final text = analysis summary | Human-readable documentation of what changed |
| No JSON parsing | Store raw markdown, not structured JSON | Task tree already modified by tool calls; summary is documentation |
| Task tree display in instruction | `task.display()` when task exists | Agent sees current state before deciding what to modify |
| ReActAgentLoop | Shared loop with state reference | Standard ReAct pattern; no custom stop conditions needed |


---


---


---

## See also

Prev : [`InformationDigester`](information_digester.md) | Next : [`TaskAssessor`](task_assessor.md)


## Related

- [Called through TaskCreator](task_creator.md)
- [Task tools (read + write)](../tools/task.md)
- [Shared Task tree on Session.task](../state/task.md)
- [DigestedInformation from InformationDigester](../state/digested_information.md)
- [TASK_ANALYZER_BASE_TOOLS](../constants/tools.md)
