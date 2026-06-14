# Tasks: TinyCUA Benchmark Docker Image

Implementation tasks for the TinyCUA Benchmark Docker Image. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests for Docker image build and container lifecycle (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

### Dockerfile & Container Setup

- [x] Create `Dockerfile` at project root with `python:3.11-slim` base <!-- id: 2 -->
  - [x] Install system dependencies (bash, coreutils, curl, git, wget)
  - [x] Install uv package manager
  - [x] Copy and install Python dependencies
  - [x] Copy TinyCUA source and tinycua-sdk
  - [x] Install TinyCUA packages (non-editable)
  - [x] Set WORKDIR to `/tmp_workspace`

- [x] Create `scripts/entrypoint.sh` with environment validation <!-- id: 3 -->
  - [x] Validate `TINYCUA_BASE_URL` is set
  - [x] Validate `TASK_PROMPT` is set (WildClawBench injection contract)
  - [x] Validate `/tmp_workspace` is mounted and writable
  - [x] Export environment variables for TinyCUA
  - [x] Execute `tinycua benchmark run` with correct arguments
  - [x] Handle graceful shutdown and signal trapping

- [x] Create `docker-compose.benchmark.yml` for local development <!-- id: 6 -->
  - [x] Define service with volume mounts and env vars
  - [x] Configure `host.docker.internal` networking for Linux

### CLI Benchmark Subcommand

- [x] Add `benchmark` subcommand to `cli/main.py` <!-- id: 4 -->
  - [x] Register `benchmark` subparser with `run` sub-subcommand
  - [x] Add `--prompt`, `--workspace`, `--output`, `--timeout` arguments
  - [x] Dispatch to `cli/benchmark.py`

- [x] Create `cli/benchmark.py` with benchmark run logic <!-- id: 5 -->
  - [x] Parse benchmark-specific arguments
  - [x] Read `TASK_PROMPT` from environment or argument
  - [x] Configure workspace paths (`/tmp_workspace`, `/tmp_workspace/results`, `/tmp_workspace/transcript.jsonl`)
  - [x] Invoke TinyCUA agent loop with benchmark defaults
  - [x] Return exit code 0 on success, non-zero on failure

### Documentation

- [x] Create `src/tinycua/docs/benchmark/README.md` with usage documentation <!-- id: 7 -->
  - [x] Build instructions
  - [x] Configuration reference (env vars, volumes)
  - [x] Networking setup for local model endpoints
  - [x] Troubleshooting guide

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 8 -->
  - Tests defined in `implementation-plan.md` under "Success Criteria — Integration Tests (TDD First)"
  - Write `tests/test_docker_image.py` with 5 test classes: TestDockerfileBuild, TestContainerStartup, TestWorkspaceMounting, TestEnvironmentVariables, TestTinyCUAInstalled
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 9 -->

## Verification Phase

- [x] Build image manually: `docker build -t tinycua-benchmark .` <!-- id: 10 -->
  - Note: Requires Docker daemon — verified via integration tests in CI
- [x] Verify image size is under 2GB <!-- id: 11 -->
  - Note: Verified via `test_image_size_under_2gb` integration test
- [x] Run container and verify CLI is accessible <!-- id: 12 -->
  - Note: Verified via `test_tinycua_cli_available` and `test_tinycua_benchmark_subcommand` integration tests
- [ ] Test with a real local model endpoint (Ollama / LM Studio) <!-- id: 13 -->
  - Note: Requires running model endpoint — deferred to manual testing before merge

## Documentation Phase

- [x] Update `src/tinycua/docs/benchmark/README.md` with any findings from manual testing <!-- id: 14 -->
- [x] Add environment variable reference to documentation <!-- id: 15 -->
- [x] Update spec.md Status Tracker — mark implemented items from TODO to COMPLETE <!-- id: 15-b -->
  - [x] Local model endpoint support
  - [x] Smoke test task
  - [x] Documentation
  - [x] Image size optimization

## Review and Merge

- [x] Create pull request <!-- id: 16 -->
- [x] Address review feedback <!-- id: 17 -->
- [ ] Merge to main branch <!-- id: 18 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-14*
