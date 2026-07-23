# Algorithm 1: Query Analyst

> **Methodology section pairing:** The prose below accompanies Algorithm 1
> in the paper. It covers design invariants and constraints that are not
> algorithmic and therefore remain outside the pseudocode block.

---

## Pseudocode (Algorithm 1)

**Input:** $\mathit{root\_session}$, $\mathit{user\_query}$, $\mathit{queue}$
**Output:** $\mathit{route} \in \{\textsc{Worker}, \textsc{Passthrough}, \textsc{Uncertain}\}$

```
// Step 1: Deduplication guard
if queue contains active QueryAnalyst then
    Return mandatory_passthrough(QueryAnalyst)

// Step 2: Deterministic precheck
if valid mandatory_passthrough exists then
    Forward continuation to target node/session; Return

// Step 3: Assemble transient reasoning window
window ← root_session.context ‖ queue.contexts ‖ user_query

// Step 4: Two-step classification (LLM + tool)
route ← ⊥; valid ← False
while ¬valid do
    analysis ← SLMAnalyze(window)
    route ← Classify(analysis); valid ← route ∈ {Worker, Passthrough, Uncertain}

// Step 5: Dispatch via route map
Dispatch(route)
if route = Worker then
    Spawn InformationDigester before WorkerNode
```

---

## Companion Prose (Not in Pseudocode)

The following design properties are described in the surrounding methodology
text and are **not** captured by the algorithm above:

### Queue Position Invariant
Query Analyst is always the first node in the queue and serves as the entry point for every `TinyCUALoop.run(...)` invocation.

### Transient Context Window
The assembled reasoning window is ephemeral; it is not backward-propagated wholesale to the parent node. Output becomes durable only when received and propagated upward by the next node per the segmented context model.

### Read-Only Tool Constraint
Query Analyst is restricted to read-only exploratory tools (task inspection, file reads, web search) for routing decisions and must not perform any write operation.

### Deduplication Policy
Query Analyst is spawned only when no active Query Analyst already exists in the queue; a duplicate entry triggers a mandatory passthrough to the active instance instead.

### Route Behavior
- **Worker**: Spawns InformationDigester to gather context, then routes to WorkerNode for task planning/execution.
- **Uncertain**: Query Analyst remains active and waits for user continuation.
- **Passthrough**: Forwards user input to an already active or queued node/session.

### Two-Step Decision Process
The classification follows a two-step process: (1) an LLM analysis call that reasons over the assembled window, and (2) a verdict/classification tool call that must produce a valid indexed label. Invalid or missing labels retry per the node retry policy.

---

## Tool Permissions Summary

| Tool | Allowed | Purpose |
|------|---------|---------|
| Read-only task inspection | Yes | Inspect existing task state for routing decisions |
| File reads | Yes | Explore information to assist classification |
| Web search | Yes | Gather external context for routing |
| Write operations | No | Query Analyst is strictly a classification and routing node |

---

## Retry Policy Summary

| Condition | Action |
|-----------|--------|
| Invalid or missing route label from classification tool | Retry with assistant-role continuation per `NodeRetryPolicy` |
| Valid mandatory passthrough on re-entry | Skip LLM classification; forward deterministically |

---

## Output Naming

Files saved as:
- `psudocode/query-analyst.tex`
- `psudocode/query-analyst.md`
