# Task Assessor

> **File:** `docs/design/agent_sessions/task_assessor.md`
> **Package:** `tinycua.agent_nodes.task_assessor`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`TaskAssessor` evaluates the current task tree and decides whether TaskAnalyzer should
run another decomposition/update pass. It is orchestrated by `TinyCUAWorker` inside the
Task Decomposition OuterLoop.

Outputs:

1. `verdict`: `"analyze"` or `"stop"`
2. `analysis`: markdown query/instructions for the next TaskAnalyzer pass

---

## Completed Task Policy

TaskAssessor should avoid selecting completed tasks for update. It should assess
incomplete, blocked, failed, in-progress, or not-started branches.

If all relevant branches are complete or no incomplete branch requires further
planning, the verdict should be `stop`.

---

## `run()` Method

```text
run(query: str) -> AsyncIterator[dict]
```

`query` may be a plain analysis query or include `TaskAnalyzerState` YAML front-matter.

Flow:

```text
run(query)
  1. parsed_state = AgentState.from_string(query)
  2. build instruction: base + current task tree + completed-task policy
  3. build SDK Agent with AssessorVerdict ClassificationTool and read-only task tools
  4. agent.run(query=query, messages=self.session.session_context, stream=True)
  5. TaskAssessorLoop enforces verdict tool call
  6. write TaskAssessorState to session.agent_state
```

---

## Tools

```text
TASK_ASSESSOR_BASE_TOOLS = [
  ClassificationTool(name="classify", labels=["analyze", "stop"]),
  *READ_ONLY_TASK_TOOLS,
]
```

TaskAssessor is read-only. It decides what needs analysis; TaskAnalyzer performs
mutations.

---

## Output: TaskAssessorState

```text
TaskAssessorState(
  type="task_assessor",
  status="terminated",
  failure=0,
  verdict="analyze" | "stop",
  analysis="markdown instructions for TaskAnalyzer",
)
```

If the classification tool is missing after retries, fallback is `stop` to prevent
infinite decomposition loops.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Read-only assessor | No write tools | Assessment should not mutate tasks |
| Completed task avoidance | Do not select completed tasks for update | Preserves finished work |
| Mandatory verdict | Loop retries missing classification | OuterLoop needs deterministic routing |
| Safe fallback | `stop` | Prevents infinite planning loops |
| AgentState output | `TaskAssessorState` | Serializable verdict + analysis |

---

## See also

Prev : [`TaskAnalyzer`](task_analyzer.md) | Next : [`TaskExecutor`](task_executor.md)

## Related

- [TinyCUAWorker OuterLoop](../orchestration/worker.md#task-decomposition-outerloop)
- [TaskAssessorState](../state/information.md#taskassessorstate)
- [Classification constants](../constants/tools.md)
