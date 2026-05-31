# Tool Constants

> **File:** `docs/design/constants/tools.md`
> **Package:** `tinycua.constants.tools`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Overview

Each agent has a module-level `*_BASE_TOOLS` constant — a list of pre-configured SDK `Tool`
instances. These are the agent's inherent tools, separated from `config.extra_tools`
(which is for external injection only). To change an agent's tools, edit the constant
in this file.

---

## All `*_BASE_TOOLS` Constants

```python
from tinycua_sdk.tools.decorators import Tool
from tinycua.tools.classification import ClassificationTool
from tinycua.tools.retrieval import enhanced_context_retrieval
from tinycua.tools.native import native_benchmark_tools

QUERY_ANALYST_BASE_TOOLS: list[Tool] = [
    ClassificationTool(labels=["primary_agent", "worker", "uncertain"]),
]

INFORMATION_DIGESTER_BASE_TOOLS: list[Tool] = [
    enhanced_context_retrieval,
]

TASK_ANALYZER_BASE_TOOLS: list[Tool] = []

TASK_ASSESSOR_BASE_TOOLS: list[Tool] = []

TASK_EXECUTOR_BASE_TOOLS: list[Tool] = [
    *native_benchmark_tools,
]

RESULT_REVIEWER_BASE_TOOLS: list[Tool] = []

PRIMARY_AGENT_BASE_TOOLS: list[Tool] = []
```

---

## Tool Source Pattern

Every orchestrator's `run()` builds the SDK Agent per-call, merging exactly two tool sources:

```python
# Inside orchestrator.run():
agent = Agent(
    ...
    tools=[*QUERY_ANALYST_BASE_TOOLS, *self.config.extra_tools],
    loop=QueryAnalystLoop(state=self.state),
)
```

| Source | Location | Purpose |
|--------|----------|---------|
| `*_BASE_TOOLS` | `tinycua.constants.tools` | Pre-configured, code-level tool set |
| `config.extra_tools` | Agent config dataclass | Externally injected — **empty by default** |

---

## `ClassificationTool`

```python
@dataclass
class ClassificationTool:
    """Maps an agent-selected index to a classification label.

    The agent calls classify(mode_index=N) and the tool returns the label
    at that index from a configurable list. The list is set here, not by
    the agent during execution.
    """
    labels: list[str]

    async def execute(self, mode_index: int) -> str:
        if 0 <= mode_index < len(self.labels):
            return self.labels[mode_index]
        raise ValueError(
            f"Classification index {mode_index} out of range [0..{len(self.labels) - 1}]"
        )
```

Defined in `tinycua/tools/classification.py`. Configured in `QUERY_ANALYST_BASE_TOOLS`.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tools as module constants | `*_BASE_TOOLS` | Code-level configuration; no runtime config overhead |
| Classification labels in tool | Not in prompt | Changing labels doesn't require prompt edits |
| Native tools in constant | `TASK_EXECUTOR_BASE_TOOLS` | Always available; not optional at runtime |
| `extra_tools` separate | Empty by default | Single injection channel; keeps base tools clean |
