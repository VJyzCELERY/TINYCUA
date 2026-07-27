# Query Analyst

> **Category:** Agent Spec

> **File:** `architecture/query-analyst.md`
> **Last Updated:** 2026-05-30
> **Status:** Implemented
> **See also:** [overview.md](overview.md), [session-architecture.md](session-architecture.md), [context-retrieval.md](context-retrieval.md), [information-digestion.md](information-digestion.md), [task-classification.md](task-classification.md), [state-objects.md](state-objects.md), [primary-agent.md](primary-agent.md)

---

## Role

The Query Analyst prepares the request for routing from root reusable context. It first
commits a neutral preliminary summary, then produces:

1. a `Context Enhanced Query` (CEQ), and
2. a `Classification`.

The Query Analyst scans session `Context` directly (no search tool needed). Deep, precise context retrieval is the responsibility of the Information Digester.

---

## Inputs / Outputs

**Input:**

- `user_query`
- `session.chat_history`
- `session.context`

**Output:**

- `summarize_query_context` — required concise summary of the request in root context.
- `Context Enhanced Query` (CEQ) — a runtime-formatted assistant-role handoff:
  ```text
  Context:
  <preliminary summary>

  User Request:
  <verbatim current user query>
  ```
  See [context-retrieval.md](context-retrieval.md) for the deep retrieval flow used by the Information Digester.
- `Classification` — routing verdict via configurable labels. Canonical schema in [state-objects.md](state-objects.md).

---

## Context Scan

The Query Analyst receives root reusable session context plus the current request and
performs a high-level scan. No retrieval tool is used. Existing session compaction
governs prompt size; the CEQ retains only the committed summary, never the
full context it was derived from.

Rules:

- The Query Analyst calls `summarize_query_context` before independent route selection.
- Runtime, not the summary tool, owns CEQ formatting and verbatim-query preservation.
- User query size does not trigger deep retrieval (that is the Information Digester's responsibility).

Deep context retrieval is defined in [context-retrieval.md](context-retrieval.md).

---

## Internal Flow

```mermaid
flowchart TD
    UQ{{"User Query"}}
    FSC{{"Session\nchat_history + Context"}}
    SCAN["High-level context scan"]
    CEQ{{"Context Enhanced Query\n(high-level)"}}
    CLASSIFY["Score request and choose mode"]
    MD{{"Classification"}}

    UQ --> SCAN
    FSC --> SCAN
    SCAN --> CEQ
    CEQ --> CLASSIFY
    CLASSIFY --> MD
```

---

## Classification

The Query Analyst uses a `ClassificationTool` with configurable labels — not a binary small/large verdict.

The configured labels determine the routing outcome. See [task-classification.md](task-classification.md) for the classification rubric and safeguard rules.

---

## Safeguards

The Query Analyst must guard against three failure modes: Worker overuse, unsafe Primary Agent routing, and open-ended uncertainty. See [task-classification.md](task-classification.md) for the full safeguard rubric.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Context scan | Fast, high-level scan | Query Analyst must be fast; deep retrieval is the Information Digester's responsibility |
| Verdict shape | Classification via configurable labels | Supports passthrough and worker routing via the same QueryAnalyst node |
| Classification style | Configurable `ClassificationTool` with safeguard rules | Prevents lazy overuse of Worker mode and unsafe Primary Agent routing |
| Enhancement approach | High-level, session-context direct scan | QA receives session context directly; no search tool needed — it scans what it already has |
