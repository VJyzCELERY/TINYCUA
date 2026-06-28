# Tasks: WildClawBench Smoke Runs

Implementation tasks for WildClawBench Smoke Runs (Milestone 5.5). Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests for smoke-run orchestration (defined in implementation-plan.md) <!-- id: 0 -->
  - [x] test_smoke_run_produces_report_with_all_categories
  - [x] test_smoke_run_collects_artifacts_per_task
  - [x] test_smoke_run_skips_unavailable_dependencies
  - [x] test_smoke_run_report_json_and_markdown
- [x] Write unit tests for smoke-run components <!-- id: 1 -->
  - [x] test SmokeTaskSelector — category coverage, skip logic for missing dependencies
  - [x] test categorize_failure — each failure category (harness_crash, timeout, llm_error, missing_dependency, grading_error, other)
  - [x] test SmokeReportGenerator — correct aggregation, per-category breakdown
  - [x] test SmokeResult — construction, serialization, status enumeration
  - [x] test idempotency — re-run does not overwrite prior artifact directories
- [x] Run all tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

- [x] Implement SmokeTask dataclass <!-- id: 3 -->
  - [x] Define frozen dataclass with task_id, category, prompt, timeout_seconds, workspace_path, output_dir, dependencies
- [x] Implement SmokeTaskSelector <!-- id: 4 -->
  - [x] Define static curated task list per WildClawBench category (one per category minimum)
  - [x] Implement dependency checking logic (capability → task mapping)
  - [x] Implement skip logic for tasks with unavailable dependencies
- [x] Implement failure categorization <!-- id: 5 -->
  - [x] Implement categorize_failure() with exception/exit-code heuristics
  - [x] Support all 6 failure categories: harness_crash, timeout, llm_error, missing_dependency, grading_error, other
- [x] Implement SmokeResult and SmokeReport dataclasses <!-- id: 6 -->
  - [x] SmokeResult: task_id, category, status, elapsed_time, usage, failure_reason, failure_category, artifact_paths
  - [x] SmokeReport: run_timestamp, model, base_url, totals, results, category_summary, failure_taxonomy
- [x] Implement SmokeRunOrchestrator <!-- id: 7 -->
  - [x] Wire task selection → execution → artifact collection pipeline
  - [x] Support both local CLI mode (tinycua run) and Docker adapter mode
  - [x] Implement cooperative timeout per task (subprocess timeout)
  - [x] Validate output directory writability upfront (fail fast)
- [x] Implement SmokeReportGenerator <!-- id: 8 -->
  - [x] Generate JSON summary report (smoke-report.json)
  - [x] Generate Markdown summary report (smoke-report.md)
  - [x] Aggregate per-category pass/fail/skip counts
  - [x] Aggregate failure taxonomy (category → count)
- [x] Add tinycua smoke-run CLI subcommand <!-- id: 9 -->
  - [x] Register subcommand in cli/main.py
  - [x] Accept flags: --model, --base-url, --api-key, --timeout, --mode, --output, --verbose
  - [x] Wire CLI to SmokeRunOrchestrator.run()
  - [x] Print summary table to stdout after completion

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 10 -->
- [x] Run unit tests — expect GREEN (all pass) <!-- id: 11 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 12 -->
- [x] Verify no regressions in existing tests <!-- id: 13 -->

## Verification Phase

- [ ] Manual: Run smoke script against a live local model endpoint <!-- id: 14 -->
- [ ] Manual: Verify artifacts (agent.log, transcript.jsonl, usage.json) are produced per task <!-- id: 15 -->
- [ ] Manual: Verify transcript.jsonl is parseable by WildClawBench's transcript_loader.py (OpenClaw-compatible JSONL format) <!-- id: 15b -->
- [ ] Manual: Verify smoke-run script does not mutate WildClawBench task files (FR-009 integrity constraint) <!-- id: 15c -->
- [ ] Manual: Verify smoke-run report accurately reflects pass/fail/skip status <!-- id: 16 -->
- [ ] Manual: Verify idempotent re-runs do not corrupt prior artifacts <!-- id: 17 -->

## Documentation Phase

- [x] Update spec.md success criteria checkboxes to reflect completed items <!-- id: 18 -->
- [x] Update spec.md status tracker <!-- id: 19 -->
- [x] Update design.md implementation phase checkboxes to reflect completed items <!-- id: 19b -->
- [x] Update implementation-plan.md verification and environment pre-requisite checkboxes to reflect completed items <!-- id: 19c -->

## Review and Merge

- [ ] Create pull request <!-- id: 20 -->
- [ ] Address review feedback <!-- id: 21 -->
- [ ] Merge to main branch <!-- id: 22 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-14*
