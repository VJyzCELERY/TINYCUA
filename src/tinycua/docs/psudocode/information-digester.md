# Algorithm 2: Information Digester Node

> **Methodology section pairing:** The prose below accompanies Algorithm 2
> in the paper. It covers design invariants and constraints that are not
> algorithmic and therefore remain outside the pseudocode block.

---

## Pseudocode (Algorithm 2)

**Input:** Session context $C$, worker query $q$
**Output:** Context cache path $\mathit{cachePath}$, digested summary $\mathit{digest}$

```
// Step 1: Collect session contexts
rootCtx ← ReadRootSession(C)
agentSessions ← ListActiveAgentSessions(C)

// Step 2: Assemble unified context cache
allContexts ← [rootCtx]
ForAll s ∈ agentSessions do
    agentCtx ← ReadAgentSession(s)
    allContexts.Append(agentCtx)
EndFor
cachePath ← WriteCacheFile(allContexts)

// Step 3: Spawn enhanced context retrieval (ReAct agent)
retrievalAgent ← SpawnReActAgent(cachePath)

// Step 4: Grep-based context retrieval
retrievedCtx ← ReActRetrieve(retrievalAgent, q)

// Step 5: Invoke digest information tool
digestTool ← InitDigestTool(cachePath)
digest ← DigestInformation(digestTool, q, retrievedCtx)

// Step 6: Ensure at least one digest operation
if digest = ∅:
    digest ← DigestInformation(digestTool, q, retrievedCtx)
```

---

## Companion Prose (Not in Pseudocode)

The following design properties are described in the surrounding methodology
text and are **not** captured by the algorithm above:

### Queue Position Invariant

The Information Digester is inserted into the queue immediately before the
Worker node when the Query Analyst classifies a query as $\textsc{Worker}$.
It always precedes the worker in execution order.

### Context Propagation Rule

The assembled context cache is durable for the worker's execution. It is not
merged back to the parent session; the digest output becomes the durable handoff.

### Digest Minimum Guarantee

The digest information tool is invoked a minimum of one time, ensuring every
worker-bound query produces a structured summary regardless of retrieval quality.

### Deduplication Policy

A new Information Digester is spawned only when one does not already exist in
the active queue for the current session context.

---

## Tool Permissions Summary

| Tool | Allowed | Purpose |
|------|---------|---------|
| ReadRootSession | Yes | Collect root session context |
| ListActiveAgentSessions | Yes | Enumerate active agent sessions |
| ReadAgentSession | Yes | Read individual agent session transcript |
| WriteCacheFile | Yes | Persist assembled context to disk |
| SpawnReActAgent | Yes | Initialize grep-based retrieval agent |
| ReActRetrieve | Yes | Execute ReAct-style context retrieval |
| InitDigestTool | Yes | Initialize digest information tool |
| DigestInformation | Yes | Produce structured digest summary |

---

## Retry Policy Summary

| Condition | Action |
|-----------|--------|
| Digest output is empty | Retry DigestInformation once |
| ReAct agent retrieval fails | Re-invoke with refined query |
| Cache file write fails | Retry assembly with error logging |
