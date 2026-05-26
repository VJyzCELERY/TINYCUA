# Analysis: Should Digested Information be paired with the Original User Query?

> **File:** `architecture/analysis_digested_info_vs_query.md`

> **Category:** Decision Record

> **Context:** This analysis feeds into the TINYCUA architecture design. The Information Digestion agent receives the **Context Enhanced Query** (from Query Analyst) and the **Full Session Context**, and produces a **Digested Information** output. The question is: should this digest be passed to the TINYCUA Worker **alone**, or **paired with the original user query** (or some derivative)?

---

## The current flow

```
Query Analyst
    ├── Output 1: Verdict (large/small)
    └── Output 2: Context Enhanced Query (CEQ)
                         │
                         ▼
              Information Digestion
                ├── Input 1: CEQ (what to focus on)
                └── Input 2: Full Session Context (raw material)
                         │
                         ▼
                Digested Information
                    │
                    ▼
              TINYCUA Worker → Task Analysis Agent
```

The question: when the Worker's Task Analysis Agent receives `Digested Information`, should it **also** receive the original user query?

---

## Option A: Digested Information alone

```
Query → Analyst → CEQ → Digestion → Digested Info ──→ Task Analysis
                                                   (no query)
```

**Pros:**
- Single source of truth — Task Analysis only has one input to reason about
- No ambiguity: the digest IS the expressed intent (query + context already merged)
- Less token usage — avoids repeating the query in the Worker's context window
- Forces the Digestion agent to be complete: if the query intent is lost, that's a failure in Digestion, not something the Worker needs to recover from

**Cons:**
- The original user intent may get diluted or misinterpreted during digestion
- Task Analysis can't "fact-check" the digest against the original query
- If Digestion over-summarizes, the Worker loses information permanently

---

## Option B: Digested Information + Original User Query

```
Query → Analyst → CEQ → Digestion → Digested Info ──→ Task Analysis
                                         ↑
Original User Query ──────────────────────┘
```

**Pros:**
- Task Analysis can cross-reference: "does the digest match what the user actually asked?"
- The original query acts as a grounding anchor — reduces hallucination drift in the Worker
- If Digestion misses something, the query is still available for the Worker to catch
- Clear separation: digest = "what the context says", query = "what the user wants"

**Cons:**
- Redundancy — the Context Enhanced Query already merged context with the query
- More tokens in the Worker's context window (could be significant for SLMs)
- Potential confusion if digest and query disagree (which does the Worker follow?)
- Task Analysis might ignore the digest and just use the raw query (defeats purpose of Digestion)

---

## Option C: Digested Information + Instructions (derived from query)

```
Query → Analyst → CEQ → Digestion → Digested Info ──→ Task Analysis
                                              ↑
                                  Instruction Generator
                                              ↑
                                  Original User Query
```

The Digestion output includes a separate `instructions` field derived from the query:
```json
{
  "digested_info": "The context contains three research papers...",
  "key_points": ["Paper A proposes X", "Paper B proposes Y"],
  "instructions": "Compare the approaches in Paper A and Paper B, highlighting differences in methodology",
  "original_intent": "summarize and compare findings"
}
```

**Pros:**
- Task Analysis gets explicit guidance on WHAT to do with the context
- The instructions are grounded in the original query but structured for the Worker
- No ambiguity: instructions tell the Worker what to do, digest provides the material

**Cons:**
- Additional processing step (though minimal — just extracting intent from CEQ)
- Risk of over-constraining: instructions might be too specific, limiting the Worker's adaptability
- Still need to decide: does Task Analysis follow instructions strictly or adaptively?

---

## Decision matrix

| Criterion | Option A (Digest Only) | Option B (Digest + Query) | Option C (Digest + Instructions) |
|-----------|----------------------|-------------------------|--------------------------------|
| **Token efficiency** | ✅ Best | ❌ Worst | ✅ Good |
| **Intent preservation** | ⚠️ Depends on Digestion quality | ✅ Best (query is reference) | ✅ Good (instructions derived) |
| **Simplicity** | ✅ Simplest | ⚠️ Two inputs to reconcile | ⚠️ Three components |
| **Recovery from Digestion errors** | ❌ No recovery | ✅ Query can override | ⚠️ Instructions may encode error |
| **Task Analysis clarity** | ❌ Must infer intent from digest | ⚠️ Must reconcile query vs digest | ✅ Instructions are explicit |
| **Risk of hallucination drift** | ⚠️ Medium (digest is only reference) | ✅ Low (query anchors) | ⚠️ Medium (instructions anchor) |
| **Works well with SLMs?** | ⚠️ Maybe (less context) | ❌ More tokens = harder for SLM | ✅ Structured format helps SLMs |

---

## Recommendation: Option C (Digest + Instructions)

The strongest approach is **Option C** for these reasons:

1. **Task Analysis needs to know what to DO** — not just what the context says. The `instructions` field explicitly bridges "here's the context" and "here's what to do with it."

2. **SLM-friendly** — structured format (`digested_info` + `instructions`) is easier for small models to parse than free-form query text. The Task Analysis agent doesn't need to re-derive intent from raw language.

3. **Preserves the original query intent** — the `instructions` are derived from the original query during digestion, so the user's intent is encoded explicitly, not buried in free text.

4. **Keeps token count manageable** — the original query could be long or contain irrelevant parts. Instructions are a compressed, action-oriented derivative.

### Implementation sketch

The Information Digestion agent's output would become:

```json
{
  "digested_info": "Compressed context relevant to the task...",
  "key_points": ["Key point 1", "Key point 2"],
  "instructions": {
    "action": "compare_and_analyze",
    "parameters": {
      "targets": ["Paper A", "Paper B"],
      "aspect": "methodology_differences"
    },
    "constraints": ["focus on methodology", "include citations"]
  },
  "original_intent_summary": "Compare two research papers",
  "relevant_context_size": "medium",
  "remaining_context_summary": "Additional papers not in focus..."
}
```

The `instructions` field tells the Task Analysis agent:
- **What action to take** (summarize, compare, search, analyze, implement)
- **Parameters** (specific targets, aspects to focus on)
- **Constraints** (boundaries, exclusions, format requirements)

This way, the Worker can proceed deterministically — it knows both the material and the mandate.

---

## Resolved decisions

### 1. Instructions are ADVISORY, not strict

**Decision:** Instructions are advisory. The Task Analysis agent can adapt or override them if it determines a better approach.

**Why:**
- SLMs hallucinate less when they have autonomy to adjust — strict instructions cause the model to *force-fit* the task into a wrong structure
- The Digestion agent may not always perfectly interpret intent; Task Analysis has more context about what's actually feasible
- Advisory instructions act as a **guide rail**, not a cage — Task Analysis can deviate when needed but has a strong default direction

**How it works in practice:**
```json
{
  "instructions": {
    "action": "compare_and_analyze",
    "parameters": {
      "targets": ["Paper A", "Paper B"],
      "aspect": "methodology_differences"
    },
    "constraints": ["focus on methodology", "include citations"],
    "advisory": true  ← explicit flag: Task Analysis can adapt
  }
}
```

---

### 2. Original user query is NOT included as fallback

**Decision:** The original query is **not** passed to the Worker. Not as a fallback, not alongside the digest.

**Why:**
- The risk is real: if the original query is available, the Task Analysis agent will **lazily default to it** instead of using the digest — defeating the entire purpose of Information Digestion
- SLMs take the path of least resistance. A raw query is simpler to parse than a structured digest, so they'll skip the digest
- The Context Enhanced Query (CEQ) already contains the query's intent merged with retrieved context. The CEQ is what went into Digestion. The query is not lost — it's embedded in the entire pipeline upstream
- If the Worker gets stuck, the **Reviewer** (not the Task Analysis agent) can signal back to the outer loop to re-classify or re-digest — the fix is at the system level, not by giving the Worker a raw query crutch

**What happens if the Worker gets stuck:**
1. Task Execution fails or produces low-confidence result
2. Task Reviewer detects failure
3. Reviewer signals back to outer loop: "digest insufficient"
4. Outer loop can either:
   - Re-run Information Digestion with different focus
   - Default to Passthrough mode (if the task wasn't actually complex)
   - Request user clarification

This keeps the recovery at the **orchestration level**, not the agent level — preventing the lazy-query problem.

---

### 3. Information Digestion generates the instructions

**Decision:** The Information Digestion agent generates the `instructions` as part of its output. Not the Query Analyst.

**Why:**
- The Query Analyst's job is **context retrieval** — it finds relevant history and produces the Context Enhanced Query. Adding instruction generation would bloat its responsibility and risk hallucination
- Information Digestion already processes the CEQ + Full Session Context together — it's in the best position to derive instructions because it sees both the intent (CEQ) and the material (full context)
- The instructions are inherently about **what to do with the context**, which is exactly Digestion's domain

**Revised flow:**
```
Query Analyst
    ├── Verdict (large/small)
    └── Context Enhanced Query
                │
                ▼
Information Digestion
    ├── Input 1: Context Enhanced Query (intent + retrieved context)
    ├── Input 2: Full Session Context (raw material)
    └── Generates:
        ├── digested_info + key_points
        ├── instructions (advisory, derived from CEQ + context)
        └── metadata (size, remaining_context)
                │
                ▼
TINYCUA Worker ← receives digest + instructions (no raw query)
```

---

## Final recommendation summary

| Question | Decision | Rationale |
|----------|----------|-----------|
| Instructions strict or advisory? | **Advisory** | SLMs need flexibility; strict instructions cause force-fitting |
| Include original query as fallback? | **No** | SLMs take the lazy path and skip the digest; recovery belongs at orchestration level |
| Who generates instructions? | **Information Digestion** | It sees both intent (CEQ) and material (full context) — best positioned |

### The final output structure of Information Digestion

```json
{
  "digested_info": "Compressed context relevant to the task...",
  "key_points": ["Key point 1", "Key point 2"],
  "instructions": {
    "action": "compare_and_analyze",
    "parameters": {
      "targets": ["Paper A", "Paper B"],
      "aspect": "methodology_differences"
    },
    "constraints": ["focus on methodology", "include citations"],
    "advisory": true
  },
  "original_intent_summary": "Compare two research papers",
  "relevant_context_size": "medium",
  "remaining_context_summary": "Additional papers not in focus..."
}
```

This is the single input to the TINYCUA Worker. No raw query. No fallback. The Worker trusts the digest and follows the instructions adaptively. If it gets stuck, the Reviewer escalates to the outer loop.
