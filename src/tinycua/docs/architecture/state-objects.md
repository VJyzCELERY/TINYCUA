# Architecture State Objects

> **Category:** Reference Spec

> **File:** `architecture/state-objects.md`
> **See also:** [session-architecture.md](session-architecture.md)
> **Last Updated:** 2026-05-27
> **Status:** Draft

This document defines the shared state and data objects used across the TINYCUA architecture docs.

**This is the canonical source for all shared data structures.** Other docs reference these schemas rather than duplicating them, so changes to shared objects only need to happen here.

---

## Core Principle

TINYCUA decomposes work by decomposing **context exposure**. State objects should make it clear which agent sees which information, and where execution resumes when human-in-the-loop clarification happens.

---

## Top-Level Objects

| Object | Producer | Consumer | Purpose |
|--------|----------|----------|---------|
| `User Query` | User | Query Analyst | Latest user instruction. Query size does not trigger enhanced retrieval by itself. |
| `Session` | Session system | Query Analyst / Information Digester / agents | Contains `Chat_History`, model-loaded `Context`, and sub-session `execution_log`. See [session-architecture.md](session-architecture.md). |
| `Context Enhanced Query` | Query Analyst | Primary Agent / Information Digester | User query enriched with relevant session `Context` when needed. |
| `Mode Decision` | Query Analyst | Top-level router | Chooses `primary_agent`, `worker`, or `uncertain`. |
| `Digested Information` | Information Digester | Task Analyzer / Primary Agent | Precision-oriented summary of relevant context and advisory instruction. Canonical schema in [information-digestion.md](information-digestion.md). |
| `Worker Config` | System/user configuration | TINYCUA Worker / Task Analyzer | Controls Worker behavior such as planning effort. |
| `Worker Result` | TINYCUA Worker | Primary Agent | Aggregated result from accepted sequential tasks. Canonical schema in [worker-orchestration.md](worker-orchestration.md). |
| `Response` | Primary Agent | User | Final user-facing answer. |

---

## Session Object

Session internals are defined in [session-architecture.md](session-architecture.md). The core shape is:

```yaml
session:
  session_id: session_001
  owner_type: primary | tinycua_internal | future_sub_agent
  owner_name: "Primary Agent"
  chat_history: []   # JSON turn/message records
  context: "structured markdown loaded by the model"
  execution_log: []  # tool calls, results, and diffs generated during sub-session execution
```

Important rules:

- `Chat_History` is the preserved turn log and should be JSON.
- `Context` is structured markdown and is what the model loads.
- Enhanced context retrieval starts when session `Context` approaches model context-window pressure.
- Sub-sessions keep their own `Chat_History`, `Context`, and `execution_log`, but sub-session `Chat_History` is propagated to primary session `Chat_History`.
- Sub-session `Context` is not automatically appended to primary session `Context`.
- Sub-session `execution_log` is not automatically propagated to primary session `execution_log`.

Use `Session.Context` for model-loadable context and `Session.Chat_History` for preserved turns. Use `Session.execution_log` for tool calls, results, and diffs from sub-session execution.

---

## Execution Log Object

The Execution Log captures the actions taken during a sub-session's execution. It is stored on the sub-session, not embedded within a Task Result. This separation means the Reviewer can inspect the full execution log of a Task Executor's sub-session, and retries create new sub-sessions with fresh logs.

```yaml
execution_log:
  short_term_todos:
    - "..."
  actions:
    - action: "..."
      observation: "..."
      diff: "optional file change diff if applicable"
  hitl_inputs:
    - "..."
  decision_trace: "..."
```

Key rules:

- The Execution Log belongs to a sub-session, not to a specific task result.
- Tool calls, observations, and diffs are recorded as part of the execution log.
- Retries create new Task Executor sub-sessions, so each retry starts with a fresh execution log.
- The Task Reviewer accesses the sub-session's execution log when evaluating a task.
- Human-in-the-loop inputs are preserved in the execution log.

---

## Mode Decision Object

The Query Analyst produces a mode decision instead of a binary small/large verdict.

```yaml
mode_decision:
  mode: primary_agent | worker | uncertain
  score: 0-10
  confidence: 0.0-1.0
  reasons:
    - "..."
  primary_agent_safety_reason: "..."        # required for primary_agent
  decomposition_benefit: "..."             # required for worker
  uncertainty_reason: "..."                # required for uncertain
  uncertain_next_action: ask_user | explore | null
```

`uncertain_next_action` is required when `mode` is `uncertain`. The goal is to avoid leaving uncertainty as an open-ended state.

---

## Worker Config Object

Worker effort is configuration, similar to model reasoning effort.

```yaml
worker_config:
  effort: none | low | medium | high
```

Effort uses planning-depth semantics:

- `none`: move quickly with minimal upfront planning;
- `low`: light upfront refinement;
- `medium`: limited sequencing/overlap review;
- `high`: thorough roadmap planning before execution.

---

## Task List Object

The `Task List` is a sequential roadmap. It is not a dependency graph and is not intended to be parallelized at the top level.

If part of a task can be parallelized, that parallelization belongs inside the task execution strategy, not in the top-level task list schema.

```yaml
task_list:
  tasks:
    - task_id: task_001
      name: "..."
      description: "..."
      context: "..."
      success_criteria:
        - "..."
      confidence: 0.0-1.0
  current_task_id: task_001
```

The `context` field should be structured markdown, not an unbounded raw dump. It may contain relevant facts, constraints, prior accepted results, known gaps, or user clarifications. Context updates should consolidate information; they may reduce or replace stale information rather than only append more text.

### Task Object

Required fields:

- `task_id`
- `name`
- `description`
- `context`
- `success_criteria`
- `confidence`

Avoid adding rigid per-task fields such as `required_tools`, `expected_output`, `max_depth`, or dependency lists unless a later design explicitly justifies them.

---

## Task Result Object

```yaml
task_result:
  task_id: task_001
  status: completed | partial | failed | blocked | insufficient_context | incorrect_task_spec | tool_failure | out_of_scope
  result: "..."
  discovered_sequence_issues:
    - "..."
  uncertainty_notes:
    - "..."
```

---

## Reviewer Decision Object

```yaml
reviewer_decision:
  task_id: task_001
  status: accepted | retry | replan | needs_more_context | escalate_user
  reason: "..."
  confidence: 0.0-1.0
  context_updates:
    - target_task_id: task_004
      update: "..."
  retry_instructions: "..."
  replan_request: "..."
  failure_count_snapshot:
    consecutive_failures: 0
```

---

## Agent State / Continuation State

Agent state determines whether the next user message resumes an internal agent or starts a new top-level request.

```yaml
agent_state:
  active_agent: query_analyst | information_digestion | task_analysis | task_execution | task_reviewer | primary_agent
  active_task_id: task_001
  status: running | waiting_for_user | terminated
  resume_target: "..."
  consecutive_failure_count: 0
```

Clarification is not a terminal state. Agents should use an `ask` / `question` mechanism when they need user input and a `terminate` signal when their work is actually complete. Human-in-the-loop replies always continue through the existing agent session/context that asked the question.

The consecutive failure counter resets after any successful task because failure escalation is based on N failures **in a row**.
