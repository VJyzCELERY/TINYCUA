# Task Classification

> **Category:** Design Note

> **File:** `architecture/task-classification.md`
> **Last Updated:** 2026-05-30
> **Status:** Implemented
> **See also:** [query-analyst.md](query-analyst.md), [state-objects.md](state-objects.md), [worker-orchestration.md](worker-orchestration.md)

This document defines how the Query Analyst chooses the processing mode for a user request.

---

## Goal

Classification decides how much orchestration is useful. It should prevent two failure modes:

- classifying too many requests as Worker tasks, causing unnecessary overhead;
- routing complex requests to the Primary Agent when they need Worker decomposition.

---

## Classification Labels

| Label | Use When |
|-------|----------|
| `passthrough` | The request can go directly to the Primary Agent. The Primary Agent may still invoke Information Digestion if it needs consolidated context. |
| `worker` | The request needs sequential task decomposition and review. |

`uncertain` is not a label. If the agent cannot decide, the loop retries or keeps the agent active — indecision does not produce a terminal classification.

---

## Scoring Dimensions

The Query Analyst uses a `ClassificationTool` with configurable labels. The rubric should consider three high-level dimensions when selecting a label:

- **Task complexity** — the breadth of work implied by the request;
- **Context dependency** — how much session `Context` is needed and how ambiguous the reference is;
- **Safety and risk** — hallucination risk if answered directly and the complexity of the expected answer.

The exact thresholds belong in implementation docs.

---

## Output Shape

The Query Analyst produces a `Classification` via the configured `ClassificationTool`. See [state-objects.md](state-objects.md) for the canonical schema and [query-analyst.md](query-analyst.md) for the agent's output contract.

---

## Anti-Laziness Safeguards

The classifier must guard against two failure modes:

- **Worker overuse**: `worker` mode requires a clear decomposition benefit and a stated reason why direct response is risky.
- **Unsafe passthrough routing**: `passthrough` requires a clear rationale for safe handling and an explanation of why Worker decomposition is not needed.

If the agent cannot decide between labels, it does not produce a terminal classification. The loop retries or keeps the agent active — indecision is handled through re-evaluation, not a special `uncertain` route.

---

## Relationship to Worker Effort

Classification decides whether to use the Worker. Worker effort decides how much upfront decomposition the Worker performs before execution.

Effort uses planning-depth semantics modeled on LLM reasoning effort. See [state-objects.md](state-objects.md) for the `Worker Config` schema and effort-level semantics.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Classification approach | Configurable `ClassificationTool` with labels | Same QueryAnalyst node serves both root and worker input gates |
| Scoring dimensions | Task complexity, context dependency, safety/risk | Covers the three axes that meaningfully distinguish routing needs |
| Anti-laziness safeguards | Worker overuse and unsafe passthrough | Covers the ways the classifier can misroute; indecision is handled via retry/open-question |
| Label definitions | Passthrough and worker | Worker requires decomposition benefit; passthrough requires safety rationale |
| Effort relationship | Separate from classification | Classification decides whether to use the Worker; effort decides how much upfront planning within it |
