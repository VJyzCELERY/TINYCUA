# Task Classification

> **Category:** Design Note

> **File:** `architecture/task-classification.md`
> **See also:** [Query Analyst](query-analyst.md), [State Objects](state-objects.md), [Worker Orchestration](worker-orchestration.md)
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

The Query Analyst should use a scoring rubric rather than a pure binary judgment. At the architecture level, the rubric should consider three high-level dimensions:

- **Task complexity** — how many intents, entities, steps, and tools are involved;
- **Context dependency** — how much session `Context` is needed and how ambiguous the reference is;
- **Safety and risk** — hallucination risk if answered directly and the complexity of the expected answer.

The exact thresholds and sub-dimensions belong in implementation docs. The important architectural rule is that the classifier must explain its reasoning.

---

## Output Shape

The Query Analyst produces a `Mode Decision` object. See [state-objects.md](state-objects.md) for the canonical schema and [query-analyst.md](query-analyst.md) for the agent's output contract.

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
- set `uncertain_next_action` to `explore` or `ask_user`;
- `explore`: the Query Analyst should attempt to resolve uncertainty on its own. It may invoke exploratory agents (e.g., the Information Digester can retrieve and narrow missing context, or a research-oriented agent can gather additional information). After exploration, re-classify the request;
- `ask_user`: pause and request clarification from the user (human-in-the-loop);
- avoid leaving uncertainty as an open-ended nondeterministic state — uncertainty should always resolve to a concrete action.

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
| "Do the thing we discussed before." with large history | `uncertain` | Ambiguous reference requires `ask_user` or `explore` before routing. |
