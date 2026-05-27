# Decision Record: Should Digested Information be paired with the Original User Query?

> **File:** `architecture/analysis_digested_info_vs_query.md`

> **Category:** Decision Record

> **Last Updated:** 2026-05-27

This decision record has been updated to match the current routing model.

---

## Current Routing Context

The Query Analyst produces:

1. `Context Enhanced Query` (CEQ)
2. `Mode Decision`

The current top-level routing model is:

```text
Query Analyst
    ├── Context Enhanced Query
    └── Mode Decision
            ├── primary_agent → Primary Agent
            │       └── may invoke Information Digestion if CEQ needs consolidation
            ├── worker → Information Digestion → TINYCUA Worker → Primary Agent
            └── uncertain → uncertain_next_action: ask_user | explore_more
```

Information Digestion is therefore used in two situations:

- before Worker Mode, where the Worker needs narrowed context before task decomposition;
- when the Primary Agent decides the CEQ needs context consolidation before it can answer safely.

---

## Question

When the Worker's Task Analysis Agent receives `Digested Information`, should it also receive the original user query?

---

## Options Considered

### Option A: Digested Information Alone

```text
CEQ → Information Digestion → Digested Information → Task Analysis
```

Pros:

- Single source of truth for Task Analysis.
- Lower context exposure.
- Forces Information Digestion to preserve intent and context correctly.

Cons:

- If Digestion loses intent, Worker cannot directly compare against the raw user query.
- Recovery must happen through orchestration rather than local fallback.

### Option B: Digested Information + Original User Query

```text
CEQ → Information Digestion → Digested Information + Original User Query → Task Analysis
```

Pros:

- Task Analysis can compare digest against the raw query.
- The original query can act as an intent anchor.

Cons:

- Increases context exposure.
- Encourages smaller models to take the easier path and reason from the raw query instead of the digest.
- Can defeat the purpose of context decomposition.
- Creates ambiguity if digest and raw query appear to disagree.

### Option C: Digested Information + Advisory Instructions

```text
CEQ → Information Digestion → Digested Information + Advisory Instructions → Task Analysis
```

Pros:

- Preserves intent in a structured, action-oriented form.
- Avoids handing raw query text to the Worker.
- Keeps Task Analysis focused on the consolidated context.
- Gives the Worker guidance without making instructions rigid.

Cons:

- Requires Information Digestion to produce a good instruction summary.
- If instructions are over-specific, Task Analysis may need to adapt.

---

## Decision

Use **Option C: Digested Information + Advisory Instructions**.

The Worker should not receive the original raw user query as a fallback. Task Analysis should receive the digest, key points, known gaps, context candidates, and advisory instructions produced by Information Digestion.

---

## Rationale

TINYCUA's architecture is based on reducing hallucination by reducing irrelevant context exposure. Passing the raw query to the Worker creates a shortcut that can cause Task Analysis to ignore the digest and reason from a broader, less curated input.

The CEQ already carries user intent into Information Digestion. Information Digestion is responsible for consolidating that intent with broad session `Context` and producing a narrowed output for downstream agents.

If the digest is insufficient, recovery should happen through orchestration:

1. Task Execution fails, returns uncertainty, or produces low confidence output.
2. Task Reviewer detects the issue.
3. Reviewer returns `needs_more_context`, `replan`, `escalate_user`, or `escalate_outer_loop`.
4. Task Analysis, renewed digestion, or user clarification handles the recovery.

This keeps recovery explicit instead of silently expanding Worker context.

---

## Current Digestion Output Shape

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

## Final Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Should instructions be strict? | No, advisory only | Task Analysis needs flexibility to adapt. |
| Should Worker receive the original raw query? | No | Raw query can defeat context decomposition. |
| Who generates instructions? | Information Digestion | It sees both CEQ intent and broad session `Context`. |
| How does Worker recover if digest is insufficient? | Reviewer/orchestration path | Recovery should be explicit and controlled. |
