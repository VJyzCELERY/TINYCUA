# Algorithm 2: Query Analyst Node

> **Methodology section pairing:** The prose below accompanies Algorithm 2
> in the paper. It covers design invariants and constraints that are not
> algorithmic and therefore remain outside the pseudocode block.

---

## Pseudocode (Algorithm 2)

**Input:** User query $q$, session context $C$
**Output:** Enhanced query $q_{\text{enhanced}}$, route label $\mathit{route}$

```
// Deduplication guard
if QueryAnalystAlreadyActive(C):
    return ⊥

// Context collection (read-only)
ctx ← CollectContext(q, C)

// Build reasoning window and classify
rw ← {q} ∪ FilterRelevant(ctx, q)
route ← ClassifyRoute(SLMAnalyze(rw))

// Validate route with retry
while route is invalid or not invoked:
    route ← ClassifyRoute(SLMAnalyze(rw))
    if retries exceeded:
        return q, DefaultRoute()

// Dispatch
q_enhanced ← {q} ∪ FilterRelevant(rw, q)
if route = Worker:
    SpawnInformationDigester()
return q_enhanced, route
```

---

## Companion Prose (Not in Pseudocode)

### Queue Position
Query Analyst is always the first node in the queue, receiving full context overhead.

### Segmented Context Model
The reasoning window is volatile — not merged back to the parent. Output becomes durable only when merged into the next node.

### Read-Only Constraint
Only read-only exploratory tools (file read, web search). No write operations permitted.

### Deduplication
Spawned only when no Query Analyst already exists in the active queue.

---

## Tool Permissions Summary

| Tool | Allowed | Purpose |
|------|---------|---------|
| CollectContext | Yes | Gather root, node, and exploratory context |
| FilterRelevant | Yes | Filter context to relevant information |
| SLMAnalyze | Yes | Analyze reasoning window via SLM |
| ClassifyRoute | Yes | Assign route label from analysis |
| SpawnInformationDigester | Conditional | Only when route = Worker |
| WriteFile | **No** | Read-only node — no mutations |

---

## Retry Policy Summary

| Condition | Action |
|-----------|--------|
| Route is invalid | Retry classification |
| Route is not invoked | Retry classification |
| MaxRetries exceeded | Return DefaultRoute (passthrough fallback) |
