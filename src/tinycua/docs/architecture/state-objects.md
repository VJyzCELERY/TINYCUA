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
| `Classification` | Query Analyst | Routing | Chosen label from configurable `ClassificationTool` labels. |
| `Context Enhanced Query` | Query Analyst | Primary Agent / Information Digester | User query enriched with high-level session context during fast routing analysis. |
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

## Classification Object

The Query Analyst uses a `ClassificationTool` with configurable labels to produce a classification.

```yaml
classification:
  label: passthrough | worker   # selected from configured labels
```

`passthrough` routes directly to the Primary Agent. `worker` routes through the full Worker pipeline.

`uncertain` is not a label. If the agent cannot decide, it does not produce a terminal classification; the loop retries or keeps the agent active.

The configured labels depend on context — the root TinyCUA uses `["passthrough", "worker"]`, while the Worker input gate uses `["task_recreation", "task_reanalysis", "proceed_execution"]`.

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

## Task Tree Object

Tasks form a tree structure navigated via DFS pre-order traversal. Each task is a node that may have child tasks (`child_tasks`). Completion status is derived from `task_result.status` for leaf tasks and propagates upward: a container task is complete only when all its children are complete.

- **Leaf task** — a task without `child_tasks` (`None`). Only leaf tasks are executed by the Task Executor.
- **Container task** — a task with `child_tasks`. Container tasks are structural: they hold child tasks but are not themselves executed. Their progress is a function of all children being complete.

DFS pre-order traversal produces a flat sequential display:

```
[ ] - Research topic (t-1)
  [ ] - Gather sources (t-1.1)
  [ ] - Analyze findings (t-1.2)
[x] - Write summary (t-2)
```

This enables automated `advance_task` tooling: traverse the tree, find the first unfinished leaf, and execute it — no manual cursor tracking needed.

```yaml
# Leaf task — no child_tasks, directly executable
task:
  task_id: "<task id>"
  parent_task_id: "<parent task id or null for root>"
  task_name: "<short label>"
  task_description: "<agent-readable description>"
  task_context: "<task-specific context (structured markdown)>"
  success_criteria:
    - "<criterion>"
  confidence: "<numeric>"
  task_result: null | TaskResult
  child_tasks: null

# Container task — has child_tasks, not executed directly
task:
  task_id: "<container task id>"
  parent_task_id: null
  task_name: "<container name>"
  task_description: "<container description>"
  task_context: "<container context>"
  success_criteria:
    - "<criterion>"
  confidence: "<numeric>"
  task_result: null | TaskResult
  child_tasks:
    - task_id: "<child task id>"
      parent_task_id: "<container task id>"
      task_name: "<child name>"
      task_description: "<child description>"
      task_context: "<child context>"
      success_criteria:
        - "<criterion>"
      confidence: "<numeric>"
      task_result: null | TaskResult
      child_tasks: null
```

Nesting can continue to arbitrary depth, controlled by the Worker's `effort` setting. See [task-creation.md](task-creation.md) for the decomposition loop and effort-controlled depth.

### Task Node Fields

Required fields:

- `task_id` — unique identifier for cross-referencing.
- `task_name` — short label for the task.
- `task_description` — agent-readable prose describing what to do.
- `task_context` — task-specific context in structured markdown. May contain relevant facts, constraints, prior accepted results, known gaps, or user clarifications. Context updates may modify this field.
- `success_criteria` — list of criteria for task completion.
- `confidence` — agent-assigned confidence in decomposition or execution readiness. Exact scale is implementation calibration.
- `task_result` — the execution result for this task (`null` if not yet started). For leaf tasks, completion status is derived from `task_result.status`. For container tasks, completion is derived from whether all children are complete.

Optional fields:

- `child_tasks` — list of child `Task` nodes (`null` for leaves). When present, this task is a container and is not executed directly.
- `parent_task_id` — ID of the parent task (`null` for root tasks). Auto-set on children when `child_tasks` is provided; explicit values must match the container's `task_id`.

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
  compromised_results:
    - task_id: "<task id>"
      result: "<unsuccessful result and limitation>"
  # Additional provenance and status fields are implementation detail.
```

The Worker Result keeps accepted outputs separate from compromised unsuccessful limitations and includes enough provenance for the Primary Agent to synthesize a transparent final answer. See [worker-orchestration.md](worker-orchestration.md) for the Worker's internal flow.

---

## Reviewer Decision Object

```yaml
reviewer_decision:
  task_id: "<task id>"
  event_id: "review-<task-local sequence>"
  status: approved | needs_revision | replan | postpone_siblings | postpone_final | compromise
  review_summary: "<complete review; default prompts render a bounded preview>"
  rationale: "<full rationale, available on demand>"
  new_findings:
    - "finding-<task-local sequence>"
  finding_updates:
    - finding_id: "finding-1"
      status: OPEN | ADDRESSED | INVALID | DEFERRED
  context_updates:
    - target_task_id: "<target task id>"
      update: "<context update>"
  review_plan:  # root review only
    - criterion_id: "acceptance-1"
      testability: empirical | judgment
      falsifying_condition: "<what would disprove the criterion>"
      procedure: "<independent check>"
      expected_observation: "<supporting observation>"
  criterion_assessments:  # root review only
    - criterion_id: "acceptance-1"
      result: supported | contradicted | inconclusive | judgment_only
      evidence_ids: ["<runtime observation id>"]
      inference: "<how the observation bears on the criterion>"
      limitations: "<remaining uncertainty>"
  assurance_status: observed | mixed | judgment_only | contradicted | inconclusive
  retry_instructions: "..."  # failure context communication — format and mechanism are implementation detail
```

Findings and review events belong only to their task. Default Executor and Reviewer
prompts receive a bounded digest for the active task; `task_inspect(event_id=...)`
returns one full event, while `field`, `offset`, and `limit` retrieve deterministic
pages of long-form review text. Cross-task facts use explicit validated
`context_updates`.

Task completion and assurance are separate. Completion records that execution and review terminated successfully. Assurance summarizes the kind of support gathered by root review; it is not a universal correctness certificate.

`escalate_user` is not a status. When the ResultReviewer cannot resolve, the agent stays
active with an open question. Human-in-the-loop interaction occurs through passthrough
routing on the next user query. If HITL is disabled, the agent continues exploring.

---

## Agent State / Continuation State

Agent state determines whether the next user message resumes an internal agent or starts a new top-level request.

```yaml
agent_state:
  active_agent: "<agent name>"   # matches the documented name of any architecture agent
  active_task_id: "<active task id>"
  status: idle | running | blocked | terminated
  resume_target: "..."
  failure: 0                      # aggregate failure count from child sessions
```

Clarification is not a terminal state. The agent state distinguishes between pausing for user input (`blocked`) and completing work (`terminated`). Human-in-the-loop replies always continue through the existing agent session/context that asked the question.

The failure counter aggregates failures from child sessions (parent.failure += child.failure), not just consecutive failures in a single node.
