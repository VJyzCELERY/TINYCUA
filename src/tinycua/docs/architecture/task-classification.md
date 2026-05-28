# Task Classification

> **Category:** Design Note

> **File:** `architecture/task-classification.md`
> **Last Updated:** 2026-05-27
> **Status:** Draft
> **See also:** [query-analyst.md](query-analyst.md), [state-objects.md](state-objects.md), [worker-orchestration.md](worker-orchestration.md)

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

The classifier must guard against three failure modes:

- **Worker overuse**: `worker` mode requires a clear decomposition benefit and a stated reason why direct response is risky. Without both, the classifier should not select `worker`.
- **Unsafe Primary Agent routing**: `primary_agent` mode requires a clear rationale for safe handling and an explanation of why Worker decomposition is not needed. The Primary Agent may still invoke Information Digestion if context consolidation is useful.
- **Open-ended uncertainty**: `uncertain` mode must set `uncertain_next_action` to `explore` or `ask_user` — never leave uncertainty as a nondeterministic state. `explore` resolves uncertainty by gathering more context (then re-classifies); `ask_user` pauses for human input.

---

## Relationship to Worker Effort

Worker mode decides whether to use the Worker. Worker effort decides how much upfront decomposition the Worker performs before execution.

Effort uses planning-depth semantics modeled on LLM reasoning effort. See [state-objects.md](state-objects.md) for the `Worker Config` schema and effort-level semantics.

---
