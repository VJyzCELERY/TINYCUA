# Formula 3: Task Executor Context

## Definition

Each TaskExecutorNode invocation operates with a bounded, isolated context. This is the key mechanism preventing context contamination.

## Context Composition

```
C(executor_i) = task_context(active_task) + selected_tools
```

Where:

### Active Task Context

```
task_context(active_task) = {
  task structure (name, description, criteria),
  task status and result (if retry),
  failure context (if retry)
}
```

### Tool Scope

The TaskExecutorNode has a restricted tool set:
- Active task execution tools (execute current task, update result)
- `enhanced_context_retrieval` (search scoped context)
- Selected outer Agent tools (per tool policy)
- HITL / mandatory passthrough (if blocked on user input)

### Tool Restrictions

```
TaskExecutorNode CANNOT:
  - Select active task (ownership belongs to loop)
  - Edit active task or mutate task tree
  - Spawn InformationDigesterNode
```

## Isolation Properties

1. **No session history**: The executor does not receive prior conversation history or other nodes' outputs.
2. **No cross-task contamination**: Other tasks' contexts are invisible to this executor.
3. **Tool-bounded**: The executor can only act within its restricted tool scope.
4. **ReAct bounded**: Execution is bounded by `max_steps`, preventing unbounded context growth within a single task.
