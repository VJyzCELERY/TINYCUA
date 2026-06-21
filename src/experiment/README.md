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

The setup script builds harness containers, starts from `.env.example` if `.env` is missing, pulls SearXNG, and pulls `busybox` for file-permission repair.

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

If results already exist and you only want to judge them:

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

The compose file includes SearXNG. Harnesses that support search receive:

```text
EXPERIMENT_SEARXNG_BASE_URL=http://searxng:8080
TINYCUA_SEARXNG_URL=http://searxng:8080/search
```

The host port defaults to `18080`; override `EXPERIMENT_SEARXNG_HOST_PORT` if needed.

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
