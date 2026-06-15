# Feature Specification: Benchmark Analysis Report

**Status**: In Review
**Created**: 2026-06-15
**Last Updated**: 2026-06-15
**Subproject(s) Affected**: tinycua
**Milestone**: 5.7 — Benchmark Analysis Report
**Tracking Issue**: https://github.com/VJyzCELERY/TINYCUA/issues/87

---

## Problem Statement _(mandatory)_

- **Goals**: Produce a written analysis report that compares TinyCUA harness performance (score, time, cost profile) against available WildClawBench harness baselines, breaks down results by category, documents the failure taxonomy, notes local LLM limitations and judge configuration, and provides concrete next-step recommendations for TinyCUA architecture improvements.
- **Gaps**: Milestones 5.5 (smoke runs) and 5.6 (full 60-task benchmark run) produce raw data — scores, usage, transcripts, logs, and task outputs — but no structured analysis has been performed. There is no comparison with other WildClawBench harness baselines (OpenClaw, Claude Code, Codex CLI, Hermes Agent). There is no categorized failure analysis, no performance profiling, and no documented recommendations for architecture follow-ups.
- **Non-Goals**:
  - Modifying WildClawBench tasks or grading to improve TinyCUA scores.
  - Implementing architecture improvements (those are follow-up work informed by this report).
  - Production-quality reporting UI or dashboard.
  - Modifying `tinycua-sdk` public APIs.
- **Constraints**:
  - The report SHOULD be based on actual benchmark data where available.
  - If benchmark runs are incomplete, the report MAY use architectural projections but MUST clearly mark all projected data as "Expected" or "Projected" and note the limitation prominently.
  - The report MUST be updated with empirical data once benchmark runs complete.
  - The report MUST use the structured artifact data (scores, usage, transcripts, logs) already collected.
  - Judge LLM configuration notes MUST reflect the actual configuration used during benchmark runs, not idealized setups.
  - Local LLM limitations MUST be documented honestly — the report is for internal architecture improvement, not external marketing.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A researcher or developer reads the benchmark analysis report to understand:
1. How TinyCUA performed overall and per-category compared to other harnesses.
2. What failed and why (failure taxonomy).
3. What local LLM limitations affected results.
4. What concrete architecture improvements should be prioritized next.

### Acceptance Scenarios

1. **Given** the benchmark analysis report exists, **When** a reader reviews the overall comparison section, **Then** TinyCUA's aggregate score, average time, and cost profile are presented alongside at least two other WildClawBench harness baselines.
2. **Given** the benchmark analysis report exists, **When** a reader reviews the category breakdown, **Then** each WildClawBench category (Productivity Flow, Code Intelligence, Social Interaction, Search & Retrieval, Creative Synthesis, Safety Alignment) has its own score/time comparison with baselines.
3. **Given** the benchmark analysis report exists, **When** a reader reviews the failure taxonomy, **Then** failures are grouped by category (harness crash, timeout, LLM error, missing dependency, grading error, other) with counts and representative examples.
4. **Given** the benchmark analysis report exists, **When** a reader reviews the local LLM limitations section, **Then** specific limitations observed during benchmark runs are documented (e.g., context window limits, multimodal support gaps, instruction-following quality).
5. **Given** the benchmark analysis report exists, **When** a reader reviews the judge configuration notes, **Then** the judge LLM model, endpoint, and any configuration decisions are documented.
6. **Given** the benchmark analysis report exists, **When** a reader reviews the recommendations section, **Then** at least three concrete, actionable architecture improvement recommendations are provided with rationale tied to observed benchmark data.
7. **Given** the benchmark analysis report exists, **When** a reader reviews the methodology section, **Then** the report documents how data was collected, what models were used, hardware/runtime details, and any caveats.

### Edge Cases

- What happens when some WildClawBench categories have zero successful tasks? The report documents the category as "no successful runs" and explains why.
- What happens when baseline data from other harnesses is not available? The report notes which baselines are unavailable and focuses on what can be compared.
- What happens when the full 60-task run (Milestone 5.6) was not completed? The report uses available data (smoke runs from 5.5) and clearly notes the scope limitation.
- What happens when judge grading failed for many tasks? The report documents grading failure rates and their impact on score reliability.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST produce a Markdown analysis report document.
- **FR-002**: Report MUST include an executive summary with overall TinyCUA performance headline.
- **FR-003**: Report MUST include an overall comparison section presenting TinyCUA's aggregate score, average execution time, and token/cost profile alongside available WildClawBench harness baselines.
- **FR-004**: Report MUST include a per-category breakdown comparing TinyCUA against baselines for each of the six WildClawBench categories.
- **FR-005**: Report MUST include a failure taxonomy section grouping failures by category (harness crash, timeout, LLM error, missing dependency, grading error, other) with counts and representative examples.
- **FR-006**: Report MUST include a local LLM limitations section documenting observed limitations that affected benchmark performance.
- **FR-007**: Report MUST include a judge configuration section documenting the judge LLM model, endpoint, and configuration notes.
- **FR-008**: Report MUST include a recommendations section with at least three concrete, actionable architecture improvement recommendations tied to observed benchmark data.
- **FR-009**: Report MUST include a methodology section documenting data collection process, models used, hardware, runtime, and caveats.
- **FR-010**: Report MUST reference actual data files from Milestones 5.5 and 5.6 (score summaries, usage files, failure logs).
- **FR-011**: Report MUST NOT modify WildClawBench tasks, grading, or baseline data.
- **FR-012**: Report MUST be stored in `docs/benchmark/` within the tinycua package.

### Key Entities _(include if feature involves data)_

- **BenchmarkAnalysisReport**: The final Markdown report document.
- **BaselineComparison**: Structured comparison data between TinyCUA and other harnesses.
- **CategoryBreakdown**: Per-category score/time/cost comparison.
- **FailureTaxonomy**: Categorized failure counts and examples.
- See design.md for full structure and data flow.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Report exists**: A Markdown analysis report is present in `docs/benchmark/`.
- [ ] **Executive summary**: Report includes a concise executive summary.
- [ ] **Overall comparison**: TinyCUA aggregate metrics are compared against at least two harness baselines.
- [ ] **Category breakdown**: Each WildClawBench category has its own comparison section.
- [ ] **Failure taxonomy**: Failures are categorized with counts and examples.
- [ ] **Local LLM limitations**: Observed limitations are documented with specific examples.
- [ ] **Judge configuration**: Judge LLM setup is documented.
- [ ] **Recommendations**: At least three concrete architecture improvement recommendations are provided.
- [ ] **Methodology**: Data collection, models, hardware, and caveats are documented.
- [ ] **Data references**: Report references actual artifact files from Milestones 5.5/5.6.

---

## Testing Plan _(mandatory)_

### Unit Tests

- N/A — this milestone produces a research report, not executable code.

### Integration Tests

- N/A — report content is validated through manual review against the success criteria.

### Manual Tests

- [ ] Review report against each success criterion checkbox.
- [ ] Verify all referenced data files exist and are accessible.
- [ ] Verify baseline comparison numbers are consistent with source data.
- [ ] Verify recommendations are traceable to specific benchmark observations.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Spec created | Done | |
| Design created | Done | |
| Report written | Pending | |
| Review against criteria | Pending | |

---

## Open Questions _(optional)_

1. **Which WildClawBench harness baselines are available for comparison?**
   - **Owner**: @VJyzCELERY
   - **Target**: Before report writing begins
   - **Status**: Resolved
   - **Proposed Answer**: Use whatever baseline data WildClawBench provides (OpenClaw, Claude Code, Codex CLI, Hermes Agent). If specific harness data is unavailable, note the gap and focus on available comparisons. This is the approach the report will take.

2. **Should the report be a single Markdown file or multiple files?**
   - **Owner**: @VJyzCELERY
   - **Target**: Before implementation
   - **Status**: Resolved
   - **Proposed Answer**: Single Markdown file for simplicity. The report is a research deliverable, not a multi-page publication. Can be split later if needed.

---

## Review Checklist

- [ ] No implementation details beyond what the design docs specify
- [ ] All mandatory sections completed
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
- [ ] Exit criteria match Milestone 5.7 from the roadmap issue
