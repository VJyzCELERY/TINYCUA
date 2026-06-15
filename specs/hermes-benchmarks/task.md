# Tasks: Hermes-Agent Benchmark Integration

Implementation tasks for Hermes-Agent Benchmark Integration. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests for HermesAgent (defined in implementation-plan.md) <!-- id: 0 -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

### Phase 1 — Hermes Config & Agent Core

- [x] Create `HermesConfig` dataclass and YAML loader in `tinycua/wildclawbench/hermes_config.py` <!-- id: 2 -->
  - [x] Define `HermesConfig` dataclass with `model`, `api_base`, `api_key_env`, `temperature`, `max_tokens`, `timeout`
  - [x] Implement `load_hermes_config(path: str) -> HermesConfig` with validation
  - [x] Validate required fields (`model`, `api_base`, `api_key_env`)
  - [x] Validate file existence
  - [x] Write unit tests for config validation (missing file, missing fields, type errors)
- [x] Create `HermesAgent` adapter class in `tinycua/wildclawbench/hermes_agent.py` <!-- id: 3 -->
  - [x] Implement `__init__` with config loading
  - [x] Implement `expects_gateway` property (return False)
  - [x] Implement `transcript_container_path` property (return `/workspace/transcript.jsonl`)
  - [x] Implement `_build_docker_command` — construct `docker run` with volume mounts, env vars
  - [x] Implement `run_task` — Docker build check, subprocess spawn, timeout handling
  - [x] Implement `collect_usage` — parse transcript JSONL, count requests/tokens
  - [x] Handle missing API key env var (error, not crash)
  - [x] Handle Docker build failure (log, skip, return error)
  - [x] Handle container timeout (same pattern as TinyCUA)
- [x] Export `HermesAgent` from `tinycua/wildclawbench/__init__.py` <!-- id: 4 -->
- [x] Write unit tests for `HermesAgent` <!-- id: 5 -->
  - [x] Config validation tests
  - [x] Docker command construction tests
  - [x] Error handling tests (missing API key, build failure, timeout)
  - [x] Usage collection tests

### Phase 2 — Docker Infrastructure

- [x] Create `docker/Dockerfile.hermes` — multi-stage Dockerfile for Hermes agent <!-- id: 6 -->
  - [x] Base on upstream WildClawBench commit `86d7144`
  - [x] Pin Hermes agent version
  - [x] Document expected image size
- [x] Create `scripts/build_hermes_image.sh` — Docker build script with layer caching <!-- id: 7 -->

### Phase 3 — Benchmark Pipeline Integration

- [x] Modify `tinycua/scripts/benchmark_config.py` — add CLI arguments <!-- id: 8 -->
  - [x] Add `agent_backend: str` field to `BenchmarkConfig`
  - [x] Add `hermes_config_path: str | None` field
  - [x] Add `--agent-backend` argument with choices `["tinycua", "hermesagent"]`
  - [x] Add `--hermes-config` argument
  - [x] Propagate args through `from_args()`
- [x] Refactor `tinycua/scripts/run_benchmark.py` — agent factory <!-- id: 9 -->
  - [x] Add `_create_agent(config)` factory function
  - [x] Change `run_full_benchmark` to accept `agent: BaseAgent | None = None`
  - [x] Update `main()` to use factory
  - [x] Import `HermesAgent`
- [x] Write unit tests for agent factory and CLI arg propagation <!-- id: 10 -->

### Phase 4 — Side-by-Side Comparison

- [x] Create `tinycua/scripts/compare_results.py` <!-- id: 11 -->
  - [x] Implement `compare_results(tinycua_data, hermes_data) -> dict`
  - [x] Per-task comparison with score deltas
  - [x] Aggregate comparison with average score deltas
  - [x] Write `comparison.json` output
  - [x] Add CLI entry point `python -m tinycua.scripts.compare_results`
- [x] Write unit tests for `compare_results` <!-- id: 12 -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 13 -->
- [x] Write remaining unit tests for edge cases <!-- id: 14 -->
  - [x] Malformed transcript JSON handling
  - [x] Hermes agent with empty task list
  - [x] Concurrent config profiles
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 15 -->
  - 731 passed, 1 pre-existing flaky failure, 18 skipped — no regressions

## Verification Phase

- [ ] Run Hermes agent smoke test (3 tasks) with mock API endpoint <!-- id: 16 -->
- [ ] Verify transcript output is WildClawBench-compatible JSONL <!-- id: 17 -->
- [ ] Run side-by-side comparison with a known TinyCUA baseline <!-- id: 18 -->
- [ ] Verify graceful failure scenarios (missing API key, bad config, Docker not installed) <!-- id: 19 -->

## Documentation Phase

- [x] Create `docs/hermes-benchmark-setup.md` — step-by-step setup guide <!-- id: 20 -->
- [x] Update benchmark README with Hermes agent usage <!-- id: 21 -->
- [ ] Update changelog with new feature <!-- id: 22 --> (no changelog file exists)

## Review and Merge

- [ ] Create pull request with `implementation-plan.md` and `task.md` as reference <!-- id: 23 -->
- [ ] Address review feedback <!-- id: 24 -->
- [ ] Merge to base branch <!-- id: 25 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-15*
