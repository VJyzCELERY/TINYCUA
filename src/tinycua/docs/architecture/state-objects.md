# Architecture State Objects

> **Category:** Reference Spec

> **File:** `architecture/state-objects.md`
> **Last Updated:** 2026-05-27
> **Status:** Draft

This document defines the shared state and data objects used across the TINYCUA architecture docs.

---

## Core Principle

TINYCUA decomposes work by decomposing **context exposure**. State objects should make it clear which agent sees which information, and where execution resumes when human-in-the-loop clarification happens.

---

## Top-Level Objects

| Object | Producer | Consumer | Purpose |
|--------|----------|----------|---------|
| `User Query` | User | Query Analyst | Latest user instruction. Query size does not trigger enhanced retrieval by itself. |
| `Full Session Context` | Session store | Query Analyst / Information Digestion | Accumulated chat history and session artifacts. Stored in a dynamically retrievable form. |
| `Context Enhanced Query` | Query Analyst | Information Passthrough / Information Digestion | User query enriched with relevant session context when needed. |
| `Mode Decision` | Query Analyst | Top-level router | Chooses `passthrough`, `digestion_only`, `worker`, or `uncertain`. |
| `Digested Information` | Information Digestion | Task Analysis / Primary Agent | Precision-oriented summary of relevant context and advisory instruction. |
| `Worker Result` | TINYCUA Worker | Primary Agent | Aggregated result from accepted sequential tasks. |
| `Response` | Primary Agent | User | Final user-facing answer. |

---

## Session Context Object

`Full Session Context` is accumulated over time. Every user-query/agent-response turn should be stored in a dynamically retrievable form.

Suggested shape:

```yaml
full_session_context:
  turns:
    - turn_id: turn_001
      user_query: "..."
      agent_response: "..."
      timestamp: "..."
      retrievable_notes:
        - "..."
      entities:
        - "..."
  compacted_summaries:
    - summary_id: summary_001
      covers_turns: [turn_001, turn_002]
      summary: "..."
  token_estimate: 12000
```

Enhanced context retrieval starts when this accumulated context reaches a configured token-size threshold. If the session is still small, the system can use the available context directly.

---

## Mode Decision Object

The Query Analyst produces a mode decision instead of a binary small/large verdict.

```yaml
mode_decision:
  mode: passthrough | digestion_only | worker | uncertain
  score: 0-10
  confidence: 0.0-1.0
  reasons:
    - "..."
  direct_response_safety_reason: "..."      # required for passthrough
  decomposition_benefit: "..."             # required for worker
  uncertainty_reason: "..."                # required for uncertain
```

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
  execution_log:
    short_term_todos:
      - "..."
    actions:
      - action: "..."
        observation: "..."
    hitl_inputs:
      - "..."
    decision_trace: "..."
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
  status: accepted | retry | replan | needs_more_context | blocked_by_sequence | escalate_user | escalate_outer_loop
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

Clarification is not a terminal state. Agents should use an `ask` / `question` mechanism when they need user input and a `terminate` signal when their work is actually complete.

The consecutive failure counter resets after any successful task because failure escalation is based on N failures **in a row**.
