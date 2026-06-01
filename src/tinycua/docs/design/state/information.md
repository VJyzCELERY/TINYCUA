# Per-Agent State

> **File:** `docs/design/state/information.md`
> **Package:** `tinycua.state.information`
> **Last Updated:** 2026-06-01

---

## Role

Agent result state is centralized on `Session.agent_state`. Each AgentNode has its
own agent-specific state class that extends `AgentState` (see [agent_state.md](agent_state.md)).
These subclasses hold the node's output fields and inherit YAML front-matter
serialization (`to_yaml()` / `from_string()`) from the base class.

---

## State Type Hierarchy

```
AgentState (base)                     # type, status, failure, agent_config
 ├── QueryAnalystState               # classification + context-enhanced query fields
 ├── InformationDigesterState        # digested_information, retrieval_iterations
 ├── TaskAnalyzerState               # analysis_summary
 ├── TaskAssessorState               # verdict, analysis
 ├── TaskExecutorState               # task_result, execution_attempts
 ├── ResultReviewerState             # reviewer_decision, context_updates
  ├── PrimaryAgentState               # final_response, citations
  └── TinyCUAWorkerState              # worker graph result/restart signal
```

All subclasses inherit `to_yaml()` and participate in `from_string()` via the
`_AGENT_STATE_REGISTRY`. See [AgentState serialization](agent_state.md#serialization--yaml-front-matter-bridge).

---

## QueryAnalystState

```text
QueryAnalystState <: AgentState
  · type: str = "query_analyst"
  · classification: str | None = None       # selected label from configured ClassificationTool labels
  · context: str | None = None            # agent's context analysis markdown
  · query: str | None = None              # original user query (passed through)
```

> `classification` comes from `ClassificationTool`.
> `context` is the first-response text (context analysis). `query` is the original
> user query.

---

## InformationDigesterState

```text
InformationDigesterState <: AgentState
  · type: str = "information_digester"
  · context_summary: str | None = None      # compressed relevant context (markdown)
  · key_points: list[str] | None = None     # key takeaway points
  · advisory_instructions: str | None = None
  · constraints: list[str] | None = None
  · known_gaps: list[str] | None = None
  · retrieval_iterations: int = 0
```

---

## TaskAnalyzerState

```text
TaskAnalyzerState <: AgentState
  · type: str = "task_analyzer"
  · analysis_summary: str | None = None    # markdown summary of created/modified/deleted tasks
```

TaskAnalyzer may receive worker input-gate classification from a preceding
`QueryAnalystState`, not from `TaskAnalyzerState` itself:

```text
---  # Worker input gate classification for TaskAnalyzer
type: query_analyst
classification: task_recreation  # or task_reanalysis or proceed_execution
---
<query>
```

When a worker input gate classifies `task_recreation`, the Worker graph clears the
current task tree and terminates itself so TinyCUA can create a fresh Worker. When a
worker input gate classifies `task_reanalysis`, `TaskInit` is injected only if
`worker.session.task is None`; otherwise TaskAnalyzer only has structural write tools.

---

## TaskAssessorState

```text
TaskAssessorState <: AgentState
  · type: str = "task_assessor"
  · verdict: Literal["analyze", "stop"] | None = None
  · analysis: str | None = None   # agent's markdown response (→ TaskAnalyzer query)
```

---

## TaskExecutorState

```text
TaskExecutorState <: AgentState
  · type: str = "task_executor"
  · task_id: str | None = None              # task that was executed
  · task_result: TaskResult | None = None   # execution outcome
  · execution_attempts: int = 0
  · tool_results: list[dict] | None = None
```

---

## ResultReviewerState

```text
ResultReviewerState <: AgentState
  · type: str = "result_reviewer"
  · decision: Literal["accept", "retry", "replan"] | None = None
  · reason: str | None = None
  · context_updates: list[dict] | None = None   # [{"task_id": str, "context": str}, ...]
  · retry_instructions: str | None = None
```

### Removed: `escalate_user`

When the reviewer cannot decide, it simply **does not call the classification tool**.
The loop does not write a terminal result, leaving the agent active with an open
question. The next user query passthrough routes back to ResultReviewer, allowing
a human-in-the-loop pattern without a dedicated escalation mode.

---

## PrimaryAgentState

```text
PrimaryAgentState <: AgentState
  · type: str = "primary_agent"
  · final_response: str | None = None
  · citations: list[str] | None = None
```

PrimaryAgent is **not transient** — it inherits the parent session. When it receives
a `QueryAnalystState` via front-matter, it appends the context to the parent's
`session_context` as an assistant message and executes the user's query against the
full parent context.

---

## TinyCUAWorkerState

```text
TinyCUAWorkerState <: AgentState
  · type: str = "tinycua_worker"
  · restart_requested: bool = False
  · handoff_query: str | None = None
  · worker_result: WorkerResult | None = None
```

The parent TinyCUA graph consumes this state without inspecting the worker's internal
queue. `restart_requested=True` means TinyCUA should create a new worker and schedule
`handoff_query` against it.

---

## Usage

Each AgentNode owns a session. The loop updates that session's agent state:

```text
class QueryAnalyst(AgentNode):
    __init__(config=None) →
        super().__init__(config=config)
    async run(query: str) →
        # QueryAnalystLoop writes session.agent_state (QueryAnalystState instance)
        ...
```

State is already stored on the session when the agent runs:

```text
# QueryAnalyst auto-creates its own session:
analyst = QueryAnalyst(config)
root_session.add_child(analyst.session)

# After run, state is on the session:
qa_state = analyst.session.agent_state  # QueryAnalystState instance
query = qa_state.to_yaml() + "\n" + user_query  # pass to next node

# Receiver:
parsed = AgentState.from_string(query)
if isinstance(parsed, QueryAnalystState):
    # Access fields directly
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| All states extend AgentState | Single base with `type` discriminator | `from_string()` auto-detects; consistent serialization |
| No intermediate ABC | Extends `AgentState` directly | `StateInformation` was unnecessary indirection |
| Per-agent state classes | One class per AgentNode type | Each node's output shape is semantically different |
| Serialization inherited | `AgentState.to_yaml()` / `from_string()` | No custom code needed per state class |
| CEQ embedded in QueryAnalystState | Context + query are fields, not a separate object | Keeps QueryAnalyst's output self-contained in one state object |
| State stored per session | `Session.agent_state` on each agent's node | Walk the tree to find any agent's state; no central dict needed |

---

## See also

Prev : [`StateObject` Base Class + Serialization](state_object.md) | Next : [`AgentState` Lifecycle Tracking](agent_state.md)

## Related

- [Each state is stored on its own Session.agent_state](session.md)
- [AgentState base class with serialization](agent_state.md)
- [Task tree — stored on Session.task](task.md)
- [Classification + ContextEnhancedQuery](classification.md)
