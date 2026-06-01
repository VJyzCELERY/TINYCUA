# TaskExecutorLoop

> **File:** `docs/design/loops/task_executor_loop.md`
> **Package:** `tinycua.loops.task_executor_loop`
> **Last Updated:** 2026-06-01

---

## Role

`TaskExecutorLoop` is a custom SDK `BaseLoop` subclass for TaskExecutor. It gives the
SDK loop access to `Session`, preserves streaming events, observes active-task result
updates, and writes `TaskExecutorState` reflecting the current active task outcome.

---

## SDK Loop Shape

```text
class TaskExecutorLoop(ReActLoop):
    def __init__(self, session: Session):
        super().__init__(session)
        self.session = session

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        ...  # SDK BaseLoop-compatible override
```

---

## Loop-Local Data

```text
execution_attempts: int
tool_results: list[dict]
failure: int
```

The authoritative task result is read from `session.task` after tool execution. The
loop should not invent a task result if `UpdateActiveTaskResult` was not used.

---

## Algorithm Inside `run(...)`

1. Run the SDK loop/LLM pass with TaskExecutor tools.
2. If `stream=True`, yield every SDK event outward.
3. Observe tool results for audit/failure accounting.
4. After the SDK pass, inspect `session.get_active_task()` / `session.task`.
5. If the active task has terminal `TaskResult.status`, mark executor terminated.
6. If the task result is non-terminal or missing, leave executor active (`running`).
7. Write `TaskExecutorState`. Emit final-result event only when terminal.

---

## Final State

```text
TaskExecutorState(
  type="task_executor",
  status="terminated" | "running" | "blocked",
  failure=failure,
  task_id=active_task.task_id if active_task else None,
  task_result=active_task.task_result if active_task else None,
  execution_attempts=execution_attempts,
  tool_results=tool_results,
)
```

---

## Termination Rule

| Active task result | Loop status |
|--------------------|-------------|
| `completed` | terminal |
| `failed` | terminal + failure increment |
| `blocked` | terminal/blocked |
| `inprogress` | active/running |
| `not_started` | active/running |
| missing result | active/running |

The loop should not force a retry just because the agent did not finish. Long-running
execution can remain active.

---

## Related

- [TaskExecutor AgentNode](../agent_node/task_executor.md)
- [TaskExecutorState](../state/information.md#taskexecutorstate)
