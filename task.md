# Tasks: Full 60-Task Local-LLM Benchmark Run

Implementation tasks for Milestone 5.6 — Full 60-Task Local-LLM Benchmark Run. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for RunMetadata, TaskResult, SummaryAggregate, summary_all.json output, and preflight_check in `tests/test_benchmark_orchestrator.py` <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation exists yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Benchmark Script Structure

- [ ] Create `src/tinycua/scripts/__init__.py` (empty package init) <!-- id: 2 -->
- [ ] Create `src/tinycua/scripts/benchmark_config.py` with `BenchmarkConfig` dataclass <!-- id: 3 -->
  - [ ] Define fields: model_name, base_url, api_key, timeout_seconds, concurrent_tasks, docker_image, use_docker, preserve_artifacts, verbose
  - [ ] Add CLI argument parsing (argparse) for overriding config defaults
  - [ ] Add `from_args()` class method to construct config from CLI args
- [ ] Create `src/tinycua/scripts/collect_metadata.py` <!-- id: 4 -->
  - [ ] Implement `collect_run_metadata(config) -> RunMetadata` — gather CPU info, GPU info, RAM, Python version, runtime version
  - [ ] Implement `preflight_check(output_dir) -> None` — verify output directory is writable
  - [ ] Add graceful fallback for missing hardware fields (return "unknown")
- [ ] Create `src/tinycua/scripts/run_benchmark.py` — main orchestrator script <!-- id: 5 -->
  - [ ] Define `TaskResult` dataclass
  - [ ] Define `SummaryAggregate` dataclass with `from_task_results()` class method
  - [ ] Implement task list loading — discover all 60 WildClawBench task IDs (from package or hardcoded list)
  - [ ] Implement `run_full_benchmark(config, output_dir, tasks)` — main execution loop
  - [ ] Implement resumption: track completed task IDs in `.completed` file; skip on re-run
  - [ ] Add argparse CLI entry point at module level (`if __name__ == "__main__"`)

### Phase 2 — Data Collection and Aggregation

- [ ] Implement per-task result collection — call `TinyCUAAgent.run_task()` and capture `AgentExecution` <!-- id: 6 -->
  - [ ] Handle timeout errors (mark as "timeout" status)
  - [ ] Handle connection errors (mark as "error" status)
  - [ ] Handle task failures (mark as "failed" status with error details)
- [ ] Implement usage data collection via `TinyCUAAgent.collect_usage()` <!-- id: 7 -->
- [ ] Implement aggregate statistics calculation in `SummaryAggregate.from_task_results()` <!-- id: 8 -->
  - [ ] Compute pass/fail/skip counts
  - [ ] Compute average, min, max, median scores (handle None scores)
  - [ ] Compute category breakdown scores

### Phase 3 — Output Generation

- [ ] Implement `summary_all.json` schema validation and writing <!-- id: 9 -->
  - [ ] Write metadata section from RunMetadata
  - [ ] Write summary section from SummaryAggregate
  - [ ] Write tasks array from list of TaskResult
  - [ ] Ensure valid JSON output with readable formatting
- [ ] Implement task artifact directory structure — `results/<task_id>/` for transcripts, usage, logs <!-- id: 10 -->
- [ ] Implement `.completed` file tracking for run resumption <!-- id: 11 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 12 -->
- [ ] Write unit tests for metadata collection edge cases (missing GPU, read-only dir) <!-- id: 13 -->
- [ ] Write unit tests for summary statistics edge cases (all pass, all fail, zero tasks) <!-- id: 14 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 15 -->

## Verification Phase

- [ ] Run subset benchmark: `uv run python scripts/run_benchmark.py --tasks t1,t2,t3` with a local LLM endpoint <!-- id: 16 -->
- [ ] Verify `summary_all.json` exists and contains metadata, summary, and tasks sections <!-- id: 17 -->
- [ ] Verify task artifacts (transcript.jsonl, usage.json, agent.log) exist for each task <!-- id: 18 -->
- [ ] Verify metadata includes model name, endpoint, hardware, runtime version <!-- id: 19 -->
- [ ] Test resumption: interrupt a run, re-run, verify completed tasks are skipped <!-- id: 20 -->
- [ ] Test preflight_check rejects read-only output directory <!-- id: 21 -->

## Documentation Phase

- [ ] Add `benchmark_results/` to `.gitignore` <!-- id: 22 -->
- [ ] Update `src/tinycua/.env.example` with benchmark-related variables <!-- id: 23 -->
- [ ] Add usage instructions in script docstrings or inline comments <!-- id: 24 -->

## Review and Merge

- [ ] Create pull request <!-- id: 25 -->
- [ ] Address review feedback <!-- id: 26 -->
- [ ] Merge to main branch <!-- id: 27 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-14*
