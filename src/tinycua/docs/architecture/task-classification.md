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
- routing complex requests to the Primary Agent when they need Worker decomposition.

---

## Modes

| Mode | Use When |
|------|----------|
| `primary_agent` | The request can start with the Primary Agent. The Primary Agent may still invoke Information Digestion if it needs consolidated context. |
| `worker` | The request needs sequential task decomposition and review. |
| `uncertain` | The Query Analyst cannot confidently choose and must select `uncertain_next_action`. |

---

## Scoring Dimensions

The Query Analyst should use a scoring rubric rather than a pure binary judgment.

Suggested dimensions:

- number of user intents;
- number of entities, files, or documents involved;
- whether external tools are likely needed;
- number of sequential steps required;
- amount of session `Context` needed;
- ambiguity level;
- risk of hallucination if answered directly;
- expected answer complexity.

The exact thresholds are intentionally draft-level. The important rule is that the classifier must explain its reasoning.

---

## Output Shape

```yaml
mode_decision:
  mode: primary_agent | worker | uncertain
  score: 0-10
  confidence: 0.0-1.0
  reasons:
    - "..."
  primary_agent_safety_reason: "..."
  decomposition_benefit: "..."
  uncertainty_reason: "..."
  uncertain_next_action: ask_user | explore_more | null
```

---

## Anti-Laziness Safeguards

For `worker` mode:

- explain the decomposition benefit;
- identify why direct response is risky;
- avoid Worker mode if no clear decomposition benefit exists.

For `primary_agent` mode:

- explain why Primary Agent handling is safe;
- identify why Worker decomposition is not required;
- allow the Primary Agent to invoke Information Digestion if it needs context consolidation.

For `uncertain` mode:

- state what is uncertain;
- set `uncertain_next_action` to `ask_user` or `explore_more`;
- avoid leaving uncertainty as an open-ended nondeterministic state.

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
| “Summarize this short paragraph.” | `primary_agent` | Clear, bounded, low context risk. |
| “Use our previous discussion to write a concise decision summary.” | `primary_agent` | Primary Agent can request Information Digestion if consolidated context is needed. |
| “Compare these architecture options, update the docs, and identify follow-up changes.” | `worker` | Multiple sequential steps, doc updates, and review needed. |
| “Do the thing we discussed before.” with large history | `uncertain` | Ambiguous reference requires `ask_user` or `explore_more` before routing. |
