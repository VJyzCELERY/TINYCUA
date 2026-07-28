# Algorithm 2: Information Digester

> **Methodology section pairing:** The prose below accompanies Algorithm 2
> in the paper. It covers design invariants and constraints that are not
> algorithmic and therefore remain outside the pseudocode block.

---

## Pseudocode (Algorithm 2)

**Input:** $\mathit{session\_id}$: root session identifier, $\mathit{agent\_sessions}$: set of active agent session contexts, $\mathit{worker\_query}$: query destined for worker node

**Output:** $\mathit{context\_cache}$: path to assembled context cache, $\mathit{digested\_info}$: structured digested summary, $\mathit{retrieved\_context}$: relevant context from enhanced retrieval

```
// Step 1: Assemble Session Contexts
root_context ← ExtractSessionContext(session_id)
all_contexts ← [root_context]
ForAll s ∈ agent_sessions do
    agent_ctx ← ExtractSessionContext(s)
    all_contexts.Append(agent_ctx)
EndFor
context_cache ← WriteCacheFile(all_contexts)

// Step 2: Initialize Enhanced Context Retrieval Tool
retrieval_tool ← InitReActAgent(context_cache)

// Step 3: Grep-Based Retrieval from Cache
retrieved_context ← ReActRetrieve(retrieval_tool, worker_query)

// Step 4: Invoke Digest Information Tool
digest_tool ← InitDigestTool(context_cache)
digested_info ← DigestInformation(digest_tool, worker_query)

// Step 5: Guarantee At Least One Digest Operation
If digested_info = ∅ Then
    digested_info ← DigestInformation(digest_tool, worker_query)
EndIf
```

---

## Companion Prose (Not in Pseudocode)

The following design properties are described in the surrounding methodology
text and are **not** captured by the algorithm above:

### Queue Position Invariant
The information digester is always inserted into the execution queue before the worker node when the query analyst classifies a query as worker. It occupies the position immediately preceding the designated worker, ensuring context is fully assembled and digested prior to worker execution.

### Context Propagation Rule
The assembled context cache is a durable artifact that persists for the duration of the worker's execution. It is not merged back into the parent session context; rather, it serves as a read-only reference store queried dynamically by the enhanced retrieval tool.

### Digest Information Tool Constraint
The digest information tool is invoked a minimum of one time. This minimum invocation count is a hard guarantee; the algorithm enforces at least one digest operation regardless of retrieval tool output quality or completeness.

### Enhanced Context Retrieval Architecture
The retrieval tool spawns a simple ReAct-style agent to perform grep-based retrieval against the session context cache. This agent operates autonomously, issuing grep queries and evaluating results until sufficient relevant context is gathered or a termination condition is met.

### Deduplication Policy
The information digester is only spawned when one does not already exist in the active queue. Duplicate digester instances for the same session are prevented by the queue scheduler.

---

## Tool Permissions Summary

| Tool | Allowed | Purpose |
|------|---------|---------|
| ExtractSessionContext | Yes | Read session transcripts and agent histories |
| WriteCacheFile | Yes | Persist assembled context to disk cache |
| InitReActAgent | Yes | Initialize grep-based retrieval agent |
| ReActRetrieve | Yes | Execute ReAct-style context retrieval |
| InitDigestTool | Yes | Initialize digest information tool |
| DigestInformation | Yes | Produce structured digest summary |

---

## Retry Policy Summary

| Condition | Action |
|-----------|--------|
| Digest output is empty | Retry digest information tool invocation once |
| ReAct agent fails to retrieve context | Re-invoke ReActRetrieve with refined query parameters |
| Cache file write fails | Retry cache assembly with error logging |

---

## Separation Rules

What goes into PSEUDOCODE (the algorithm block):
- Boolean checks and guards
- Data collection / function calls
- Loop control flow (while, for)
- Conditional branching (if/else)
- Variable assignments and data construction
- Retry logic

What stays in COMPANION PROSE (methodology text):
- Queue position invariants ("always first in queue")
- Propagation rules ("not merged back to parent", "durable only when merged")
- Tool constraints ("read-only", "no write operations")
- Deduplication policies ("only spawned when none exists")
- Architectural role descriptions
- Design rationale
