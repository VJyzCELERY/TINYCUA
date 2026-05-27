# Task Analysis (Inside TINYCUA Worker)

> **Category:** Agent Spec

> **File:** `architecture/task-analysis.md`
> **See also:** [overview.md](overview.md), [worker-orchestration.md](worker-orchestration.md), [state-objects.md](state-objects.md), [task-execution.md](task-execution.md), [task-reviewer.md](task-reviewer.md)

---

## Role

The Task Analysis Agent receives `Digested Information` and creates a sequential task roadmap for the Worker.

The roadmap is not a dependency graph and is not intended to be parallelized at the top level. If parallel work is useful, it belongs inside an individual task's execution strategy.

---

## Inputs / Outputs

**Input:**

- `Digested Information`
- `Worker Config` with `effort`

**Output:** `Task List`

```yaml
task_list:
  tasks:
    - task_id: task_001
      name: "Short task name"
      description: "What this task should accomplish"
      context: "Only the context this task needs"
      success_criteria:
        - "Semantic condition for success"
      confidence: 0.0-1.0
```

Required task fields:

- `task_id`
- `name`
- `description`
- `context`
- `success_criteria`
- `confidence`

Avoid rigid visible fields such as `required_tools`, `expected_output`, `max_depth`, or dependencies.

The `context` field should be structured markdown. It should remain small and focused. Updating context means consolidating information, not blindly appending more information.

---

## Long-Term Tasks vs Short-Term Todos

Task Analysis produces long-term tasks: the sequential roadmap needed to satisfy the user request.

Task Execution may create short-term todos while executing one task. Those todos belong in the execution log, not in the top-level roadmap.

---

## Effort-Controlled Decomposition

Task Analysis may run one or more refinement passes depending on Worker effort.

| Effort | Task Analysis Behavior |
|--------|------------------------|
| None | Create an initial roadmap quickly and allow Reviewer recovery to refine later. |
| Low | Create the roadmap with minimal upfront refinement. |
| Medium | Create the roadmap and perform limited overlap/sequencing review. |
| High | Thoroughly decompose and refine before execution begins. |

---

## Internal Flow

```mermaid
flowchart TD
    DI{{"Digested Information"}}
    CREATE["Create initial sequential roadmap"]
    EFFORT{"Effort allows refinement?"}
    REFINE["Optional per-task decomposition pass"]
    REVIEW["Review overlap and sequencing"]
    ASSIGN["Assign each task context"]
    TL{{"Task List"}}

    DI --> CREATE
    CREATE --> EFFORT
    EFFORT -->|Yes| REFINE
    EFFORT -->|No| REVIEW
    REFINE --> REVIEW
    REVIEW --> ASSIGN
    ASSIGN --> TL
```

---

## Replanning Requests

Task Reviewer may ask Task Analysis to revise the roadmap when:

- a task is too broad;
- a task should be split;
- task ordering is wrong;
- a result reveals missing context;
- repeated failures suggest the roadmap is flawed.

`needs_more_context` from the Reviewer is handled by Task Analysis. Task Analysis may revise the current task context, split the task, or ask the broader orchestration layer for renewed digestion when the existing digest is insufficient.

The Reviewer should request replanning rather than directly rewriting the decomposition semantics.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Roadmap shape | Sequential list | Keeps orchestration simple and avoids dependency-graph complexity |
| Task schema | Lightweight | Reduces prompt overhead and rigidity |
| Success definition | Semantic success criteria | Avoids overfitting to predicted exact outputs |
| Decomposition depth | Effort-controlled | Allows faster or more thorough Worker behavior |
