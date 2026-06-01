# Tool Constants

> **File:** `docs/design/constants/tools.md`
> **Package:** `tinycua.constants.tools`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Overview

Each AgentNode has a module-level `*_BASE_TOOLS` constant — a list of pre-configured
SDK `Tool` instances. These are the node's inherent tools, separated from
`config.extra_tools` (external injection only).

---

## Classification Constants

QueryAnalyst uses a configurable `ClassificationTool`. Labels are supplied by
`QueryAnalystConfig.classification_labels`.

```text
TINYCUA_INPUT_GATE_CLASSIFICATION: list[str] = [
    "passthrough",
    "worker",
]

TINYCUA_WORKER_INPUT_GATE_CLASSIFICATION: list[str] = [
    "task_recreation",     # clear current task tree and terminate worker for restart
    "task_reanalysis",     # analyze tasks; TaskInit only if worker has no task yet
    "proceed_execution",   # skip analysis/decomposition and execute/review
]

TASK_ASSESSOR_CLASSIFICATION: list[str] = ["analyze", "stop"]

RESULT_REVIEWER_CLASSIFICATION: list[str] = ["accept", "retry", "replan"]
```

`uncertain` and `escalate_user` are intentionally absent. Indecision means the node
does not produce a terminal decision and remains active with an open question.

---

## Shared Tool Sets

```text
READ_ONLY_TASK_TOOLS: list[tinycua_sdk.Tool] = [
    ReadActiveTask,
    ReadTask,
    ListTask,
]

WRITE_TASK_TOOLS: list[tinycua_sdk.Tool] = [
    TaskInit,
    SetSubTask,
    AddSubTask,
    DeleteSubTask,
    EditSubTask,
    SwapTask,
    UpdateTaskResult,
]

# General read-only exploration tools available to transient exploration agents.
EXPLORATION_TOOL: list[tinycua_sdk.Tool] = [
    FileReadTool(),
    FileListTool(),
    WebSearchTool(),
]

# Shared execution surface for PrimaryAgent and TaskExecutor.
SHARED_AGENT_BASE_TOOLS: list[tinycua_sdk.Tool] = [
    ShellTool(),
    FileReadTool(),
    FileWriteTool(),
    TODO_LIST_TOOL,
    # ... other general-purpose tools
]
```

### InformationDigester inner-agent tool split

InformationDigester's `enhanced_context_retrieval` tool spawns inner transient agents.
Those inner agents receive:

```text
CONTEXT_CACHE_TOOLS = [grep_context, read_context]  # scoped strictly to cache file
EXPLORATION_TOOL = [FileReadTool, FileListTool, WebSearchTool]  # general read-only exploration
```

The cache tools and exploration tools are intentionally separate. `grep_context` and
`read_context` can only operate on the context cache, while `EXPLORATION_TOOL` may
inspect external project/web sources as read-only exploratory context.

---

## AgentNode Base Tools

```text
QUERY_ANALYST_BASE_TOOLS(config): list[tinycua_sdk.Tool] = [
    ClassificationTool(name="classify", labels=config.classification_labels)
]

QUERY_ANALYST_READ_TOOLS: list[tinycua_sdk.Tool] = READ_ONLY_TASK_TOOLS

INFORMATION_DIGESTER_BASE_TOOLS: list[tinycua_sdk.Tool] = []
    # Tools built dynamically in run():
    # → enhanced_context_retrieval(cache_path, model, tools=[*CONTEXT_CACHE_TOOLS, *EXPLORATION_TOOL])
    # → digest_information

TASK_ANALYZER_BASE_TOOLS: list[tinycua_sdk.Tool] = [
    *READ_ONLY_TASK_TOOLS,
    SetSubTask,
    AddSubTask,
    DeleteSubTask,
    EditSubTask,
    SwapTask,
    UpdateTaskResult,
]
    # TaskInit is excluded by default. Worker injects TaskInit only for task_reanalysis
    # when worker.session.task is None.

TASK_ASSESSOR_BASE_TOOLS: list[tinycua_sdk.Tool] = [
    ClassificationTool(name="classify", labels=TASK_ASSESSOR_CLASSIFICATION)
]

TASK_EXECUTOR_BASE_TOOLS: list[tinycua_sdk.Tool] = [
    *SHARED_AGENT_BASE_TOOLS,
    ReadActiveTask,
    ListTask,
    UpdateActiveTaskResult,
]

RESULT_REVIEWER_BASE_TOOLS: list[tinycua_sdk.Tool] = [
    *READ_ONLY_TASK_TOOLS,
    UpdateActiveTaskResult,       # retry path may reset active task to not_started
    ReviewContextUpdateTool,      # specialized minimal context-update tool
    ClassificationTool(name="classify", labels=RESULT_REVIEWER_CLASSIFICATION),
]

PRIMARY_AGENT_BASE_TOOLS: list[tinycua_sdk.Tool] = [
    *SHARED_AGENT_BASE_TOOLS,
]
```

---

## `ClassificationTool`

```text
ClassificationTool implements tinycua_sdk.Tool
  · labels: list[str]          # configured at construction
  · name: str = "classify"
  · execute(label_index: int) → str:
      · if 0 ≤ label_index < len(labels): return labels[label_index]
      · raise ValueError if out of range
```

Labels live in config/constants, not prompt text. The same QueryAnalyst implementation
can therefore act as TinyCUA root input gate, TinyCUAWorker input gate, or any future
DecisionNode-like input gate.

---

## Tool Source Pattern

Every AgentNode's `run()` builds the SDK Agent per-call, merging base tools and
caller-injected extras:

```text
tools = [*BASE_TOOLS, *self.session.agent_state.agent_config.extra_tools]
```

| Source | Location | Purpose |
|--------|----------|---------|
| `*_BASE_TOOLS` | `tinycua.constants.tools` | Pre-configured code-level tool set |
| `config.extra_tools` | Agent config dataclass | External injection (empty by default) |

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| QueryAnalyst labels configurable | `QueryAnalystConfig.classification_labels` | Same node can act as root or worker input gate |
| No uncertain label | Root classifications are `passthrough` / `worker` | Indecision = active/open-question behavior |
| No escalate_user label | Reviewer classifications are `accept` / `retry` / `replan` | HITL through non-termination |
| Split exploration/context tools | `EXPLORATION_TOOL` separate from cache tools | Context tools are cache-scoped; exploration tools are broader read-only |
| TaskInit conditional | Inject only when worker task analysis starts without a task tree | Allows initial creation while preventing destructive reset during normal analysis |
| TaskExecutor scoped tools | `UpdateActiveTaskResult`, not `UpdateTaskResult` | Executor can only update current active task |
| ResultReviewer specialized tools | Minimal review-write surface | Reviewer can reset active task and add context without arbitrary edits |
| `extra_tools` separate | Empty by default | Single injection channel; keeps base tools clean |

---

## See also

Prev : [Per-Agent Config Dataclasses](../config/agents.md) | Next : [Agent Instruction Constants](instructions.md)

## Related

- [Config extra_tools channel](../config/agents.md)
- [QueryAnalyst classification config](../agent_node/query_analyst.md)
- [InformationDigester enhanced retrieval](../agent_node/information_digester.md)
- [Task tools](../tools/task.md)
