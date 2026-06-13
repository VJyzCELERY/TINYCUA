# Tasks: WildClawBench TinyCUA BaseAgent Adapter

Implementation tasks for Milestone 5.2. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for WildClawBench adapter (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->
  - Command: `cd src/tinycua && uv run pytest tests/integration/test_wildclawbench_integration.py -v`

## Implementation Phase

### Phase 1 — Local BaseAgent Copy

- [ ] Create `tinycua/wildclawbench/__init__.py` package init <!-- id: 2 -->
- [ ] Create `tinycua/wildclawbench/base_agent.py` with local copies of `BaseAgent` ABC, `AgentTaskSpec`, and `AgentExecution` <!-- id: 3 -->
  - [ ] Define `AgentTaskSpec` frozen dataclass with all fields from WildClawBench
  - [ ] Define `AgentExecution` dataclass with `elapsed_time`, `error`, `gateway_proc`, `agent_proc`
  - [ ] Define `BaseAgent` ABC with `expects_gateway`, `transcript_container_path`, `prepare_grading_transcript()`, `run_task()`, `collect_usage()`

### Phase 2 — TinyCUAAgent Adapter

- [ ] Create `tinycua/wildclawbench/agent.py` with `TinyCUAAgent` class <!-- id: 4 -->
  - [ ] Implement `__init__()` with `base_url`, `api_key`, `model`, `tinycua_bin` parameters
  - [ ] Implement `expects_gateway` property returning `False`
  - [ ] Implement `transcript_container_path` property returning `/tmp_workspace/results/transcript.jsonl`
  - [ ] Implement `prepare_grading_transcript()` returning `transcript_container_path`
- [ ] Implement `run_task()` subprocess spawning <!-- id: 5 -->
  - [ ] Build CLI command: `tinycua run <prompt> --timeout <t> --output-dir <d> --workspace <w> --model <m>`
  - [ ] Add optional `--base-url` and `--api-key` flags when configured
  - [ ] Set environment variables for subprocess (`TINYCUA_BASE_URL`, `TINYCUA_API_KEY`, `TINYCUA_MODEL`)
  - [ ] Create output directory and workspace if they don't exist
  - [ ] Spawn subprocess with `Popen()` and `communicate(timeout=...)`
  - [ ] Handle `TimeoutExpired` — kill process, set error message
  - [ ] Handle `FileNotFoundError` — set error for missing binary
  - [ ] Handle non-zero exit codes — include stderr in error message
  - [ ] Return `AgentExecution` with `elapsed_time` and optional `error`
- [ ] Implement `collect_usage()` transcript parsing <!-- id: 6 -->
  - [ ] Read `transcript.jsonl` from output directory
  - [ ] Count LLM request events (`"llm"` or `"response"` in event type)
  - [ ] Sum `total_tokens` from `usage` fields in events
  - [ ] Return `{"requests": int, "total_tokens": int|None, "cost": 0.0}`
  - [ ] Return zeroed values when transcript is missing or unparseable

### Phase 3 — Unit Tests

- [ ] Create `tests/unit/test_wildclawbench_agent.py` <!-- id: 7 -->
  - [ ] Test `expects_gateway` returns `False`
  - [ ] Test `transcript_container_path` returns correct string
  - [ ] Test `prepare_grading_transcript` returns `transcript_container_path`
  - [ ] Test `run_task` builds correct CLI command (mock Popen, capture args)
  - [ ] Test `run_task` includes `--base-url` and `--api-key` when configured
  - [ ] Test `run_task` sets environment variables for subprocess
  - [ ] Test `run_task` returns `AgentExecution` with `elapsed_time >= 0`
  - [ ] Test `run_task` returns error when binary not found
  - [ ] Test `run_task` returns error on non-zero exit code
  - [ ] Test `run_task` kills process on timeout
  - [ ] Test `run_task` creates output directory if missing
  - [ ] Test `run_task` creates workspace if missing
  - [ ] Test `collect_usage` returns expected keys
  - [ ] Test `collect_usage` parses transcript for request counts and tokens
  - [ ] Test `collect_usage` returns zeroed values for missing transcript

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 8 -->
  - Command: `cd src/tinycua && uv run pytest tests/integration/test_wildclawbench_integration.py -v`
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 9 -->

## Verification Phase

- [ ] Verify adapter can be imported: `python -c "from tinycua.wildclawbench.agent import TinyCUAAgent"` <!-- id: 10 -->
- [ ] Verify `BaseAgent` ABC is satisfied (no abstract method errors) <!-- id: 11 -->
- [ ] Verify `run_task` handles all error cases gracefully <!-- id: 12 -->
- [ ] Verify `collect_usage` handles missing/malformed transcripts <!-- id: 13 -->

## Documentation Phase

- [ ] Update status tracker in `spec.md` — mark completed items <!-- id: 14 -->
- [ ] Update `design.md` implementation phases — mark completed phases <!-- id: 15 -->

## Review and Merge

- [ ] Create pull request <!-- id: 16 -->
- [ ] Address review feedback <!-- id: 17 -->
- [ ] Merge to main branch <!-- id: 18 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-14*
