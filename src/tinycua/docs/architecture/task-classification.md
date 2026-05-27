# Task Classification

> **Category:** Design Note

> **File:** `architecture/task-classification.md`
> **Last Updated:** 2026-05-27
> **Status:** Draft

This document defines how the Query Analyst chooses the processing mode for a user request.

---

## Goal

Task classification decides how much orchestration is useful. It should prevent two failure modes:

- classifying too many requests as Worker tasks, causing unnecessary overhead;
- classifying complex requests as small, causing the Primary Agent to receive too much context and hallucinate.

---

## Modes

| Mode | Use When |
|------|----------|
| `passthrough` | The request is clear, small, and safe for the Primary Agent to answer directly. |
| `digestion_only` | The request needs context reduction but not a full Worker roadmap. |
| `worker` | The request needs sequential task decomposition and review. |
| `uncertain` | The Query Analyst cannot confidently choose; run additional analysis or use digestion as a safer middle ground. |

---

## Scoring Dimensions

The Query Analyst should use a scoring rubric rather than a pure binary judgment.

Suggested dimensions:

- number of user intents;
- number of entities, files, or documents involved;
- whether external tools are likely needed;
- number of sequential steps required;
- amount of session context needed;
- ambiguity level;
- risk of hallucination if answered directly;
- expected answer complexity.

The exact thresholds are intentionally draft-level. The important rule is that the classifier must explain its reasoning.

---

## Output Shape

```yaml
mode_decision:
  mode: passthrough | digestion_only | worker | uncertain
  score: 0-10
  confidence: 0.0-1.0
  reasons:
    - "..."
  direct_response_safety_reason: "..."
  decomposition_benefit: "..."
  uncertainty_reason: "..."
```

---

## Anti-Laziness Safeguards

For `worker` mode:

- explain the decomposition benefit;
- identify why direct response is risky;
- avoid Worker mode if no clear decomposition benefit exists.

For `passthrough` mode:

- explain why direct response is safe;
- identify why context exposure is not risky;
- reject passthrough if the request requires many sequential steps.

For `uncertain` mode:

- state what is uncertain;
- prefer additional analysis or `digestion_only` over guessing.

---

## Relationship to Worker Effort

Worker mode decides whether to use the Worker. Worker effort decides how much upfront decomposition the Worker performs before execution.

Effort uses planning-depth semantics: `none` means move quickly with minimal upfront planning, while `high` means perform thorough planning before execution.

Examples:

- `worker` + `effort: none`: create a lightweight roadmap and refine during review.
- `worker` + `effort: high`: refine the roadmap thoroughly before execution begins.

---

## Examples

| Request | Likely Mode | Reason |
|---------|-------------|--------|
| “Summarize this short paragraph.” | `passthrough` | Clear, bounded, low context risk. |
| “Use our previous discussion to write a concise decision summary.” | `digestion_only` | Needs context reduction but not multi-step execution. |
| “Compare these architecture options, update the docs, and identify follow-up changes.” | `worker` | Multiple sequential steps, doc updates, and review needed. |
| “Do the thing we discussed before.” with large history | `uncertain` or `digestion_only` | Ambiguous reference requires context recovery before routing. |
