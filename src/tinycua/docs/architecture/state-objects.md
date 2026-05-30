# Architecture State Objects

> **Category:** Reference Spec

> **File:** `architecture/state-objects.md`
> **Last Updated:** 2026-05-30
> **Status:** Implemented
> **See also:** [session-architecture.md](session-architecture.md), [overview.md](overview.md), [query-analyst.md](query-analyst.md), [information-digestion.md](information-digestion.md), [worker-orchestration.md](worker-orchestration.md), [task-creation.md](task-creation.md), [task-analysis.md](task-analysis.md), [task-execution.md](task-execution.md), [result-reviewer.md](result-reviewer.md), [primary-agent.md](primary-agent.md)

This document defines the shared state and data objects used across the TINYCUA architecture docs.

**This is the canonical source for all cross-cutting shared data structures.** Component-specific schemas that are consumed by only one agent are documented in their own files, but any schema shared between two or more components lives here.

---

## Core Principle

TINYCUA decomposes work by decomposing **context exposure**. State objects should make it clear which agent sees which information, and where execution resumes when human-in-the-loop clarification happens.

---

## Top-Level Objects

| Object | Producer | Consumer | Purpose |
|--------|----------|----------|---------|
| `User Query` | User | Query Analyst | Latest user instruction. |
| `Session` | Session system | Query Analyst / Information Digester / agents | Contains `chat_history`, model-loaded `Context`, and sub-session `execution_log`. See [session-architecture.md](session-architecture.md). |
| `Context Enhanced Query` | Query Analyst | Primary Agent / Information Digester | User query enriched with high-level session context during fast routing analysis. |
| `Mode Decision` | Query Analyst | Routing (see [overview.md](overview.md)) | Chooses `primary_agent`, `worker`, or `uncertain` based on mode. |
| `Digested Information` | Information Digester | Task Analyzer / Primary Agent | Precision-oriented summary of relevant context and advisory instruction. Canonical schema below. |
| `Worker Config` | System/user configuration | TINYCUA Worker / Task Analyzer | Controls Worker behavior such as planning effort. |
| `Worker Result` | TINYCUA Worker | Primary Agent | Aggregated result from accepted sequential tasks. Canonical schema below. |
| `Response` | Primary Agent | User | Final user-facing answer. |

---

## Session Object

The canonical Session schema is defined in [session-architecture.md](session-architecture.md).

Use `Session.context` for model-loadable context and `Session.chat_history` for preserved turns. Use `Session.execution_log` for actions and outcomes from sub-session execution.

See [session-architecture.md](session-architecture.md) for the complete schema rules, compaction behavior, and sub-session propagation contract.

---

## Execution Log Object

The Execution Log captures the actions taken during a sub-session's execution. It is stored on the sub-session, not embedded within a Task Result. This separation means the Reviewer can inspect the full execution log of a Task Executor's sub-session, and retries create new sub-sessions with fresh logs.

The execution log should capture:

- the sequence of actions taken and their outcomes;
- human-in-the-loop inputs received during execution;
- a concise decision trace or reasoning summary.

Key rules:

- The Execution Log belongs to a sub-session, not to a specific task result.
- Retries create new Task Executor sub-sessions, so each retry starts with a fresh execution log.
- The Result Reviewer accesses the sub-session's execution log when evaluating a task.

---

## Mode Decision Object

The Query Analyst produces a mode decision instead of a binary small/large verdict.

```yaml
mode_decision:
  mode: primary_agent | worker | uncertain
  score: "<numeric>"  # exact scale is implementation calibration
  confidence: "<numeric>"  # exact scale is implementation calibration
  reasons:
    - "..."
  uncertain_next_action: ask_user | explore | null
```

`reasons` must include a rationale appropriate to the chosen mode (e.g., safety rationale for `primary_agent`, decomposition benefit for `worker`, or uncertainty description for `uncertain`).

`uncertain_next_action` is required when `mode` is `uncertain`. The goal is to avoid leaving uncertainty as an open-ended state.

---

## Digested Information Object

The Information Digester produces `Digested Information` — a precision-oriented summary consumed by the Task Analyzer (Worker Mode) and the Primary Agent (when it invokes Information Digestion).

```yaml
digested_information:
  context_summary: "<compressed relevant context (markdown)>"   # required
  key_points:                                                   # required
    - "<takeaway point>"
  advisory_instructions: "<action-oriented guidance>"           # optional
  constraints:                                                  # optional
    - "<guardrail>"
  known_gaps:                                                   # optional
    - "<missing information>"
```

Key rules:
- Context Summary and Key Points are required. Advisory Instructions, Constraints, and Known Gaps may be empty if not applicable.
- The Information Digester is a privileged narrowing boundary: it may inspect broad session `Context`, but downstream agents receive only this consolidated output.
- See [information-digestion.md](information-digestion.md) for the Information Digester's internal flow and design decisions.

---

## Worker Config Object

Worker effort is configuration, similar to model reasoning effort.

```yaml
worker_config:
  effort: none | high   # Additional intermediate levels are implementation calibration detail
```

Effort controls how much planning happens before execution.

- `none` — minimal upfront planning; refine during execution.
- `high` — thorough planning; full decomposition before execution.

---

## Task List Object

The `Task List` is a sequential roadmap. It is not a dependency graph and is not intended to be parallelized at the top level.

If part of a task can be parallelized, that parallelization belongs inside the task execution strategy, not in the top-level task list schema.

### Nested Task Lists

During the Task Creation loop, complex tasks may be decomposed into sub-tasks. This produces a nested tree structure where a task item can contain a `tasks` field holding a sub-list.

- **Leaf task** — a task without a `tasks` field. Only leaf tasks are executed by the Task Executor.
- **Container task** — a task with a `tasks` field. Container tasks are structural: they hold a sub-list but are not themselves executed. Their `name` and `description` describe the container's purpose; the actual work is defined by their child tasks.

```yaml
task_list:
  tasks:
    # Leaf task — no `tasks` field
    - task_id: "<task id>"
      name: "<task name>"
      description: "<task description>"
      context: "<task-specific context (structured markdown)>"
      success_criteria:
        - "<criterion>"
    # Container task — has `tasks` sub-list, not executed
    - task_id: "<container task id>"
      name: "<container name>"
      description: "<container description>"
      context: "<container context>"
      success_criteria: []
      tasks:
        - task_id: "<child task id>"
          name: "<child name>"
          description: "<child description>"
          context: "<child context>"
          success_criteria:
            - "<criterion>"
  current_task_id: "<current task id>"
```

Nesting can continue to arbitrary depth, controlled by the Worker's `effort` setting. See [task-creation.md](task-creation.md) for the decomposition loop and effort-controlled depth.

The `context` field should be structured markdown. It may contain relevant facts, constraints, prior accepted results, known gaps, or user clarifications. Context updates may modify a task's `context` field — they can replace or add to existing context. The architecture does not prescribe a specific consolidation strategy.

### Task Object

Required fields:

- `task_id`
- `name`
- `description`
- `context`
- `success_criteria`
- `confidence` — agent-assigned confidence in the task's decomposition or execution readiness. Exact scale is implementation calibration.

Optional fields:

- `tasks` — a nested sub-list of task objects. When present, this task is a container and is not executed.

Additional fields may be introduced if justified by a later design decision.

---

## Task Result Object

```yaml
task_result:
  task_id: "<task id>"
  status: completed | failed | blocked
  result: "..."
  discovered_sequence_issues:
    - "..."
  uncertainty_notes:
    - "..."
```

---

## Worker Result Object

The Worker Result aggregates accepted task outputs for the Primary Agent to synthesize into a final response.

```yaml
worker_result:
  accepted_results:
    - task_id: "<task id>"
      name: "<task name>"
      result: "<task result>"
  # Additional provenance and status fields are implementation detail.
```

The Worker Result should contain only accepted task outputs and enough provenance for the Primary Agent to synthesize a final answer without bypassing Worker guarantees. See [worker-orchestration.md](worker-orchestration.md) for the Worker's internal flow.

---

## Reviewer Decision Object

```yaml
reviewer_decision:
  task_id: "<task id>"
  status: accepted | retry | replan | escalate_user
  reason: "..."
  confidence: "<numeric>"  # exact scale is implementation calibration
  context_updates:
    - target_task_id: "<target task id>"
      update: "<context update>"
  retry_instructions: "..."  # failure context communication — format and mechanism are implementation detail
```

---

## Agent State / Continuation State

Agent state determines whether the next user message resumes an internal agent or starts a new top-level request.

```yaml
agent_state:
  active_agent: "<agent name>"   # matches the documented name of any architecture agent
  active_task_id: "<active task id>"
  status: idle | running | blocked | terminated
  resume_target: "..."
  consecutive_failures: 0
```

Clarification is not a terminal state. The agent state distinguishes between pausing for user input (`blocked`) and completing work (`terminated`). Human-in-the-loop replies always continue through the existing agent session/context that asked the question.

The consecutive failure counter resets after any successful task because failure escalation is based on N failures **in a row**.
