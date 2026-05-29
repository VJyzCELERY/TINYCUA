# Information Digester

> **Category:** Agent Spec

> **File:** `architecture/information-digestion.md`
> **Last Updated:** 2026-05-29
> **Status:** Draft
> **See also:** [overview.md](overview.md), [query-analyst.md](query-analyst.md), [session-architecture.md](session-architecture.md), [context-retrieval.md](context-retrieval.md), [primary-agent.md](primary-agent.md), [worker-orchestration.md](worker-orchestration.md), [task-analysis.md](task-analysis.md), [state-objects.md](state-objects.md)

---

## Role

The Information Digester is an exploration agent. It receives what it treats as the user query (the `Context Enhanced Query` from the Query Analyst) and explores the current Session `Context` to find relevant lower-level, finer-detail context. It then compiles that context into precision-oriented `Digested Information`.

It should preserve task-critical details and remove distracting context. The purpose is not merely token reduction; the purpose is reducing irrelevant context exposure.

The Information Digester is a privileged narrowing boundary: it may explore broad session `Context` and perform deep retrieval, but downstream agents should receive only the consolidated output they need.

Key framing:

- The Information Digester does **not** receive the full Session `Context` as its direct context. It accesses the Session `Context` through **Enhanced Context Retrieval** — a search tool that explores the Session `Context` as an external information source.
- The Information Digester does not distinguish between a raw user query and a `Context Enhanced Query`. It treats whatever it receives as the query and explores for missing context.
- The Information Digester is an **exploration agent** — its core loop is: identify information gaps in the query → use Enhanced Context Retrieval to search the Session `Context` → compile relevant findings into `Digested Information`.

---

## Inputs / Outputs

**Input:**

- `context_enhanced_query` (high-level) — the query to process. The Information Digester treats this as the user query; it does not distinguish it from a raw query.

The Information Digester does **not** receive the full Session `Context` as direct input. It accesses the Session `Context` through its Enhanced Context Retrieval tool (below).

- caller: `primary_agent` or `worker`

**Tools:**

- **Enhanced Context Retrieval** — searches the current Session `Context` (structured markdown) as an external data store. Uses keyword pagination, vector retrieval, LLM-based exploration, or any combination. See [context-retrieval.md](context-retrieval.md).

**Output:**

The digest is sent to downstream agents as structured text; storage format is an implementation detail. Canonical output schema and section descriptions are in [state-objects.md](state-objects.md).

---

## Internal Flow

```mermaid
flowchart TD
    CEQ{{"Context Enhanced Query\n(treated as user query)"}}
    GAPS["Identify information gaps\nin the query"]
    RETRIEVE["Enhanced Context Retrieval\n(explore Session Context\nvia keyword / vector / LLM)"]
    SESSION_CTX[("Session Context\n(structured markdown)\n— current state")]
    RET_CTX{{"Retrieved Context\n(low-level, fine detail)"}}
    FOCUS["Identify relevant topics/entities"]
    EXTRACT["Extract relevant context"]
    FILTER["Remove distracting context"]
    PRESERVE["Preserve task-critical details"]
    STRUCTURE["Structure digest and advisory instructions"]
    DI{{"Digested Information"}}

    CEQ --> GAPS
    GAPS --> RETRIEVE
    SESSION_CTX -. "searched by" .-> RETRIEVE
    RETRIEVE --> RET_CTX
    RET_CTX --> FOCUS
    FOCUS --> EXTRACT
    EXTRACT --> FILTER
    FILTER --> PRESERVE
    PRESERVE --> STRUCTURE
    STRUCTURE --> DI
```

---

## Downstream Use

In Worker Mode, the Task Analyzer uses Digested Information to create a sequential roadmap. Each task receives its own `context` field.

In Primary Agent Mode, the Primary Agent may invoke Information Digestion if it needs broader context consolidation before response composition.

---

## Advisory Instructions

Instructions are advisory. They guide downstream agents but do not rigidly constrain them.

The Task Analyzer can adapt the plan if the digest suggests a better task roadmap. The Primary Agent can adapt presentation while staying within the provided information.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deep retrieval location | Information Digester | Query Analyst stays fast with high-level scan; deep, precise exploration of Session `Context` belongs in the exploration stage |
| Context access | Via Enhanced Context Retrieval tool | The Information Digester does not load the full Session `Context` directly — it searches it as an external source, keeping its own context window small |
| Retrieval approach | Precision-first, LLM-judged | Generate search queries from identified gaps, search Session `Context`, use LLM to judge relevance semantically |
| Main objective | Precision-oriented digestion | Reduce irrelevant context exposure, not only token count |
| Boundary | Privileged narrowing boundary | Digestion can explore broad context without leaking broad context downstream |
| Instructions | Advisory | Allows downstream agents to adapt without drifting from context |
| Known gaps | Explicitly signaled | Prevents downstream agents from hallucinating to fill missing information |
