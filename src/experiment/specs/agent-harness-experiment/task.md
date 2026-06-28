# Tasks: Agent Harness Experiment

Implementation tasks for Agent Harness Experiment. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests from `implementation-plan.md` for stub-Docker sequential execution, failure continuation, empty prompt rejection, and overwrite guard <!-- id: 0 -->
- [x] Write unit tests for prompt loading, metadata generation, result path creation, and overwrite behavior <!-- id: 1 -->
- [x] Write static tests for `docker-compose.yml` and Dockerfiles: four services, four named volumes, shared `.env`, TINYCUA local package install <!-- id: 2 -->
- [x] Run tests — expect RED because implementation files do not exist yet: `cd src/experiment && uv run pytest` <!-- id: 3 -->

## Implementation Phase

- [x] Create minimal Python experiment subproject <!-- id: 4 -->
  - [x] Add `src/experiment/pyproject.toml` with pytest dev dependency
  - [x] Add empty package/test structure only where needed
- [x] Implement `src/experiment/run_experiment.py` <!-- id: 5 -->
  - [x] Parse `--num`, `--prompt`, `--prompt-file`, `--overwrite`, and test-only `--output-root`
  - [x] Reject missing or whitespace-only prompts before Docker runs
  - [x] Invoke services in order: `opencode`, `hermes`, `openclaw`, `tinycua`
  - [x] Capture stdout/stderr and write per-agent artifacts
  - [x] Write `metadata.json` with timing, status, and exit code
  - [x] Continue after per-agent failures and return non-zero if any agent failed
- [x] Add shared experiment configuration <!-- id: 6 -->
  - [x] Add `src/experiment/.env.example`
  - [x] Include example local model config: `http://localhost:1234/v1`, `qwen3.5-9b`, `<put_api_key_here>`
  - [x] Document `host.docker.internal` for container-to-host access
- [x] Add Docker Compose file <!-- id: 7 -->
  - [x] Define four separate services
  - [x] Define `Opencode_Vol`, `Hermes_Vol`, `Openclaw_Vol`, `TINYCUA_Vol`
  - [x] Use shared `env_file: .env`
  - [x] Add `host.docker.internal:host-gateway`
- [x] Add TINYCUA container setup <!-- id: 8 -->
  - [x] Add `docker/tinycua.Dockerfile`
  - [x] Install local `src/tinycua-sdk` then local `src/tinycua` with uv
  - [x] Run `tinycua run` with `--dir`, `--provider-url`, `--api-key`, `--model`, `--provider-type`, and `--timeout`
- [x] Add Opencode container setup <!-- id: 9 -->
  - [x] Add `docker/opencode.Dockerfile`
  - [x] Install `opencode-ai`
  - [x] Map shared model/provider config visibly, with `EXPERIMENT_OPENCODE_MODEL` as the only override
  - [x] Preserve config/setup failures in stderr
- [x] Add OpenClaw container setup <!-- id: 10 -->
  - [x] Add `docker/openclaw.Dockerfile`
  - [x] Install `openclaw@latest` or use official image if simpler
  - [x] Generate minimal `~/.openclaw/openclaw.json` from shared env
  - [x] Run `openclaw agent --message "$EXPERIMENT_PROMPT"`
- [x] Add Hermes container setup <!-- id: 11 -->
  - [x] Add `docker/hermes.Dockerfile`
  - [x] Use simplest verified Hermes install path
  - [x] Map shared provider/model/key config
  - [x] Fail loudly if local OpenAI-compatible base URL is unsupported
- [x] Add only-if-useful shell wrapper(s) for per-container prompt/log writing <!-- id: 12 -->
  - [x] Prefer duplicated simple entrypoints if a shared wrapper gets clever
  - [x] Ensure every container writes to `/workspace/experiment-${EXPERIMENT_NUM}`

## Testing Phase

- [x] Run integration tests — expect GREEN: `cd src/experiment && uv run pytest tests/integration` <!-- id: 13 -->
- [x] Run unit/static tests — expect GREEN: `cd src/experiment && uv run pytest tests/unit` <!-- id: 14 -->
- [x] Run full experiment test suite: `cd src/experiment && uv run pytest` <!-- id: 15 -->
- [x] Run existing relevant TINYCUA CLI tests if TINYCUA invocation assumptions changed: `cd src/tinycua && uv run pytest tests/integration/test_cli_run.py` <!-- id: 16 -->

## Verification Phase

- [x] Build images: `cd src/experiment && docker compose build` <!-- id: 17 -->
- [x] Create `.env` from `.env.example` and adjust host URL if needed <!-- id: 18 -->
- [x] Run a short real prompt: `cd src/experiment && uv run python run_experiment.py --num 1 --prompt "write hello.txt"` <!-- id: 19 -->
- [x] Inspect each agent's `prompt.txt`, `container.env`, `stdout.log`, `stderr.log`, and `metadata.json` <!-- id: 20 -->
- [x] Confirm failed harness setup is readable rather than hidden <!-- id: 21 -->

## Documentation Phase

- [x] Add `src/experiment/README.md` with only build/run/result inspection commands <!-- id: 22 -->
- [x] Update `src/README.md` to list `experiment` if desired by project convention <!-- id: 23 -->
- [x] Keep spec/design/task docs in `src/experiment/specs/agent-harness-experiment/` <!-- id: 24 -->

## Review and Merge

- [ ] Commit implementation in small TDD-friendly commits <!-- id: 25 -->
- [ ] Push branch and update PR #145 <!-- id: 26 -->
- [ ] Address review feedback <!-- id: 27 -->
- [ ] Merge after tests and review pass <!-- id: 28 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-18*
