# Tasks: TinyCUA Benchmark Docker Image

Implementation tasks for the TinyCUA Benchmark Docker Image. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for Docker image build and container lifecycle (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

### Dockerfile & Container Setup

- [ ] Create `Dockerfile` at project root with `python:3.11-slim` base <!-- id: 2 -->
  - [ ] Install system dependencies (bash, coreutils, curl, git, wget)
  - [ ] Install uv package manager
  - [ ] Copy and install Python dependencies
  - [ ] Copy TinyCUA source and tinycua-sdk
  - [ ] Install TinyCUA packages (non-editable)
  - [ ] Set WORKDIR to `/tmp_workspace`

- [ ] Create `scripts/entrypoint.sh` with environment validation <!-- id: 3 -->
  - [ ] Validate `TINYCUA_BASE_URL` is set
  - [ ] Validate `/tmp_workspace` is mounted and writable
  - [ ] Export environment variables for TinyCUA
  - [ ] Execute `tinycua benchmark run` with correct arguments
  - [ ] Handle graceful shutdown and signal trapping

### CLI Benchmark Subcommand

- [ ] Add `benchmark` subcommand to `cli/main.py` <!-- id: 4 -->
  - [ ] Register `benchmark` subparser with `run` sub-subcommand
  - [ ] Add `--prompt`, `--workspace`, `--output`, `--timeout` arguments
  - [ ] Dispatch to `cli/benchmark.py`

- [ ] Create `cli/benchmark.py` with benchmark run logic <!-- id: 5 -->
  - [ ] Parse benchmark-specific arguments
  - [ ] Read `TASK_PROMPT` from environment or argument
  - [ ] Configure workspace paths (`/tmp_workspace`, `/tmp_workspace/results`, `/tmp_workspace/transcript.jsonl`)
  - [ ] Invoke TinyCUA agent loop with benchmark defaults
  - [ ] Return exit code 0 on success, non-zero on failure

### Documentation

- [ ] Create `docs/benchmark/README.md` with usage documentation <!-- id: 7 -->
  - [ ] Build instructions
  - [ ] Configuration reference (env vars, volumes)
  - [ ] Networking setup for local model endpoints
  - [ ] Troubleshooting guide

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 8 -->
  - Tests defined in `implementation-plan.md` under "Success Criteria — Integration Tests (TDD First)"
  - Write `tests/test_docker_image.py` with 5 test classes: TestDockerfileBuild, TestContainerStartup, TestWorkspaceMounting, TestEnvironmentVariables, TestTinyCUAInstalled
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 9 -->

## Verification Phase

- [ ] Build image manually: `docker build -t tinycua-benchmark .` <!-- id: 10 -->
- [ ] Verify image size is under 2GB <!-- id: 11 -->
- [ ] Run container and verify CLI is accessible <!-- id: 12 -->
- [ ] Test with a real local model endpoint (Ollama / LM Studio) <!-- id: 13 -->

## Documentation Phase

- [ ] Update `docs/benchmark/README.md` with any findings from manual testing <!-- id: 14 -->
- [ ] Add environment variable reference to documentation <!-- id: 15 -->

## Post-MVP Enhancements

- [ ] Create `docker-compose.benchmark.yml` for local development <!-- id: 6 -->
  - [ ] Define service with volume mounts and env vars
  - [ ] Configure `host.docker.internal` networking for Linux

## Review and Merge

- [ ] Create pull request <!-- id: 16 -->
- [ ] Address review feedback <!-- id: 17 -->
- [ ] Merge to main branch <!-- id: 18 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-14*
