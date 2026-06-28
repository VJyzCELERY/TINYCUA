# Task Plan: TinyCUA Source-of-Truth Runtime Closure

**Spec**: `./spec.md`
**Design**: `./design.md`
**Status**: Validation In Progress
**Last Updated**: 2026-06-16

---

## Guardrails

- Do not modify `src/tinycua-sdk/`.
- Do not hardcode route decisions, task decomposition shape, app scaffolds, research conclusions, or success outputs.
- Do not use synthetic terminal success.
- Do not parse arbitrary prose into task state.
- Do not use display sanitization to hide broken state.
- Use `uv run` from `src/tinycua` for Python checks.
- Keep notebook prompts natural.

## Continuity / Compaction Protocol

If the assistant context is compacted, resumed, or transferred, continue from this file and the paired `spec.md`/`design.md` without waiting for another user prompt. The standing instruction is to keep working until the TinyCUA runtime is source-of-truth aligned, has no shortcut/hardcoded behavior, passes deterministic validation, and has live-LLM evidence for direct response and Worker-mode end-to-end flows.

On resume after compaction:

1. Re-run start preflight from project root: `uv run python .agents/scripts/preflight-start.py`.
2. Re-read:
   - `src/tinycua/specs/tinycua-source-of-truth-runtime-closure/spec.md`
   - `src/tinycua/specs/tinycua-source-of-truth-runtime-closure/design.md`
   - `src/tinycua/specs/tinycua-source-of-truth-runtime-closure/task.md`
   - source-of-truth docs listed in `design.md` references.
3. Inspect current `git diff` and continue only intended work.
4. Continue the first unchecked task in this plan.
5. Never replace missing context with hardcoded outcomes; if something is unclear, record the gap in this task file and continue source-of-truth audit/validation where possible.

---

## Phase 1 — Re-read and Audit

- [x] Re-read architecture overview.
- [x] Re-read loop overview and expected scenarios.
- [x] Re-read tool scope source of truth.
- [x] Re-read QueryAnalyst and Worker contracts.
- [x] Re-read TaskCreate, TaskAnalyzer, AnalysisEffort, TaskExecutor, ResultReviewer, ResultAggregation contracts.
- [x] Audit current runtime for each contract mismatch.
- [x] Write contract-gap checklist before code changes.

## Phase 2 — Test-First Contract Updates

- [x] Add tests for TaskCreate requiring successful `task_init` without hardcoded title.
- [x] Add tests for TaskAnalyzer/TaskAssessor tool-owned decomposition/assessment.
- [x] Add tests for documented AnalysisEffort pass controller queue behavior.
- [x] Add tests for TaskExecutor requiring action tools plus `task_result_update`.
- [x] Add tests for ResultReviewer requiring `task_review_decision` and no prose inference.
- [x] Add tests for ResultAggregation refusing to claim completion without actual task state/result.
- [x] Add tests for streaming/non-streaming validation parity.
- [x] Add guardrail tests for forbidden shortcuts and stale scaffold markers.

## Phase 3 — Runtime Implementation

- [x] Improve node instructions and retry continuations so real LLMs understand required tools and state contracts.
- [x] Replace pre-spawned analyzer duplicates with documented AnalysisEffort controller behavior.
- [x] Ensure TaskCreate/Analyzer/Assessor/Executor/Reviewer have sufficient context and tool exposure.
- [x] Ensure worker route queue shapes match `docs/design/loops/worker.md`.
- [x] Ensure retry exhaustion stops false success while preserving diagnostic/failure response capability.
- [x] Ensure streaming path applies the same validation and queue completion behavior.
- [x] Clean notebook workspace by default and expose effort/context configuration.
- [x] Route TaskExecutor runtime failures through ResultReviewer instead of terminal response.
- [x] Stop TaskExecutor turn immediately after successful `task_result_update`.
- [x] Carry reviewed task context and tool evidence/artifacts into subsequent worker tasks.
- [x] Expose full node LLM input/output/tool-call diagnostics in transcript/trace displays.
- [x] Add `scripts/run_agent.py` notebook replacement with `.env.example` configuration.
- [x] Clean `scripts/run_agent.py --stream` console output: raw reasoning/output text, concise tool markers, no event-label/raw JSON spam in live console or default summary.
- [x] Remove reviewer retry-threshold terminal escape so repeated `needs_revision` cannot route to `ResponseNode` while tasks remain incomplete.
- [x] Encourage `InformationDigester` to inspect prior context with `enhanced_context_retrieval` when useful, without forcing retrieval before `digest_information`.
- [x] Isolate `TaskExecutor` prompts to active task/task tree context instead of inherited root user/digester/chat context; apply same injection in streaming path.
- [x] Make streaming the canonical runtime path: sync execution now drains `_run_stream()` instead of maintaining a duplicate node loop; non-stream LLM dicts are adapted into stream events.
- [x] Fill empty TaskExecutor LLM content from successful `task_result_update` state so executor completion is evidence-backed without requiring a post-tool prose turn.
- [x] Remove generic validation-failure-to-`ResponseNode` routing; validation failure now retries or raises, with only explicit designed recovery paths such as TaskExecutor evidence review.
- [x] Add streamed retry support for real validation failures without using terminal `ResponseNode` as a failure escape hatch.
- [x] Remove TaskAssessor-visible executor/completion leakage from `task_update` schema/errors and rewrite TaskAssessor as whole-task-tree decomposition gate during analysis-effort passes.
- [x] Add TaskAssessor modes: upfront analysis-effort uses whole-task-tree decomposition assessment; ResultReviewer `replan` uses active/local task-region assessment before task reanalysis.

## Phase 4 — Validation

- [x] `uv run ruff check tinycua tests`
- [x] Targeted deterministic tests for runtime closure.
- [x] Broad deterministic suite.
- [x] Live notebook contract.
- [x] Manual live direct response.
- [x] Manual live app creation.
- [x] Manual live script streaming smoke test.
- [ ] Manual live research/deep-search prompt.

## Phase 5 — Iterative Self-Review

- [ ] Re-read source docs after implementation.
- [x] Re-grep runtime for forbidden markers.
- [x] Re-run deterministic validation after any fix.
- [x] Re-run live validation after deterministic pass.
- [ ] Re-run live app creation after executor/reviewer routing polish.
- [ ] Record remaining gaps or mark complete only when none remain.
