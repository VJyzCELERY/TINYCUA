# Information Digestion

> **Category:** Agent Spec

> **File:** `architecture/information-digestion.md`
> **See also:** [overview.md](overview.md), [query-analyst.md](query-analyst.md), [context-retrieval.md](context-retrieval.md), [task-analysis.md](task-analysis.md)

---

## Role

Information Digestion turns broad session information into precision-oriented `Digested Information`.

It should preserve task-critical details and remove distracting context. The purpose is not merely token reduction; the purpose is reducing irrelevant context exposure.

---

## Inputs / Outputs

**Input:**

- `context_enhanced_query`
- `full_session_context` when needed

**Output:**

```yaml
digested_information:
  digested_info: "compressed relevant context"
  key_points:
    - "..."
  context_candidates:
    - "candidate context for downstream task contexts"
  entity_map:
    entity_name: "relevant details"
  relevance_notes:
    - "why selected context matters"
  known_gaps:
    - "information that may be missing"
  instructions:
    action: "..."
    constraints:
      - "..."
    advisory: true
  original_intent_summary: "..."
```

---

## Internal Flow

```mermaid
flowchart TD
    CEQ{{"Context Enhanced Query"}}
    FSC{{"Full Session Context"}}
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

In Worker Mode, Task Analysis uses Digested Information to create a sequential roadmap. Each task receives its own `context` field.

In Digestion-Only Mode, the Primary Agent receives Digested Information directly and synthesizes the response without Worker decomposition.

---

## Advisory Instructions

Instructions are advisory. They guide downstream agents but do not rigidly constrain them.

Task Analysis can adapt the plan if the digest suggests a better task roadmap. The Primary Agent can adapt presentation while staying within the provided information.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Main objective | Precision-oriented digestion | Reduce irrelevant context exposure, not only token count |
| Instructions | Advisory | Allows downstream agents to adapt without drifting from context |
| Output support | Context candidates and known gaps | Helps Task Analysis create task-specific context |
| Original query included? | No raw-query crutch by default | Downstream agents should work from CEQ/digest, not default to broad history |
