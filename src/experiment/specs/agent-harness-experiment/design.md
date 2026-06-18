# Design Document: Agent Harness Experiment

**Spec**: `./spec.md`  
**Status**: Draft  
**Last Updated**: 2026-06-18

---

## Overview

Add a lightweight `src/experiment` subproject with Docker Compose, four agent images, one shared `.env`, and one runner script. The runner executes Opencode, Hermes, Openclaw, and TINYCUA sequentially with the same prompt and shared model settings, stores each agent's artifacts in its own named volume, and records timing metadata as plain files. TINYCUA is always installed from this repository's local `src/tinycua-sdk` and `src/tinycua` packages so experiments test the branch under review.

---

## Architecture

### Component Overview

```
researcher
    |
    v
run_experiment.py --num N --prompt "..."
    |
    +--> docker compose run opencode --> Opencode_Vol/experiment-N/
    +--> docker compose run hermes   --> Hermes_Vol/experiment-N/
    +--> docker compose run openclaw --> Openclaw_Vol/experiment-N/
    +--> docker compose run tinycua  --> TINYCUA_Vol/experiment-N/

shared .env --> normalized provider/model/base-url/api-key settings
```

Each service is a separate container with its own named volume mounted at `/workspace`:

| Agent | Service | Volume | Result root |
|-------|---------|--------|-------------|
| Opencode | `opencode` | `Opencode_Vol` | `/workspace/experiment-{num}` |
| Hermes | `hermes` | `Hermes_Vol` | `/workspace/experiment-{num}` |
| OpenClaw | `openclaw` | `Openclaw_Vol` | `/workspace/experiment-{num}` |
| TINYCUA | `tinycua` | `TINYCUA_Vol` | `/workspace/experiment-{num}` |

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `src/experiment/specs/agent-harness-experiment/spec.md` | New | Product scope for the experiment harness. |
| `src/experiment/specs/agent-harness-experiment/design.md` | New | This design. |
| `src/experiment/docker-compose.yml` | New | Defines four one-shot services and four named volumes. |
| `src/experiment/.env.example` | New | Documents normalized shared settings. |
| `src/experiment/run_experiment.py` | New | Small sequential runner and metadata collector. |
| `src/experiment/docker/*.Dockerfile` | New | Minimal per-agent images. |

---

## Data Model

### New Entities _(if applicable)_

```text
ExperimentResult:
    experiment_num: int
    agent: "opencode" | "hermes" | "openclaw" | "tinycua"
    prompt: str
    started_at: ISO-8601 timestamp
    ended_at: ISO-8601 timestamp
    duration_seconds: float
    exit_code: int
    status: "passed" | "failed"
```

Each agent volume stores:

```text
experiment-{num}/
  prompt.txt
  stdout.log
  stderr.log
  metadata.json
```

### Schema Changes _(if applicable)_

- No existing schema changes.
- Result files are append-free: one experiment directory is one immutable-ish run unless `--overwrite` is used.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

Command-line interface:

```bash
uv run python run_experiment.py --num 1 --prompt "Implement a small todo CLI"
uv run python run_experiment.py --num 1 --prompt-file prompt.txt
```

Runner contract:

- Requires exactly one prompt source: `--prompt` or `--prompt-file`.
- Runs agents in this order: `opencode`, `hermes`, `openclaw`, `tinycua`.
- Uses Docker Compose services with shared `env_file: .env`.
- Writes metadata even when an agent exits non-zero.

Shared `.env` keys:

```text
EXPERIMENT_LLM_PROVIDER=openai-compatible
EXPERIMENT_LLM_MODEL=qwen3.5-9b
EXPERIMENT_LLM_BASE_URL=http://localhost:1234/v1
EXPERIMENT_LLM_API_KEY=<put_api_key_here>
EXPERIMENT_TIMEOUT_SECONDS=900
EXPERIMENT_TINYCUA_PROVIDER_TYPE=openai-chat-completions
```

Per-agent containers map these normalized keys to native config names at the container boundary. Do not build a universal config translator in the MVP; keep the mapping visible in each Dockerfile or entrypoint.

### Container Setup Contracts

#### TINYCUA

- **Base image**: `python:3.12-slim`.
- **Install source**: local repository code only.
- **Build context**: repository root, so the image can copy `src/tinycua-sdk` and `src/tinycua`.
- **Install command**:

```Dockerfile
COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /usr/local/bin/uv
COPY src/tinycua-sdk ./tinycua-sdk
COPY src/tinycua ./tinycua
RUN uv pip install --no-cache-dir --system ./tinycua-sdk \
 && uv pip install --no-cache-dir --system ./tinycua
```

- **Run command**:

```bash
tinycua run \
  --prompt "$EXPERIMENT_PROMPT" \
  --dir "/workspace/experiment-${EXPERIMENT_NUM}" \
  --provider-url "$EXPERIMENT_LLM_BASE_URL" \
  --api-key "$EXPERIMENT_LLM_API_KEY" \
  --model "$EXPERIMENT_LLM_MODEL" \
  --provider-type "${EXPERIMENT_TINYCUA_PROVIDER_TYPE:-openai-chat-completions}" \
  --timeout "${EXPERIMENT_TIMEOUT_SECONDS:-900}"
```

Use `--dir`; current `tinycua run` does not use the older `--workspace` / `--output-dir` flags.

#### Opencode

- **Base image**: Node LTS image.
- **Install command**: `npm install -g opencode-ai`.
- **Config mapping**: generate a minimal Opencode config from the shared experiment env so it points at `EXPERIMENT_LLM_BASE_URL` and `EXPERIMENT_LLM_MODEL`. If Opencode requires provider-specific model syntax, expose only one override: `EXPERIMENT_OPENCODE_MODEL`, defaulting to `EXPERIMENT_LLM_MODEL`.
- **Run command**:

```bash
opencode run \
  --model "${EXPERIMENT_OPENCODE_MODEL:-$EXPERIMENT_LLM_MODEL}" \
  "$EXPERIMENT_PROMPT"
```

If Opencode cannot consume the local OpenAI-compatible URL directly from env/config, fail loudly and keep the stderr in `stderr.log`.

#### OpenClaw

- **Base image**: Node LTS image or official OpenClaw image if it is simpler.
- **Install command**: `npm install -g openclaw@latest`.
- **Config mapping**: write `~/.openclaw/openclaw.json` from `EXPERIMENT_LLM_BASE_URL`, `EXPERIMENT_LLM_MODEL`, and `EXPERIMENT_LLM_API_KEY` during container startup.
- **Run command**:

```bash
openclaw agent \
  --message "$EXPERIMENT_PROMPT" \
  --thinking "${EXPERIMENT_OPENCLAW_THINKING:-high}"
```

#### Hermes

- **Base image**: Python 3.11 image unless upstream requires a different runtime.
- **Install command**: official Hermes installer or a pinned package install once verified.
- **Config mapping**: initialize Hermes with `EXPERIMENT_LLM_PROVIDER`, `EXPERIMENT_LLM_MODEL`, and `EXPERIMENT_LLM_API_KEY`. If Hermes cannot use `EXPERIMENT_LLM_BASE_URL` for a local OpenAI-compatible endpoint, record that as an explicit MVP limitation in stderr.
- **Run command**:

```bash
hermes -z "$EXPERIMENT_PROMPT" \
  --provider "$EXPERIMENT_LLM_PROVIDER" \
  --model "$EXPERIMENT_LLM_MODEL"
```

### Output Capture Contract

Each container entrypoint creates `/workspace/experiment-${EXPERIMENT_NUM}` and writes:

```text
prompt.txt      # exact prompt received
stdout.log      # harness stdout
stderr.log      # harness stderr and setup warnings
metadata.json   # runner-written timing/status metadata
```

The runner may write `metadata.json` after `docker compose run` returns. The harness command itself should write only prompt/log/artifacts; no database or service-side metrics collector.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Missing prompt | Exit 2 with message | No containers run. |
| Empty prompt | Exit 2 with message | Whitespace-only counts as empty. |
| Existing result directory | Exit 2 unless `--overwrite` | Avoid accidental comparison loss. |
| Docker Compose command fails | Record non-zero exit code | Continue to next agent by default. |
| Missing `.env` | Exit 2 with message | Tell user to copy `.env.example`. |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Add a tiny test for prompt validation and metadata shape.
- [ ] Add `docker-compose.yml` with four separate services and named volumes: `Opencode_Vol`, `Hermes_Vol`, `Openclaw_Vol`, `TINYCUA_Vol`.
- [ ] Add `.env.example` with normalized LLM settings.
- [ ] Add `run_experiment.py` that runs the four services sequentially and captures stdout/stderr/duration.
- [ ] Add a TINYCUA Dockerfile that installs local `src/tinycua-sdk` and `src/tinycua`, then runs `tinycua run`.
- [ ] Add minimal Opencode, OpenClaw, and Hermes Dockerfiles or placeholders that make missing config/CLI commands obvious.
- [ ] Add README usage notes only if the commands are not obvious from `.env.example` and script help.

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Add optional `--fail-fast` if sequential failure continuation becomes noisy.
- [ ] Add optional summary table after a run.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use Docker Compose plus a Python runner.
   - **Reason**: Compose handles build/run/volumes; Python's stdlib handles timing, subprocesses, and JSON without new dependencies.
   - **Alternatives Considered**: A full benchmark framework — rejected because this branch is for readable experiments, not a platform.

2. **Decision**: Store results inside per-agent named volumes.
   - **Reason**: Matches the requested isolation model and prevents agents from trampling each other's workspace.
   - **Alternatives Considered**: One shared output directory — rejected because cross-agent writes make comparisons messier.

3. **Decision**: Continue after agent failure by default.
   - **Reason**: One broken harness should not block comparison data from the others.
   - **Alternatives Considered**: Fail-fast — useful later, but not the default for comparison runs.

4. **Decision**: Use plain logs plus `metadata.json`.
   - **Reason**: Greppable, diffable, and enough for manual comparison.
   - **Alternatives Considered**: Database or metrics backend — rejected as overkill.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agent CLI invocation differs by harness | High | Med | Keep commands visible and overridable in compose/Dockerfiles. |
| Provider config names differ | High | Med | Normalize shared env keys, map per harness at container boundary. |
| Local model endpoint is on the host | High | Med | Add `host.docker.internal:host-gateway` and document that Linux containers should use `http://host.docker.internal:1234/v1` if `localhost` resolves inside the container. |
| Real LLM runs are slow or flaky | Med | Med | Provide stub/dry-run path for tests; keep real runs manual. |
| Containers write huge artifacts | Med | Low | MVP stores only prompt/logs/metadata by default. |
| Volumes hide files from host browsing | Med | Low | Document `docker compose run`/`cp` inspection path if needed. |

---

## Open Questions _(optional)_

1. Exact install/run commands for Hermes and OpenClaw images can stay visible and fail-loud until we verify their current CLIs.
2. The example local URL is `http://localhost:1234/v1` for host-side use. Containers may need `http://host.docker.internal:1234/v1`; keep this as one documented `.env` edit, not automatic magic.

---

## References

- Spec: `./spec.md`
