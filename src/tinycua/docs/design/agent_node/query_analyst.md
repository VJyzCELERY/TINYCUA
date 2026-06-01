# Query Analyst

> **File:** `docs/design/agent_node/query_analyst.md`
> **Package:** `tinycua.agent_nodes.query_analyst`
> **Last Updated:** 2026-06-01
> **Status:** Draft

---

## Role

`QueryAnalyst` is an AgentNode used as an **InputGate** target. It is usually
transient (`is_transient=True`) and does not become a durable child session. Its job is
strictly internal:

1. Assemble relevant session context.
2. Analyze the user query and current context.
3. Classify the query using a configurable `ClassificationTool`.
4. Produce `QueryAnalystState` as YAML-front-matter-serializable output.

QueryAnalyst is **not** the user-facing response agent. The user may see its streamed
text, but that text is context/prompt material for downstream agents, not the final
answer.

---

## Configurable Classification

QueryAnalyst has no hardcoded classification labels. It reads labels from
`QueryAnalystConfig.classification_labels`.

```text
QueryAnalystConfig
  · classification_labels: list[str]
  · hitl_enabled: bool = False
```

Common label sets:

```text
TINYCUA_INPUT_GATE_CLASSIFICATION = ["passthrough", "worker"]

TINYCUA_WORKER_INPUT_GATE_CLASSIFICATION = [
    "task_recreation",
    "task_reanalysis",
    "proceed_execution",
]
```

`uncertain` is not a label. If the analyst cannot decide, it should either keep
exploring (HITL disabled) or enter idle/open-question state (HITL enabled). If the
loop exhausts required-classification retries, it falls back to the first configured
label; for TinyCUA root this is `passthrough`.

---

## Session

`QueryAnalyst` creates a transient session.

```text
__init__(config: QueryAnalystConfig | None, parent: Session | None) -> None
  → super().__init__(config=config, session=None)
  → mark session.is_transient = True
  → set parent reference if provided
  → _assemble_session_context()
```

The session is not registered in the parent's `child_sessions`. On termination,
chat_history, token usage, and failure propagate, but `session_context` does not.

---

## `run()` Method

```text
run(query: str) -> AsyncIterator[dict]
```

`query` is the original user query or graph input string. QueryAnalyst does not parse
structured front-matter for normal root-gate operation; it analyzes the text as input.

### Flow

```text
run(query)
  1. Use preassembled self.session.session_context
  2. Build instruction: base + classification labels + task display if available
  3. Build SDK Agent with ClassificationTool(labels=config.classification_labels)
     and read-only task tools if task exists
  4. agent.run(query=query, messages=self.session.session_context, stream=True)
  5. Preserve first response text as context analysis
  6. QueryAnalystLoop enforces ClassificationTool call
  7. Write QueryAnalystState to session.agent_state
```

---

## Context Assembly

`_assemble_session_context()` loads parent context and active descendant context.

```text
_assemble_session_context()
  parent = self.session.parent
  if no parent: return
  parent_context = parent.get_messages()
  active_context = parent.get_active_session().get_messages() if different
  combined = parent_context + active_context
  self.session.session_context = _compact_until_fits(combined)
```

QueryAnalyst compaction threshold should be greater than or equal to the parent's
threshold so it can hold at least as much context as the parent.

---

## Tools

```text
_get_tools()
  tools = [ClassificationTool(name="classify", labels=config.classification_labels)]
  if parent.task exists:
      tools += READ_ONLY_TASK_TOOLS
  tools += config.extra_tools
```

QueryAnalyst has no write tools. It may inspect tasks but must not mutate them.

---

## Output: QueryAnalystState

QueryAnalystLoop writes a `QueryAnalystState` instance to `session.agent_state`.

```text
QueryAnalystState(
  type="query_analyst",
  status="terminated",
  failure=0,
  classification="passthrough" | "worker" | <configured label>,
  context=<first response markdown>,
  query=<original user query>,
)
```

### Mandatory output rules

1. There must be a classification decision.
   - If missing, the loop retries.
   - If still missing, fallback = first configured label (TinyCUA root: `passthrough`).
2. `query` must contain the original user query.
   - `query=None` or `query=""` is invalid.
3. `context` may be empty.
   - `context=None` / `""` is valid if no useful context exists.
4. Context comes from the **first response output** only.
   - Retry responses used to force tool calls do not replace context.

### YAML pass-through

```text
qa_state = self.session.agent_state
downstream_query = qa_state.to_yaml() + "\n" + qa_state.query
```

Downstream nodes reconstruct with `AgentState.from_string(downstream_query)`.

---

## ContextEnhancedQuery Interop

`QueryAnalystState` contains the same semantic values as a `ContextEnhancedQuery`:

```text
ContextEnhancedQuery(context=qa_state.context or "", query=qa_state.query)
```

`ContextEnhancedQuery.to_messages()` is allowed for transient message extension, but
must not be appended to chat history/session context unchanged. If context is persisted,
append it as an assistant message and avoid re-adding the user query. See
[mode_decision.md](../state/mode_decision.md#contextenhancedquery-methods).

---

## Instruction Requirements

The QueryAnalyst instruction must strongly state:

- You are not responding directly to the user.
- You are analyzing context and creating prompt/context material for downstream agents.
- You must decide one of the configured labels using the classification tool.
- For TinyCUA root, classify small tasks/chat/steering as `passthrough` and large task
  creation/execution requests as `worker`.
- For TinyCUA root, only use graph-level active-node context. If `TinyCUAWorker` is
  active, QueryAnalyst should treat the worker as the active node and must not assume
  visibility into the worker's internal TaskExecutor/ResultReviewer queue.
- For worker input gate, classify whether to recreate tasks, reanalyze tasks, or proceed
  directly to execution.
- The first response should be useful context for the next agent.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| InputGate target | QueryAnalyst is called first | Normalizes input before routing |
| Configurable labels | `QueryAnalystConfig.classification_labels` | Same node can act as TinyCUA or Worker gate |
| No uncertain label | Indecision = no terminal decision / fallback passthrough | Simpler routing; HITL through active node |
| Transient session | `is_transient=True` | Output consumed inline; not a durable graph queue/session-tree child |
| First response as context | Retry text cannot replace context | Prevents retry nudges from polluting downstream context |
| Mandatory query | Original user query must always be present | Downstream nodes need the real query |
| Read-only task tools only | Can inspect but not mutate tasks | Input gate must not change task state |
| AgentState output | Writes `QueryAnalystState` to `session.agent_state` | Self-serializing YAML front-matter pass-through |

---

## See also

Prev : [AgentNode Factory](factory.md) | Next : [`InformationDigester`](information_digester.md)

## Related

- [Classification constants](../constants/tools.md)
- [QueryAnalystState](../state/information.md#queryanalyststate)
- [ContextEnhancedQuery](../state/mode_decision.md)
- [TinyCUA input gate](../orchestration/tinycua.md)
- [TinyCUAWorker input gate](../orchestration/worker.md)
