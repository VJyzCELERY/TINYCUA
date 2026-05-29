# Decision Record: Should Digested Information be paired with the Original User Query?

> **Category:** Decision Record

> **File:** `architecture/analysis-digested-info-vs-query.md`
> **Last Updated:** 2026-05-27
> **Status:** Implemented
> **See also:** [information-digestion.md](information-digestion.md), [query-analyst.md](query-analyst.md), [task-analysis.md](task-analysis.md), [state-objects.md](state-objects.md)

This decision record has been updated to match the current routing model.

---

## Current Routing Context

The Query Analyst performs a fast, high-level scan and produces:

1. `Context Enhanced Query` (CEQ) — high-level enrichment
2. `Mode Decision`

The Information Digester receives the CEQ and uses Enhanced Context Retrieval (a search tool that explores the current Session `Context` as an external source) to produce `Digested Information`.

The current top-level routing model is:

```text
Query Analyst (high-level scan)
    ├── Context Enhanced Query (high-level)
    └── Mode Decision
            ├── primary_agent → Primary Agent
            │       └── may invoke Information Digestion if CEQ needs precise consolidation
            ├── worker → Information Digester (deep retrieval + digestion) → TINYCUA Worker → Primary Agent
            └── uncertain → uncertain_next_action: ask_user | explore
```

The Information Digester is therefore used in two situations:

- before Worker Mode, where the Worker needs narrowed context before task decomposition;
- when the Primary Agent decides the CEQ needs context consolidation before it can answer safely.

---

## Question

When the Worker's Task Analyzer receives `Digested Information`, should it also receive the original user query?

---

## Options Considered

### Option A: Digested Information Alone

```text
CEQ → Information Digester → Digested Information → Task Analyzer
```

Pros:

- Single source of truth for Task Analysis.
- Lower context exposure.
- Forces the Information Digester to preserve intent and context correctly.

Cons:

- If Digestion loses intent, Worker cannot directly compare against the raw user query.
- Recovery must happen through orchestration rather than local fallback.

### Option B: Digested Information + Original User Query

```text
CEQ → Information Digester → Digested Information + Original User Query → Task Analyzer
```

Pros:

- The Task Analyzer can compare digest against the raw query.
- The original query can act as an intent anchor.

Cons:

- Increases context exposure.
- Encourages smaller models to take the easier path and reason from the raw query instead of the digest.
- Can defeat the purpose of context decomposition.
- Creates ambiguity if digest and raw query appear to disagree.

### Option C: Digested Information + Advisory Instructions

```text
CEQ → Information Digester → Digested Information + Advisory Instructions → Task Analyzer
```

Pros:

- Preserves intent in a structured, action-oriented form.
- Avoids handing raw query text to the Worker.
- Keeps the Task Analyzer focused on the consolidated context.
- Gives the Worker guidance without making instructions rigid.

Cons:

- Requires the Information Digester to produce a good instruction summary.
- If instructions are over-specific, the Task Analyzer may need to adapt.

---

## Decision

Use **Option C: Digested Information + Advisory Instructions**.

The Worker should not receive the original raw user query as a fallback. The Task Analyzer should receive the digest (context summary, key points, known gaps, and advisory instructions) produced by the Information Digester.

---

## Rationale

TINYCUA's architecture is based on reducing hallucination by reducing irrelevant context exposure. Passing the raw query to the Worker creates a shortcut that can cause the Task Analyzer to ignore the digest and reason from a broader, less curated input.

The CEQ already carries user intent into the Information Digester. The Information Digester is responsible for consolidating that intent with broad session `Context` and producing a narrowed output for downstream agents.

If the digest is insufficient, recovery should happen through orchestration, not by silently expanding Worker context. This keeps recovery explicit.

---

## Current Digestion Output Shape

The canonical Digested Information schema is defined in [state-objects.md](state-objects.md).

---

## Final Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Should instructions be strict? | No, advisory only | The Task Analyzer needs flexibility to adapt. |
| Should Worker receive the original raw query? | No | Raw query can defeat context decomposition. |
| Who generates instructions? | The Information Digester | It sees both CEQ intent and broad session `Context`. |
| How does Worker recover if digest is insufficient? | Reviewer/orchestration path | Recovery should be explicit and controlled. |
