# Tasks: TinyCUA CLI / Runtime Entry Point

Implementation tasks for TinyCUA CLI / Runtime Entry Point. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for CLI argument parsing, config loading, exit codes, transcript writing, and log writing (in `src/tinycua/tests/integration/test_cli_run.py`) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create `tinycua/cli/config.py` — `load_config()` function that reads `TINYCUA_BASE_URL`, `TINYCUA_API_KEY`, `TINYCUA_MODEL` from env vars, applies CLI overrides, validates required fields <!-- id: 2 -->
  - [ ] Implement `load_config(base_url, api_key, model)` → dict with base_url, api_key, model
  - [ ] Add validation: raise `ValueError` if base_url or api_key missing after env + CLI merge
- [ ] Create `tinycua/cli/transcript.py` — `write_transcript(messages, path)` function that writes OpenClaw-compatible JSONL <!-- id: 3 -->
  - [ ] Implement `write_transcript()` — each line is a JSON object with role/content
  - [ ] Ensure output directory is created if it doesn't exist
- [ ] Create `tinycua/cli/logging.py` — `write_log_entry(path, event, level, data)` function for structured JSON logs <!-- id: 4 -->
  - [ ] Implement `write_log_entry()` — JSON lines with timestamp, event, level, data
  - [ ] Implement `write_log_entry()` as append-only (open file in append mode)
- [ ] Create `tinycua/cli/run.py` — `run` subcommand with argparse, agent execution, timeout watchdog, transcript/log writing <!-- id: 5 -->
  - [ ] Implement `parse_args(argv)` — argparse with `--prompt`, `--timeout`, `--output-dir`, `--workspace`, `--base-url`, `--api-key`, `--model`, `--verbose`
  - [ ] Implement `run_command()` — orchestrates config loading, agent creation, execution, timeout, transcript/log writing, returns exit code
  - [ ] Implement timeout watchdog using `threading.Timer` — send `threading.Event` to interrupt agent after timeout
  - [ ] Handle exit code 124 on timeout
  - [ ] Handle exit code 1 on agent errors
  - [ ] Handle exit code 0 on success
- [ ] Modify `tinycua/cli/main.py` — replace no-op with argparse subcommand dispatcher <!-- id: 6 -->
  - [ ] Add `argparse` with `run` subcommand
  - [ ] Dispatch to `run_command()` when `tinycua run` is invoked
  - [ ] Show help when `tinycua` is invoked without subcommand
- [ ] Modify `tinycua/loops/tinycua_loop.py` — expose working messages for transcript capture <!-- id: 7 -->
  - [ ] Add `self._working_messages: list[dict] = []` to `__init__()`
  - [ ] Set `self._working_messages = working` in `_run_sync()` before returning
  - [ ] Add `get_working_messages()` property method
- [ ] Instrument `TinyCUALoop._call_llm()` to capture `response.usage` per node and store alongside messages in `_working_messages` <!-- id: 21 -->
  - [ ] Add `usage: dict | None = None` field to each message dict stored in `_working_messages`
  - [ ] Set usage from response object after each `_call_llm()` call

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 8 -->
- [ ] Write unit tests for config loading edge cases (missing env vars, invalid timeout, empty prompt) <!-- id: 9 -->
- [ ] Write unit tests for transcript and log writer (empty messages, special characters, large transcripts) <!-- id: 10 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 11 -->

## Verification Phase

- [ ] Run `tinycua run "echo hello"` against a local LLM endpoint and verify transcript output <!-- id: 12 -->
- [ ] Run with `--timeout 5` against a slow prompt and verify timeout behavior (exit code 124) <!-- id: 13 -->
- [ ] Run with invalid endpoint and verify error handling (exit code 1) <!-- id: 14 -->
- [ ] Verify `tinycua` without subcommand shows help <!-- id: 15 -->

## Documentation Phase

- [ ] Update `src/tinycua/README.md` (if exists) with CLI usage examples <!-- id: 16 -->
- [ ] Add a "Usage Examples" section to `specs/5.1-cli-runtime-entry-point/spec.md` with CLI invocation examples (e.g., `tinycua run "create a file"`, `tinycua run --timeout 120 --model llama-3-8b "do something"`) <!-- id: 17 -->

## Review and Merge

- [ ] Create pull request <!-- id: 18 -->
- [ ] Address review feedback <!-- id: 19 -->
- [ ] Merge to main branch <!-- id: 20 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-13*
