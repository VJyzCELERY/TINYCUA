# Task Execution (Inside TINYCUA Worker)

> **Category:** Agent Spec

> **File:** `architecture/task-execution.md`
> **See also:** [overview.md](overview.md), [session-architecture.md](session-architecture.md), [worker-orchestration.md](worker-orchestration.md), [task-analysis.md](task-analysis.md), [task-reviewer.md](task-reviewer.md)

---

## Role

The Task Execution Agent executes one task from the sequential roadmap.

It receives only the current task's information plus shallow roadmap awareness. It should not receive the full parent session `Context` or full previous task details by default.

---

## Inputs / Outputs

**Input:**

```yaml
task:
  task_id: task_001
  name: "..."
  description: "..."
  context: "..."
  success_criteria:
    - "..."
  confidence: 0.0-1.0
shallow_task_list:
  - task_id: task_001
    name: "..."
  - task_id: task_002
    name: "..."
retry_context: "optional failure context from reviewer"
```

Retries create a new Task Execution agent sub session. The previous failure is recorded in the task context/retry context so the new executor can continue with the relevant lesson without inheriting the full prior executor context.

**Output:**

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

## Internal Flow

```mermaid
flowchart TD
    TASK{{"Current Task + Context"}}
    THINK["Think: plan short-term todo/action"]
    ACT["Act: use tool or reason"]
    OBSERVE["Observe result"]
    LOG["Update execution log"]
    DONE{"Stop condition met?"}
    RESULT{{"Task Result + Execution Log"}}

    TASK --> THINK
    THINK --> ACT
    ACT --> OBSERVE
    OBSERVE --> LOG
    LOG --> DONE
    DONE -->|No| THINK
    DONE -->|Yes| RESULT
```

---

## Stop Conditions

Task Execution should stop when:

- success criteria are satisfied;
- the task is out of scope;
- a sequencing issue is discovered;
- context is insufficient;
- the task appears incorrectly specified;
- a required tool/action fails;
- uncertainty is too high and should be reviewed instead of guessed.

If a later roadmap task appears to be needed first, Task Execution should return `blocked` with a sequencing explanation.

---

## Execution Log

The execution log is evidence for Task Reviewer. It should include:

- short-term todos generated during execution;
- tool actions and observations;
- human-in-the-loop user inputs;
- concise decision trace or reasoning summary.

This avoids forcing the Reviewer to ingest the full raw execution session.

If Task Execution asks the user for clarification, the user reply resumes the same Task Execution sub session. Clarification is not a terminal state.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Context scope | Current task context only | Prevents unrelated context from polluting execution |
| Roadmap awareness | Shallow task list | Helps scope control without exposing future task details |
| Output | Result + execution log | Gives Reviewer evidence for acceptance and context propagation |
| Failure handling | Return explicit status | Reviewer decides retry, replan, escalation, or context update |
