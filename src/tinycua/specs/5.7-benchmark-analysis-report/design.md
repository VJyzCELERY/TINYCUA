# Design Document: Benchmark Analysis Report

**Spec**: `./spec.md`
**Status**: In Review
**Last Updated**: 2026-06-15

---

## Overview

This design implements Milestone 5.7 — Benchmark Analysis Report. It produces a structured Markdown research report that analyzes TinyCUA's WildClawBench benchmark performance data from Milestones 5.5 (smoke runs) and 5.6 (full 60-task run), compares it against available harness baselines, categorizes failures, documents local LLM limitations and judge configuration, and provides concrete architecture improvement recommendations. The report is a research deliverable — it does not introduce executable code beyond the report document itself.

---

## Architecture

### Component Overview

```
Benchmark Data (5.5/5.6 artifacts)
  → Data Collection (score summaries, usage, transcripts, logs)
  → Analysis Sections:
      ├── Executive Summary
      ├── Overall Comparison (vs baselines)
      ├── Category Breakdown (per-category comparison)
      ├── Failure Taxonomy (categorized failures)
      ├── Local LLM Limitations
      ├── Judge Configuration Notes
      ├── Recommendations (architecture follow-ups)
      └── Methodology
  → Benchmark Analysis Report (docs/benchmark/analysis-report.md)
```

### Affected Components

> **Path convention**: All paths are relative to `src/tinycua/`.

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `docs/benchmark/analysis-report.md` | New | The benchmark analysis report document |
| `docs/benchmark/README.md` | Modified | Added link to analysis report in "Analysis Report" section |
| `specs/5.7-benchmark-analysis-report/spec.md` | New | This spec |
| `specs/5.7-benchmark-analysis-report/design.md` | New | This design |

---

## Data Model

### Input Data Sources

The report consumes structured data from prior milestones:

| Source | Milestone | Format | Location |
|--------|-----------|--------|----------|
| Smoke run summary | 5.5 | JSON + Markdown | `benchmark_results/` or smoke-run output directories (from Milestone 5.5 execution) |
| Full benchmark summary | 5.6 | `summary_all.json` or equivalent | `benchmark_results/` (from Milestone 5.6 execution) |
| Per-task transcripts | 5.4 | JSONL | `benchmark_results/results/<task_id>/` (from Milestone 5.4/5.5/5.6 execution) |
| Per-task usage | 5.4 | JSON | `benchmark_results/results/<task_id>/` (from Milestone 5.4/5.5/5.6 execution) |
| Per-task logs | 5.1 | Text | `benchmark_results/results/<task_id>/` (from Milestone 5.1/5.5/5.6 execution) |

### Report Structure

```markdown
# TinyCUA WildClawBench Benchmark Analysis Report

## Executive Summary
## Methodology
## Overall Comparison
## Category Breakdown
  ### Productivity Flow
  ### Code Intelligence
  ### Social Interaction
  ### Search & Retrieval
  ### Creative Synthesis
  ### Safety Alignment
## Failure Taxonomy
## Local LLM Limitations
## Judge Configuration Notes
## Recommendations
## Appendix: Raw Data References
```

### Baseline Comparison Data

> **Note**: The structures below are conceptual data models for illustration only — they will not be implemented as code.

```python
@dataclass
class HarnessBaseline:
    name: str                     # "OpenClaw", "Claude Code", etc.
    aggregate_score: float | None  # Overall score (None if unavailable)
    avg_time_seconds: float | None
    total_tokens: int | None
    category_scores: dict[str, float | None]  # category → score
```

### Category Breakdown Entry

```python
@dataclass
class CategoryAnalysis:
    category: str
    tinycua_score: float | None
    tinycua_avg_time: float | None
    tinycua_tasks_attempted: int
    tinycua_tasks_passed: int
    baselines: dict[str, float | None]  # harness_name → score
    failure_count: int
    failure_categories: dict[str, int]  # failure_type → count
```

---

## API / Interface Contracts

### Report Sections

This milestone produces a document, not executable interfaces. The report sections map to the spec requirements:

| Section | Spec Requirement | Data Source |
|---------|-----------------|-------------|
| Executive Summary | FR-002 | Aggregate metrics from summary files |
| Overall Comparison | FR-003 | TinyCUA summary + baseline data |
| Category Breakdown | FR-004 | Per-category scores from summary + baselines |
| Failure Taxonomy | FR-005 | Failure categorization from smoke runs (5.5) and full run (5.6) |
| Local LLM Limitations | FR-006 | Observed behavior during execution + transcript analysis |
| Judge Configuration | FR-007 | Configuration used during benchmark runs |
| Recommendations | FR-008 | Derived from analysis of failures, limitations, and comparison gaps |
| Methodology | FR-009 | Documentation of setup, models, hardware, caveats |

### Error Handling

| Situation | Response |
|-----------|----------|
| Baseline data unavailable for a harness | Note the gap in the comparison table; focus on available baselines |
| No successful tasks in a category | Document as "0/N passed" with failure reasons |
| Full 60-task run not completed | Note scope limitation; use available smoke-run data |
| Judge grading failed for many tasks | Document grading failure rate and impact on score reliability |
| Local model endpoint details unknown | Document what is known; note gaps in hardware/endpoint details |

---

## Implementation Phases

### Phase 1 — Data Collection and Validation (required)

- [x] Assess available artifact data (determined: no TinyCUA runs completed yet)
- [ ] Collect all benchmark artifacts from Milestones 5.5 and 5.6 (deferred — unavailable because runs not executed)
- [ ] Validate score summary files exist and are parseable (deferred — unavailable because runs not executed)
- [ ] Validate usage files contain non-null token counts (deferred — unavailable because runs not executed)
- [x] Catalog available baseline data from WildClawBench (documented in report)
- [x] Document any missing data gaps (documented in report methodology section)

### Phase 2 — Report Writing (required)

- [ ] Write executive summary with headline metrics
- [ ] Write methodology section documenting setup, models, hardware, caveats
- [ ] Write overall comparison section with baseline table
- [ ] Write per-category breakdown sections
- [ ] Write failure taxonomy with counts and examples
- [ ] Write local LLM limitations section
- [ ] Write judge configuration notes
- [ ] Write recommendations section with at least three concrete items
- [ ] Write appendix with raw data file references

### Phase 3 — Review and Validation (required)

- [ ] Verify all success criteria checkboxes are met
- [ ] Verify baseline comparison numbers match source data
- [ ] Verify recommendations are traceable to specific observations
- [ ] Peer review of report quality and completeness

---

## Technical Decisions

1. **Decision**: Produce a single Markdown file rather than multiple reports or a dashboard.
   - **Reason**: The report is a research deliverable for internal architecture improvement. A single Markdown file is easy to read in PRs, issues, and Git history. It avoids unnecessary infrastructure for a one-time analysis.
   - **Alternatives Considered**: Multi-file report with separate per-category files — rejected as over-engineering for a single analysis pass. HTML dashboard — rejected because it requires hosting and is not version-controlled naturally.

2. **Decision**: Base the report on actual artifact data where available; if benchmark runs are incomplete, use architectural projections clearly marked as "Expected" or "Projected."
   - **Reason**: Actual TinyCUA benchmark runs were not completed by the report deadline. Projections are used for TinyCUA-specific analysis and are clearly distinguished from baseline data.
   - **Alternatives Considered**: Synthetic data without disclosure — rejected because it would undermine the report's credibility. Projections with clear labeling are used instead.

3. **Decision**: Include representative failure examples (transcript snippets) rather than just counts.
   - **Reason**: Failure counts alone don't explain why things failed. Representative examples help developers understand root causes and prioritize fixes.
   - **Alternatives Considered**: Counts-only failure taxonomy — rejected because it lacks diagnostic value for architecture improvement recommendations.

4. **Decision**: Document local LLM limitations as observed facts rather than speculating about model quality.
   - **Reason**: The report is for internal use. Honest documentation of what the local model could and couldn't do is more useful than subjective quality judgments.
   - **Alternatives Considered**: Subjective quality ratings — rejected because they're not reproducible and may not reflect the actual failure modes.

5. **Decision**: Recommendations section must tie each recommendation to specific benchmark data.
   - **Reason**: Untied recommendations are opinion. Data-tied recommendations are actionable and defensible.
   - **Alternatives Considered**: General best-practice recommendations — rejected because they don't leverage the benchmark data that this milestone exists to analyze.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Baseline data from other harnesses is incomplete or unavailable | High | Medium | Document available baselines; focus comparison on what's available; note gaps explicitly |
| Full 60-task run (5.6) was not completed | Medium | High | Use smoke-run data (5.5) as primary source; note scope limitation in methodology |
| Local model endpoint details are not well-documented | Medium | Low | Document what is known; note gaps; recommendations can account for uncertainty |
| Report becomes too long for PR review | Low | Low | Keep report concise; use tables for comparisons; appendix for raw data references |
| Failure examples are too verbose | Medium | Low | Use 2-3 sentence summaries per example; full transcripts are in artifact directories |

---

## Open Questions _(optional)_

1. **Where should the final report be committed?**
   - **Resolved**: `docs/benchmark/analysis-report.md` within the tinycua package, alongside the existing `docs/benchmark/README.md`.
   - **Owner**: @VJyzCELERY
   - **Target**: Before implementation
   - **Rationale**: Keeps the report with other benchmark documentation. The `docs/benchmark/` directory already exists and contains benchmark-related documentation.

2. **Should the report be generated programmatically or written manually?**
   - **Resolved**: Written manually, informed by data. The analysis requires human judgment for recommendations and limitation documentation. Data tables can be extracted from summaries, but the narrative and recommendations are human-authored.
   - **Owner**: @VJyzCELERY
   - **Target**: Before implementation
   - **Rationale**: A research report benefits from human analysis and interpretation. Programmatic generation would produce tables but not insights.

---

## References

- Spec: [./spec.md](./spec.md)
- Milestone 5.7 contract: `issue #87` — "compare TinyCUA harness score/time/cost profile with available WildClawBench harness baselines; category breakdown; failure taxonomy; local LLM limitations and judge configuration notes; next-step recommendations for TinyCUA architecture improvements"
- Prior milestones:
  - Milestone 5.5: `specs/5.5-wildclawbench-smoke-runs/` — smoke run data and artifacts
  - Milestone 5.6: Full 60-task benchmark run data (if completed)
  - Milestone 5.4: `specs/5.4-transcript-artifacts/` — transcript and usage format
  - Milestone 5.3: `specs/5.3-docker-image/` — Docker image for benchmark runs
  - Milestone 5.1: `specs/5.1-cli-runtime-entry-point/` — CLI entry point
- WildClawBench sources:
  - GitHub: `https://github.com/InternLM/WildClawBench`
  - Paper: `https://arxiv.org/abs/2605.10912`
  - Leaderboard: `https://internlm.github.io/WildClawBench/`
  - Dataset: `https://huggingface.co/datasets/internlm/WildClawBench`
