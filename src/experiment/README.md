# Agent Harness Experiment

This subproject runs the same task prompts through four agent harnesses:

- `opencode`
- `hermes`
- `openclaw`
- `tinycua`

It records each harness output, workdir, logs, runtime metadata, and optional judge verdicts.

## Requirements

- Docker with Docker Compose
- `uv`
- An OpenAI-compatible LLM server reachable from Docker containers

The default `.env.example` assumes LM Studio or another OpenAI-compatible server at:

```text
http://host.docker.internal:1234/v1
```

If you run the LLM server directly on the host and containers cannot reach it, keep `host.docker.internal`. If you run without Docker, use `http://localhost:1234/v1` instead.

## Setup

From this directory:

```bash
cp .env.example .env
$EDITOR .env
bash scripts/setup.sh
```

Important `.env` values:

| Variable | Purpose |
|---|---|
| `EXPERIMENT_LLM_BASE_URL` | OpenAI-compatible model API URL used by harness containers. |
| `EXPERIMENT_LLM_MODEL` | Model name passed to harnesses. |
| `EXPERIMENT_LLM_API_KEY` | API key placeholder for OpenAI-compatible servers. |
| `EXPERIMENT_TIMEOUT_SECONDS` | Hard wall-clock cap per harness run. Default: `14400`. |
| `EXPERIMENT_IDLE_TIMEOUT_SECONDS` | Optional idle-output timeout. Default: disabled. |
| `EXPERIMENT_HERMES_PROCESS_POLL_TIMEOUT_SECONDS` | Hermes guard for stuck process polling. Default: `600`; `0` disables. |
| `JUDGE_MODEL` / `JUDGE_VARIANT` | Judge model configuration for `judge.py`. |

The setup script builds harness containers, starts from `.env.example` if `.env` is missing, pulls SearXNG, and pulls the `python:3.12-alpine` evaluator image.

## Run one experiment

```bash
uv run python run_experiment.py \
  --num 3 \
  --prompt "Make me a simple analog clock app with animation in a single HTML file" \
  --overwrite
```

Run only selected harnesses while iterating:

```bash
uv run python run_experiment.py \
  --num 3 \
  --prompt "Make me a simple analog clock app with animation in a single HTML file" \
  --agents tinycua \
  --overwrite
```

Available harness names: `opencode,hermes,openclaw,tinycua`.

## Run a controlled fixture

Controlled fixtures seed an isolated coding workspace and use repository-owned deterministic checks instead of the LLM judge:

```bash
uv run python run_template_experiment.py --fixtures smoke-test --agents tinycua
```

TinyCUA ablations are controlled-fixture-only aliases. They reuse the TinyCUA
image while isolating results and state:

```bash
uv run python run_template_experiment.py \
  --fixtures experiment-4 \
  --agents tinycua,tinycua-nr,tinycua-nd,tinycua-nd-nr
```

`tinycua-nr` disables review, `tinycua-nd` disables digestion, and
`tinycua-nd-nr` disables both. They are opt-in and are not included in defaults.
The controlled-runner default agent sequence is
`tinycua,opencode,hermes,openclaw`. An explicit `--agents` list both selects
agents and preserves their order.

Runs are fixture-major by default. Use `--order-by agent` to finish all selected
fixtures for each agent before advancing to the next listed agent:

```bash
uv run python run_template_experiment.py \
  --fixtures experiment-1,experiment-2,experiment-3,experiment-4,experiment-5 \
  --agents tinycua,tinycua-nr,tinycua-nd,tinycua-nd-nr,opencode,hermes,openclaw \
  --order-by agent \
  --output-root template-results/campaign-1
```

Reusing the same `--output-root` resumes automatically. Complete pass or fail
pairs are skipped, interrupted pairs are rerun from clean state, and new
fixtures or agents are added to the same campaign. `outcomes.json` and
`run_metadata.json` aggregate every invocation. Incompatible runner inputs, model
settings, timeouts, fixture revisions, or agent configurations fail before Docker
work. Migrated schema-v1 results remain readable but are sealed against new pair
execution because their historical runner inputs cannot be verified.

To apply changed evaluators to saved workdirs without rerunning agents, use
`--re-evaluate` (optionally with the same fixture and agent selectors). It records
the new evaluator result alongside the original evaluation and rebuilds
`outcomes.json`:

```bash
uv run python run_template_experiment.py --re-evaluate --fixtures experiment-4
```

Each completed pair retains only `result.json`, `stdout.log`, `stderr.log`,
`environment.json`, and a cleaned `workdir/`. Evaluator scores are embedded in
`result.json`; generated environments, caches, helper scripts, transfer logs,
and evaluator scratch are removed. Harness state and workspace volumes are
fresh for every executed pair and removed afterward. `--overwrite` replaces
only the selected pairs.

Clone `experiment-fixtures/template/` into
`experiment-fixtures/experiments-list/<name>/` to create a task. See that
template's README for manifest, dependency, evaluator, and Dockerfile contracts.

## Run the full five-task experiment

Create a manifest, for example `tmp/experiment_command.txt`:

```text
Experiment_1: Hello there
Experiment_2: Can you search the current latest and best frontier LLM model and how good are they? Write your findings down on a report.md
Experiment_3: Make me a simple analog clock app with animation in a single HTML file
Experiment_4: Can you make me an app like Notion using python for the backend, intuitive webui for the frontend and SQLite for the primary storage / database
Experiment_5: Can you do a research on Neural Networks and Transformer for me and write me a comprehensive studying docs using markdown for me to read and learn more about them?
```

Run all harnesses and judge each experiment comparatively:

```bash
uv run python run_batch_experiments.py \
  --manifest tmp/experiment_command.txt \
  --cross-judge
```

The batch runner does three things:

1. runs `scripts/setup.sh` unless `--skip-setup` is passed;
2. runs each manifest prompt through the selected harnesses;
3. runs `judge.py` for each experiment.

Useful batch options:

```bash
# Run only specific harnesses.
uv run python run_batch_experiments.py --manifest tmp/experiment_command.txt --agents tinycua --cross-judge

# Reuse already-built containers.
uv run python run_batch_experiments.py --manifest tmp/experiment_command.txt --skip-setup --cross-judge

# Stop at the first run/judge failure.
uv run python run_batch_experiments.py --manifest tmp/experiment_command.txt --fail-fast --cross-judge

# Preview commands without running them.
uv run python run_batch_experiments.py --manifest tmp/experiment_command.txt --dry-run --cross-judge
```

## Judge existing results

For controlled template results, run the qualitative semantic judge. It
discovers however many completed harness submissions exist for each fixture,
anonymizes them, receives deterministic evaluator outcomes as context, and
compares qualitative strengths and weaknesses:

```bash
uv run python judge.py --fixture experiment-4
uv run python judge.py --fixture experiment-4,experiment-5
```

Semantic verdicts are written to:

```text
template-results/<fixture>/cross_verdict/verdict.md
template-results/<fixture>/cross_verdict/mapping.json
```

Legacy results judging is optional and must be explicitly selected with `--num`:

```bash
uv run python judge.py --num 4 --cross-judge
```

Judge selected harnesses only:

```bash
uv run python judge.py --num 4 --agents opencode,hermes,openclaw,tinycua --cross-judge
```

Cross-judge mode anonymizes submissions as `A`, `B`, `C`, and `D`, then writes:

```text
results/<first-selected-agent>/experiment-<num>/cross_verdict/verdict.md
results/<first-selected-agent>/experiment-<num>/cross_verdict/mapping.json
```

For the checked-in evaluation snapshot, those verdicts were copied into `evaluation-results/judges_verdict/experiment_<num>/` by hand after sanitizing the raw results.

Non-cross-judge mode writes per-harness verdicts under each harness result directory.

## Result layout

Raw run outputs are written under `results/`:

```text
results/
├── opencode/experiment-<num>/
│   ├── workdir/
│   └── logs/
│       ├── prompt.txt
│       ├── container.env
│       ├── stdout.log
│       ├── stderr.log
│       └── metadata.json
├── hermes/experiment-<num>/...
├── openclaw/experiment-<num>/...
└── tinycua/experiment-<num>/...
```

If `--cross-judge` is used, `cross_verdict/` is added under the first selected harness result directory. If regular judging is used, `judge_verdict/` is added under each selected harness result directory.

`metadata.json` contains runtime fields such as `started_at`, `llm_started_at`, `warmup_seconds`, `duration_seconds`, `exit_code`, and `status`.

`results/` is ignored by git because it can contain caches, environments, databases, logs, and bulky artifacts. The checked-in `evaluation-results/` directory is a manually sanitized snapshot of selected results.

## Web search

The existing harness configuration supplies SearXNG aliases to all four agents
(OpenCode, Hermes, OpenClaw, and TinyCUA):

```text
EXPERIMENT_SEARXNG_BASE_URL=http://searxng:8080
TINYCUA_SEARXNG_URL=http://searxng:8080/search
```

The host port defaults to `18080`; override `EXPERIMENT_SEARXNG_HOST_PORT` if needed.
Controlled campaigns start SearXNG if needed and wait up to 60 seconds for its
`/healthz` endpoint before building or running a pair. The service is not
restarted between invocations: preserving SearXNG's engine backoff avoids
immediately retrying upstreams that already returned rate limits or CAPTCHAs.
Container lifecycle cannot clear limits attached to the host's public IP.

Controlled runs are noninteractive and full-access by existing configuration:
OpenCode (`--dangerously-skip-permissions`), Hermes (`--yolo`), and OpenClaw
(full profile with sandbox off). No legacy Dockerfile or Compose change is
needed for that behavior.

## Verify the runner

```bash
uv run pytest
```

## Cleanup

Remove generated local outputs when done:

```bash
rm -rf results archives tmp
docker compose down
```

Do not commit raw `results/`, `.env`, virtual environments, container caches, or generated databases.
