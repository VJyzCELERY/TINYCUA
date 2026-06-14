# Tasks: WildClawBench Smoke Runs

Implementation tasks for WildClawBench Smoke Runs (Milestone 5.5). Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for smoke-run orchestration (defined in implementation-plan.md) <!-- id: 0 -->
  - [ ] test_smoke_run_produces_report_with_all_categories
  - [ ] test_smoke_run_collects_artifacts_per_task
  - [ ] test_smoke_run_skips_unavailable_dependencies
  - [ ] test_smoke_run_report_json_and_markdown
- [ ] Write unit tests for smoke-run components <!-- id: 1 -->
  - [ ] test SmokeTaskSelector — category coverage, skip logic for missing dependencies
  - [ ] test categorize_failure — each failure category (harness_crash, timeout, llm_error, missing_dependency, grading_error, other)
  - [ ] test SmokeReportGenerator — correct aggregation, per-category breakdown
  - [ ] test SmokeResult — construction, serialization, status enumeration
  - [ ] test idempotency — re-run does not overwrite prior artifact directories
- [ ] Run all tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

- [ ] Implement SmokeTask dataclass <!-- id: 3 -->
  - [ ] Define frozen dataclass with task_id, category, prompt, timeout_seconds, workspace_path, output_dir, dependencies
- [ ] Implement SmokeTaskSelector <!-- id: 4 -->
  - [ ] Define static curated task list per WildClawBench category (one per category minimum)
  - [ ] Implement dependency checking logic (capability → task mapping)
  - [ ] Implement skip logic for tasks with unavailable dependencies
- [ ] Implement failure categorization <!-- id: 5 -->
  - [ ] Implement categorize_failure() with exception/exit-code heuristics
  - [ ] Support all 6 failure categories: harness_crash, timeout, llm_error, missing_dependency, grading_error, other
- [ ] Implement SmokeResult and SmokeReport dataclasses <!-- id: 6 -->
  - [ ] SmokeResult: task_id, category, status, elapsed_time, usage, failure_reason, failure_category, artifact_paths
  - [ ] SmokeReport: run_timestamp, model, base_url, totals, results, category_summary, failure_taxonomy
- [ ] Implement SmokeRunOrchestrator <!-- id: 7 -->
  - [ ] Wire task selection → execution → artifact collection pipeline
  - [ ] Support both local CLI mode (tinycua run) and Docker adapter mode
  - [ ] Implement cooperative timeout per task (subprocess timeout)
  - [ ] Validate output directory writability upfront (fail fast)
- [ ] Implement SmokeReportGenerator <!-- id: 8 -->
  - [ ] Generate JSON summary report (smoke-report.json)
  - [ ] Generate Markdown summary report (smoke-report.md)
  - [ ] Aggregate per-category pass/fail/skip counts
  - [ ] Aggregate failure taxonomy (category → count)
- [ ] Add tinycua smoke-run CLI subcommand <!-- id: 9 -->
  - [ ] Register subcommand in cli/main.py
  - [ ] Accept flags: --model, --base-url, --api-key, --timeout, --mode, --output, --verbose
  - [ ] Wire CLI to SmokeRunOrchestrator.run()
  - [ ] Print summary table to stdout after completion

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 10 -->
- [ ] Run unit tests — expect GREEN (all pass) <!-- id: 11 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 12 -->
- [ ] Verify no regressions in existing tests <!-- id: 13 -->

## Verification Phase

- [ ] Manual: Run smoke script against a live local model endpoint <!-- id: 14 -->
- [ ] Manual: Verify artifacts (agent.log, transcript.jsonl, usage.json) are produced per task <!-- id: 15 -->
- [ ] Manual: Verify smoke-run report accurately reflects pass/fail/skip status <!-- id: 16 -->
- [ ] Manual: Verify idempotent re-runs do not corrupt prior artifacts <!-- id: 17 -->

## Documentation Phase

- [ ] Update spec.md success criteria checkboxes to reflect completed items <!-- id: 18 -->
- [ ] Update spec.md status tracker <!-- id: 19 -->

## Review and Merge

- [ ] Create pull request <!-- id: 20 -->
- [ ] Address review feedback <!-- id: 21 -->
- [ ] Merge to main branch <!-- id: 22 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-14*
