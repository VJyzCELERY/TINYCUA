# Classification + ContextEnhancedQuery

> **File:** `docs/design/state/mode_decision.md`
> **Package:** `tinycua.state.classification`
> **Last Updated:** 2026-06-01
> **Status:** Legacy file path; concept renamed from ModeDecision to Classification

---

## Role

`ContextEnhancedQuery` and a generic classification result are produced by
QueryAnalyst. The old `ModeDecision` concept is replaced by configurable
ClassificationTool output.

The file path remains `mode_decision.md` for now to avoid breaking links, but the
source-of-truth concept is **classification**, not ModeDecision.

---

## ContextEnhancedQuery Contract

```text
ContextEnhancedQuery extends StateObject
    · context: str — agent output: markdown with relevant context, keywords, etc.
    · query: str — original user query (passed through unchanged)
```

`ContextEnhancedQuery` is a structured value object embedded in `QueryAnalystState`.
It is not itself an AgentState subclass.

---

## Classification Output

Classification is produced by `ClassificationTool(labels=config.classification_labels)`.

```text
QueryAnalystState <: AgentState
  · classification: str                # selected label from configured labels
  · context: str | None
  · query: str                         # original user query; required
```

Root TinyCUA labels:

```text
["passthrough", "worker"]
```

Worker input-gate labels:

```text
["task_recreation", "task_reanalysis", "proceed_execution"]
```

`uncertain` is not a label. If the agent cannot decide, it does not produce a terminal
classification; the loop may retry, fallback to the first configured label, or stay
active depending on HITL configuration.

---

## ContextEnhancedQuery Methods

### `to_messages() → list[dict]`

```text
ContextEnhancedQuery.to_messages() → list[dict[str, str]]
  · Returns:
      [
          {"role": "user", "content": self.context},
          {"role": "user", "content": self.query}
      ]
```

**Important usage rules:**

1. Do not append these messages to chat history by default.
2. If the context is persisted, append it as `role="assistant"` because it is
   agent-produced context.
3. Do not re-add the `query` message to session context if the external user query is
   already present.
4. Use `ceq.query` as the `agent.run(query=...)` argument.

---

## Validation

- `classification` must be one of the labels configured for that QueryAnalyst instance.
- `ContextEnhancedQuery.query` / `QueryAnalystState.query` must contain the original
  user query; `None` or `""` is invalid.
- `context` may be empty.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ModeDecision removed | Use generic classification | QueryAnalyst can act as different input gates |
| Labels configurable | `QueryAnalystConfig.classification_labels` | Same node supports root and worker decisions |
| No uncertain label | Indecision = retry/open-question/fallback | Avoids special route |
| CEQ transient by default | `to_messages()` is for message extension | Prevents context pollution |
| Context as assistant when persisted | Role change required | Context is agent-produced |

---

## See also

Prev : [`Task` Tree + `TaskResult`](task.md) | Next : [`DigestedInformation`](digested_information.md)

## Related

- [QueryAnalyst AgentNode](../agent_node/query_analyst.md)
- [QueryAnalystState](information.md#queryanalyststate)
- [Classification constants](../constants/tools.md)
