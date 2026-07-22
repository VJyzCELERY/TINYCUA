# Algorithm 2: Query Analyst Node

> **Methodology section pairing:** The prose below accompanies Algorithm 2
> in the paper. It covers design invariants and constraints that are not
> algorithmic and therefore remain outside the pseudocode block.

---

## Pseudocode (Algorithm 2)

**Input:** User query $q$, session context $C$
**Output:** Enhanced query $q_{\text{enhanced}}$, route label $\mathit{route}$

```
─────────────────────────────────────────────────────
STEP 1: Deduplication Guard
─────────────────────────────────────────────────────

if QueryAnalystAlreadyActive(C):
    return ⊥
```

```
─────────────────────────────────────────────────────
STEP 2: Context Collection (Read-Only)
─────────────────────────────────────────────────────

rootCtx  ← ReadRootSession(C)
nodeCtx  ← InspectExistingNodes(C)
exploratoryCtx ← ExploreInformation(q, C)
```

```
─────────────────────────────────────────────────────
STEP 3: Temporary Reasoning Window
─────────────────────────────────────────────────────

reasoningWindow ← { q,
    FilterRelevant(rootCtx, q),
    FilterRelevant(nodeCtx, q),
    exploratoryCtx }
```

```
─────────────────────────────────────────────────────
STEP 4: SLM Classification
─────────────────────────────────────────────────────

analysis ← SLMAnalyze(reasoningWindow)
route    ← ClassifyRoute(analysis)
```

```
─────────────────────────────────────────────────────
STEP 5: Route Validation and Retry
─────────────────────────────────────────────────────

retryCount ← 0
while route is invalid or route is not invoked:
    retryCount ← retryCount + 1
    if retryCount > NodeRetryPolicy.MaxRetries:
        route ← DefaultRoute()
        break
    analysis ← SLMAnalyze(reasoningWindow)
    route    ← ClassifyRoute(analysis)
```

```
─────────────────────────────────────────────────────
STEP 6: Route Dispatch
─────────────────────────────────────────────────────

q_enhanced ← { q, FilterRelevant(reasoningWindow, q) }

if route = Worker:
    SpawnInformationDigester()
    return q_enhanced, Worker
else if route = Passthrough:
    return q_enhanced, Passthrough
```

---

## Companion Prose (Not in Pseudocode)

The following design properties are described in the surrounding methodology
text and are **not** captured by the algorithm above:

### Queue Position Invariant

The Query Analyst node is always enqueued as the first node in the
`NodeQueue`. It serves as the initial input layer of the TinyCUA loop,
receiving the full context overhead from the root session or existing nodes.

### Segmented Context Model

The temporary reasoning window (Step 3) is a **volatile construct**. It is
not merged back into the parent node's session. The output produced by the
Query Analyst becomes durable only when it is received by and merged into the
next node in the queue (either the Information Digester or the Response Node).

### Read-Only Tool Constraint

The Query Analyst is restricted to **read-only exploratory tools**. It may
inspect the status of existing tasks and explore external information (e.g.,
reading files, web search) to assist routing decisions. It is **not permitted**
to perform any write operation, ensuring its role is solely to classify and
route.

### Deduplication Policy

A Query Analyst is spawned only when no Query Analyst already exists in the
active queue. This ensures a single classification pass per query and prevents
redundant routing decisions.

---

## Tool Permissions Summary

| Tool | Allowed | Purpose |
|------|---------|---------|
| ReadRootSession | Yes | Collect root session context |
| InspectExistingNodes | Yes | Check status of existing tasks |
| ExploreInformation | Yes | Read files, web search for routing context |
| WriteFile | **No** | Read-only node — no mutations |
| ModifyTask | **No** | Read-only node — no mutations |
| SpawnInformationDigester | Conditional | Only when route = Worker |

---

## Retry Policy Summary

| Condition | Action |
|-----------|--------|
| Route is invalid | Retry classification up to MaxRetries |
| Route is not invoked | Retry classification up to MaxRetries |
| MaxRetries exceeded | Use DefaultRoute() (passthrough fallback) |
| Query Analyst already active | Skip — deduplication enforced |
