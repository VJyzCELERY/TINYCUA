# Information Digester

> **Category:** Agent Spec

> **File:** `architecture/information-digestion.md`
> **Last Updated:** 2026-05-27
> **Status:** Draft
> **See also:** [overview.md](overview.md), [query-analyst.md](query-analyst.md), [session-architecture.md](session-architecture.md), [context-retrieval.md](context-retrieval.md), [primary-agent.md](primary-agent.md), [task-analysis.md](task-analysis.md), [state-objects.md](state-objects.md)

---

## Role

The Information Digester turns broad session `Context` into precision-oriented `Digested Information`.

It should preserve task-critical details and remove distracting context. The purpose is not merely token reduction; the purpose is reducing irrelevant context exposure.

The Information Digester is a privileged narrowing boundary: it may inspect broad session `Context`, but downstream agents should receive only the consolidated output they need.

---

## Inputs / Outputs

**Input:**

- `context_enhanced_query`
- session `Context` when needed
- retrievable session `chat_history` when needed
- caller: `primary_agent` or `worker`

**Output:**

Canonical schema is in [state-objects.md](state-objects.md). The digest is sent to downstream agents as structured text; storage format is an implementation detail. See [state-objects.md](state-objects.md) for the canonical output schema and section descriptions.

---

## Internal Flow

```mermaid
flowchart TD
    CEQ{{"Context Enhanced Query"}}
    FSC{{"Session Context\n(+ retrievable chat_history when needed)"}}
    FOCUS["Identify relevant topics/entities"]
    EXTRACT["Extract relevant context"]
    FILTER["Remove distracting context"]
    PRESERVE["Preserve task-critical details"]
    STRUCTURE["Structure digest and advisory instructions"]
    DI{{"Digested Information"}}

    CEQ --> FOCUS
    FSC -. "when needed" .-> FOCUS
    FOCUS --> EXTRACT
    EXTRACT --> FILTER
    FILTER --> PRESERVE
    PRESERVE --> STRUCTURE
    STRUCTURE --> DI
```

---

## Downstream Use

In Worker Mode, the Task Analyzer uses Digested Information to create a sequential roadmap. Each task receives its own `context` field.

In Primary Agent Mode, the Primary Agent may invoke Information Digestion if the Context Enhanced Query needs broader context consolidation before response composition.

---

## Advisory Instructions

Instructions are advisory. They guide downstream agents but do not rigidly constrain them.

The Task Analyzer can adapt the plan if the digest suggests a better task roadmap. The Primary Agent can adapt presentation while staying within the provided information.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Main objective | Precision-oriented digestion | Reduce irrelevant context exposure, not only token count |
| Boundary | Privileged narrowing boundary | Digestion can inspect broad context without leaking broad context downstream |
| Instructions | Advisory | Allows downstream agents to adapt without drifting from context |
| Output format | Text representation sent to agents | LLMs consume text naturally; storage format is an implementation detail |
| Original query included? | No raw-query crutch by default | Downstream agents should work from digest, not default to broad history |
| Known gaps | Explicitly signaled | Prevents downstream agents from hallucinating to fill missing information |
