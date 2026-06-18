# Tasks: Agent Harness Experiment

Implementation tasks for Agent Harness Experiment. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests from `implementation-plan.md` for stub-Docker sequential execution, failure continuation, empty prompt rejection, and overwrite guard <!-- id: 0 -->
- [ ] Write unit tests for prompt loading, metadata generation, result path creation, and overwrite behavior <!-- id: 1 -->
- [ ] Write static tests for `docker-compose.yml` and Dockerfiles: four services, four named volumes, shared `.env`, TINYCUA local package install <!-- id: 2 -->
- [ ] Run tests — expect RED because implementation files do not exist yet: `cd src/experiment && uv run pytest` <!-- id: 3 -->

## Implementation Phase

- [ ] Create minimal Python experiment subproject <!-- id: 4 -->
  - [ ] Add `src/experiment/pyproject.toml` with pytest dev dependency
  - [ ] Add empty package/test structure only where needed
- [ ] Implement `src/experiment/run_experiment.py` <!-- id: 5 -->
  - [ ] Parse `--num`, `--prompt`, `--prompt-file`, `--overwrite`, and test-only `--output-root`
  - [ ] Reject missing or whitespace-only prompts before Docker runs
  - [ ] Invoke services in order: `opencode`, `hermes`, `openclaw`, `tinycua`
  - [ ] Capture stdout/stderr and write per-agent artifacts
  - [ ] Write `metadata.json` with timing, status, and exit code
  - [ ] Continue after per-agent failures and return non-zero if any agent failed
- [ ] Add shared experiment configuration <!-- id: 6 -->
  - [ ] Add `src/experiment/.env.example`
  - [ ] Include example local model config: `http://localhost:1234/v1`, `qwen3.5-9b`, `<put_api_key_here>`
  - [ ] Document `host.docker.internal` for container-to-host access
- [ ] Add Docker Compose file <!-- id: 7 -->
  - [ ] Define four separate services
  - [ ] Define `Opencode_Vol`, `Hermes_Vol`, `Openclaw_Vol`, `TINYCUA_Vol`
  - [ ] Use shared `env_file: .env`
  - [ ] Add `host.docker.internal:host-gateway`
- [ ] Add TINYCUA container setup <!-- id: 8 -->
  - [ ] Add `docker/tinycua.Dockerfile`
  - [ ] Install local `src/tinycua-sdk` then local `src/tinycua` with uv
  - [ ] Run `tinycua run` with `--dir`, `--provider-url`, `--api-key`, `--model`, `--provider-type`, and `--timeout`
- [ ] Add Opencode container setup <!-- id: 9 -->
  - [ ] Add `docker/opencode.Dockerfile`
  - [ ] Install `opencode-ai`
  - [ ] Map shared model/provider config visibly, with `EXPERIMENT_OPENCODE_MODEL` as the only override
  - [ ] Preserve config/setup failures in stderr
- [ ] Add OpenClaw container setup <!-- id: 10 -->
  - [ ] Add `docker/openclaw.Dockerfile`
  - [ ] Install `openclaw@latest` or use official image if simpler
  - [ ] Generate minimal `~/.openclaw/openclaw.json` from shared env
  - [ ] Run `openclaw agent --message "$EXPERIMENT_PROMPT"`
- [ ] Add Hermes container setup <!-- id: 11 -->
  - [ ] Add `docker/hermes.Dockerfile`
  - [ ] Use simplest verified Hermes install path
  - [ ] Map shared provider/model/key config
  - [ ] Fail loudly if local OpenAI-compatible base URL is unsupported
- [ ] Add only-if-useful shell wrapper(s) for per-container prompt/log writing <!-- id: 12 -->
  - [ ] Prefer duplicated simple entrypoints if a shared wrapper gets clever
  - [ ] Ensure every container writes to `/workspace/experiment-${EXPERIMENT_NUM}`

## Testing Phase

- [ ] Run integration tests — expect GREEN: `cd src/experiment && uv run pytest tests/integration` <!-- id: 13 -->
- [ ] Run unit/static tests — expect GREEN: `cd src/experiment && uv run pytest tests/unit` <!-- id: 14 -->
- [ ] Run full experiment test suite: `cd src/experiment && uv run pytest` <!-- id: 15 -->
- [ ] Run existing relevant TINYCUA CLI tests if TINYCUA invocation assumptions changed: `cd src/tinycua && uv run pytest tests/integration/test_cli_run.py` <!-- id: 16 -->

## Verification Phase

- [ ] Build images: `cd src/experiment && docker compose build` <!-- id: 17 -->
- [ ] Create `.env` from `.env.example` and adjust host URL if needed <!-- id: 18 -->
- [ ] Run a short real prompt: `cd src/experiment && uv run python run_experiment.py --num 1 --prompt "write hello.txt"` <!-- id: 19 -->
- [ ] Inspect each agent's `prompt.txt`, `stdout.log`, `stderr.log`, and `metadata.json` <!-- id: 20 -->
- [ ] Confirm failed harness setup is readable rather than hidden <!-- id: 21 -->

## Documentation Phase

- [ ] Add `src/experiment/README.md` with only build/run/result inspection commands <!-- id: 22 -->
- [ ] Update `src/README.md` to list `experiment` if desired by project convention <!-- id: 23 -->
- [ ] Keep spec/design/task docs in `src/experiment/specs/agent-harness-experiment/` <!-- id: 24 -->

## Review and Merge

- [ ] Commit implementation in small TDD-friendly commits <!-- id: 25 -->
- [ ] Push branch and update PR #145 <!-- id: 26 -->
- [ ] Address review feedback <!-- id: 27 -->
- [ ] Merge after tests and review pass <!-- id: 28 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-18*
