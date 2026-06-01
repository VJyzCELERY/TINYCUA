# QueryAnalystLoop

> **File:** `docs/design/loops/query_analyst_loop.md`
> **Last Updated:** 2026-06-01

---

## Role

`QueryAnalystLoop` enforces the configurable ClassificationTool, preserves first
response text as context, and writes `QueryAnalystState` to `session.agent_state`.

---

## Flow

```text
stream initial response
capture first response text as context
if ClassificationTool called:
  decision = selected label
else:
  retry only for missing classification
if still missing:
  decision = config.classification_labels[0]  # TinyCUA root: passthrough

session.agent_state = QueryAnalystState(
  type="query_analyst",
  status="terminated",
  classification=decision,
  context=first_response_text,
  query=original_user_query,
)
```

`uncertain` is not a classification label. HITL/open-question behavior is represented by a node not
terminating, not by a special classification.

---

## Related

- [QueryAnalyst AgentNode](../agent_sessions/query_analyst.md)
- [QueryAnalystState](../state/information.md#queryanalyststate)
