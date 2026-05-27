# TINYCUA Worker Orchestration

> **Category:** Process Spec

> **File:** `architecture/worker-orchestration.md`
> **See also:** [session-architecture.md](session-architecture.md)
> **Last Updated:** 2026-05-27
> **Status:** Draft

This document defines the internal Worker orchestration used in Worker Mode.

---

## Role

The TINYCUA Worker is an internal orchestration of specialized TINYCUA agents. Externally, the user can experience TINYCUA as a single agent, but internally Worker Mode coordinates:

1. Task Analysis
2. Task Execution
3. Task Reviewer

The Worker exists to reduce hallucination by decomposing context exposure. Each internal agent receives only the context required for its role.

These specialized Worker agents may use sub sessions for context isolation, but they are still part of the same TINYCUA agent. They are not the same concept as future explicit Sub Agents. See [session-architecture.md](session-architecture.md).

---

## Inputs / Outputs

**Input:**

- `Digested Information` from Information Digestion.
- `Worker Config`, including `effort`.

**Output:** `Worker Result` for the Primary Agent.

The Worker does not expose the full internal specialized-agent structure to the user unless it needs human clarification.

---

## Sequential Roadmap Model

The Worker executes a sequential task roadmap. The top-level task list is not a dependency graph and is not a parallel execution plan.

If a task contains parallelizable work, that parallelization happens inside Task Execution for that task. The top-level Worker still advances through the roadmap sequentially.

---

## Internal Flow

```mermaid
flowchart TD
    DI{{"Digested Information"}}
    TA["Task Analysis Agent"]
    TL{{"Sequential Task List"}}
    PICK["Pick current task"]
    TC{{"Task Context"}}
    TE["Task Execution Agent"]
    TRS{{"Task Result + Execution Log"}}
    RV["Task Reviewer Agent"]
    DEC{{"Reviewer Decision"}}
    NEXT{"Decision"}
    UPDATE["Consolidate unfinished/upcoming task contexts"]
    REMAIN{"Remaining unfinished tasks?"}
    RETRY["Create new Executor with failure recorded in task context"]
    REPLAN["Call Task Analysis to revise roadmap"]
    ASK["Ask user / pause continuation state"]
    FAIL_TERM["Terminate Worker with failure summary"]
    AGG["Aggregate accepted results"]
    WR{{"Worker Result"}}

    DI --> TA
    TA --> TL
    TL --> PICK
    PICK --> TC
    TC --> TE
    TE --> TRS
    TRS --> RV
    TL -. "shallow list" .-> RV
    RV --> DEC
    DEC --> NEXT
    NEXT -->|accepted| UPDATE
    UPDATE --> REMAIN
    REMAIN -->|Yes| PICK
    REMAIN -->|No| AGG
    NEXT -->|retry| RETRY
    RETRY --> TE
    NEXT -->|replan| REPLAN
    REPLAN --> TA
    NEXT -->|escalate_user| ASK
    NEXT -->|consecutive failure threshold| FAIL_TERM
    FAIL_TERM --> ASK
    AGG --> WR
```

---

## Worker Effort

Worker effort is configuration that controls how much planning happens before execution.

Effort uses planning-depth semantics: `none` means the Worker proceeds quickly with minimal upfront planning, while `high` means the Worker spends more time on thorough planning before execution.

| Effort | Behavior |
|--------|----------|
| None | Create a lightweight roadmap and defer extra decomposition to reviewer-driven recovery. |
| Low | Create an initial roadmap with minimal refinement. |
| Medium | Create an initial roadmap and perform limited sequencing/overlap review. |
| High | Spend more time decomposing and refining the roadmap before execution. |

Effort changes the amount of upfront Task Analysis. It does not change the sequential nature of the top-level task list.

```yaml
worker_config:
  effort: none | low | medium | high
```

---

## Human-in-the-Loop Continuation

Clarification is not task completion. If an internal agent needs user input, the Worker should store continuation state and resume that same internal point after the user replies.

Each specialized agent can have its own sub session with its own `Chat_History` and `Context`. Human-in-the-loop continuation resumes that existing sub session.

Two signaling concepts are recommended:

- `ask` / `question`: agent needs user clarification and pauses.
- `terminate`: agent has actually completed its assigned work.

This prevents a clarification turn from accidentally restarting the whole request from Query Analyst.

---

## Repeated Failure Rule

The Worker tracks a volatile universal consecutive-failure counter. If failures happen N times in a row, the Worker should ask the user and explain the current point of failure.

If any task succeeds, the counter resets to zero.

The Worker only terminates successfully when the final unfinished task is accepted and no remaining unfinished tasks exist. If the final task is retried, replanned, or decomposed into new tasks, the Worker continues. If the consecutive failure threshold is reached, the Worker terminates with a failure summary and asks the user what should happen next.

---

## Worker Result

The Worker Result should contain only accepted task outputs and enough provenance for the Primary Agent to synthesize a final answer without bypassing Worker guarantees.

```yaml
worker_result:
  accepted_results:
    - task_id: task_001
      name: "..."
      result: "..."
  unresolved_items:
    - "..."
  reviewer_notes:
    - "..."
  confidence: 0.0-1.0
```
