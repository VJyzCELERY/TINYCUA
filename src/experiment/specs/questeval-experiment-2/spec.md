# Feature Specification: QuestEval Research Assignment Evaluation

**Status**: Draft
**Created**: 2026-07-27
**Last Updated**: 2026-07-27
**Subproject(s) Affected**: `src/experiment`
**Primary Issue**: [VJyzCELERY/TINYCUA#172](https://github.com/VJyzCELERY/TINYCUA/issues/172)

## Problem Statement

- **Goals**: Evaluate Experiment 2 (research assignment) results using QuestEval to produce reproducible, bias-free numeric scores for each harness's research report output.
- **Gaps**: Existing evaluation uses manual LLM-as-judge scoring, which introduces evaluator bias, is not reproducible, and costs API fees per evaluation run.
- **Non-Goals**: Evaluating Experiment 1 (coding tasks), Pass@k metrics, Coherence/Fluency dimensions (QuestEval does not measure these), or replacing the template-based experiment runner from Issue #172.
- **Constraints**: QuestEval operates in reference-less mode (no gold-standard summary required). T5-small models may have limited discrimination on technical content. BERTScore is disabled on Apple Silicon.

## User Scenarios & Testing

### Primary Scenario

A researcher wants to evaluate how well each coding harness (tinycua, hermes, opencode, openclaw) performed on the research assignment: "Can you search the current latest and best frontier LLM model and how good are they? Write your findings down on a report.md." QuestEval generates questions from the ground-truth source document, answers them using each harness's report, and compares answers to produce a factual consistency score.

### Acceptance Scenarios

1. **Given** the ground-truth source document and a harness's report.md, **When** QuestEval evaluation runs, **Then** it produces a corpus_score in [0-1] measuring factual consistency and coverage.
2. **Given** all four harnesses have report.md outputs, **When** the evaluation completes, **Then** scores are saved to `questeval_scores.json` and a ranked summary is produced.
3. **Given** QuestEval scores exist, **When** compared to previous manual LLM-judge scores, **Then** the ranking order is preserved (tinycua > hermes > opencode/openclaw).

### Edge Cases

- A harness has no report.md: skip that harness with a warning.
- QuestEval models not installed: fail with clear installation instructions.
- Source document missing: fail with instruction to create `questeval_source.txt`.

## Requirements

### Functional Requirements

- **FR-001**: Load the ground-truth source document from `questeval_source.txt`.
- **FR-002**: Load each harness's `report.md` from `evaluation-results/{harness}/experiment-2/workdir/report.md`.
- **FR-003**: Run QuestEval in reference-less mode (`corpus_questeval(hypothesis=[report], sources=[source])`).
- **FR-004**: Produce per-harness `corpus_score` and `ex_level_scores`.
- **FR-005**: Save results to `evaluation-results/questeval-scores/questeval_scores.json`.
- **FR-006**: Print a ranked summary to stdout.

### Key Entities

- **Source Document**: Ground-truth Epoch AI benchmark data (June 2026) used as the reference for question generation.
- **Hypothesis**: Each harness's report.md output from Experiment 2.
- **QuestEval Score**: Factual consistency score [0-1] derived from T5 QG/QA answer matching.

## Success Criteria

- [ ] `questeval_scores.json` contains scores for all harnesses with report.md present.
- [ ] Scores are reproducible across runs (same source + hypothesis = same score).
- [ ] Ranking matches expected order: tinycua > hermes > opencode/openclaw.
- [ ] Script runs without API calls (local T5 models only).

## Testing Plan

### Unit Tests

- Source document loads correctly from `questeval_source.txt`.
- Hypothesis loading returns None for missing harness reports.
- Score JSON structure matches expected schema.

### Integration Tests

- Full evaluation pipeline produces `questeval_scores.json` with valid scores.
- Scores are within [0, 1] range.

### Manual Tests

- Run `python questeval_evaluation.py` and verify ranked output.
- Compare automated scores with previous manual evaluation summary.
