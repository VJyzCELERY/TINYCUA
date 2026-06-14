# Tasks: Full 60-Task Local-LLM Benchmark Run

Implementation tasks for Milestone 5.6 — Full 60-Task Local-LLM Benchmark Run. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests for RunMetadata, TaskResult, SummaryAggregate, summary_all.json output, and preflight_check in `tests/test_benchmark_orchestrator.py` <!-- id: 0 -->
- [x] Run integration tests — expect RED (failures) since no implementation exists yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Benchmark Script Structure

- [x] Update `src/tinycua/.env.example` with benchmark-related variables (LLM_BASE_URL, LLM_MODEL) <!-- id: 23 -->
- [x] Create `src/tinycua/scripts/__init__.py` (empty package init) <!-- id: 2 -->
- [x] Add usage instructions in script docstrings or inline comments <!-- id: 24 -->
- [x] Create `src/tinycua/scripts/benchmark_config.py` with `BenchmarkConfig` dataclass <!-- id: 3 -->
  - [x] Define fields: model_name, base_url, api_key, timeout_seconds, concurrent_tasks, docker_image, use_docker, preserve_artifacts, verbose
  - [x] Add CLI argument parsing (argparse) for overriding config defaults
  - [x] Add `from_args()` class method to construct config from CLI args
- [x] Create `src/tinycua/scripts/collect_metadata.py` <!-- id: 4 -->
  - [x] Implement `collect_run_metadata(config) -> RunMetadata` — gather CPU info, GPU info, RAM, Python version, runtime version
  - [x] Implement `preflight_check(output_dir) -> None` — verify output directory is writable
  - [x] Add graceful fallback for missing hardware fields (return "unknown")
- [x] Create `src/tinycua/scripts/run_benchmark.py` — main orchestrator script <!-- id: 5 -->
  - [x] Define `TaskResult` dataclass
  - [x] Define `SummaryAggregate` dataclass with `from_task_results()` class method
  - [x] Implement task list loading — discover all 60 WildClawBench task IDs (from package or hardcoded list)
  - [x] Implement `run_full_benchmark(config, output_dir, tasks)` — main execution loop
  - [x] Add argparse CLI entry point at module level (`if __name__ == "__main__"`)
  - [x] Add `--tasks` CLI argument (comma-separated task IDs) to override default full suite

### Phase 2 — Data Collection and Aggregation

- [x] Implement per-task result collection — call `TinyCUAAgent.run_task()` and capture `AgentExecution` <!-- id: 6 -->
  - [x] Handle timeout errors (mark as "timeout" status)
  - [x] Handle connection errors (mark as "error" status)
  - [x] Handle task failures (mark as "failed" status with error details)
- [x] Implement usage data collection via `TinyCUAAgent.collect_usage()` <!-- id: 7 -->
- [x] Implement aggregate statistics calculation in `SummaryAggregate.from_task_results()` <!-- id: 8 -->
  - [x] Compute pass/fail/skip counts
  - [x] Compute average, min, max, median scores (handle None scores)
  - [x] Compute category breakdown scores

### Phase 3 — Output Generation

- [x] Implement `summary_all.json` schema validation and writing <!-- id: 9 -->
  - [x] Write metadata section from RunMetadata
  - [x] Write summary section from SummaryAggregate
  - [x] Write tasks array from list of TaskResult
  - [x] Ensure valid JSON output with readable formatting
- [x] Implement task artifact directory structure — `results/<task_id>/` for transcripts, usage, logs <!-- id: 10 -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 12 -->
- [ ] Write unit tests for metadata collection edge cases (missing GPU, read-only dir) <!-- id: 13 -->
- [x] Write unit tests for summary statistics edge cases (all pass, all fail, zero tasks) <!-- id: 14 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 15 -->

## Verification Phase

- [ ] Run subset benchmark: `uv run python src/tinycua/scripts/run_benchmark.py --tasks t1,t2,t3` with a local LLM endpoint <!-- id: 16 -->
- [x] Verify `summary_all.json` exists and contains metadata, summary, and tasks sections <!-- id: 17 -->
- [x] Verify task artifacts (transcript.jsonl, usage.json, agent.log) exist for each task <!-- id: 18 -->
- [x] Verify metadata includes model name, endpoint, hardware, runtime version <!-- id: 19 -->
- [x] Test preflight_check rejects read-only output directory <!-- id: 21 -->
- [ ] Verify `--tasks t1,t2,t3` runs only specified tasks <!-- id: 31 -->

## Documentation Phase

- [x] Add `benchmark_results/` to `.gitignore` <!-- id: 22 -->
- [x] Update spec.md success criteria checkboxes after verification <!-- id: 28 -->
- [x] Update design.md implementation phase checkboxes after verification <!-- id: 29 -->
- [x] Update spec.md review checklist after review completion <!-- id: 30 -->

## Review and Merge

- [x] Create pull request <!-- id: 25 -->
- [ ] Address review feedback <!-- id: 26 -->
- [ ] Merge to main branch <!-- id: 27 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-15*
