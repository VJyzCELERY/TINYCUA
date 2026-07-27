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

Clone `experiment-fixtures/template/` into `experiment-fixtures/experiments-list/<name>/` to create a task. A fixture contains `manifest.yaml`, `workdir/`, `eval/`, and optionally one `docker/Dockerfile`. The manifest requires non-empty `prompt` and `eval_image` strings plus an `eval_command` list of non-empty strings. The evaluator runs the declared command in `eval_image`, with read-only `/eval` and `/submission` mounts. Before that command, it installs only top-level `/submission/requirements.txt`, `/submission/pyproject.toml`, `/eval/requirements.txt`, and `/eval/pyproject.toml` in the ephemeral evaluator container. To install nested submission manifests, list each safe relative `requirements.txt` or `pyproject.toml` path in `submission_dependency_files`; undeclared nested manifests fail evaluator setup rather than being guessed. Set `entrypoint_manages_dependencies: true` for a free-form entrypoint that installs dependencies itself; that skips submission-manifest installation and nested-manifest validation while preserving evaluator dependency installation. A manifest requires Python and pip in `eval_image`; otherwise the evaluator fails with a clear diagnostic. Manifest-free evaluators, including BusyBox, run their command directly. Set `submission_dockerfile` to a safe relative Dockerfile path to make the host runner run a bounded `docker build` using the copied submission as context before evaluation. Its stdout and stderr are retained as `submission-build.*.log`; a failed build skips evaluation and fails the pair. This works when agents run in Docker because the runner on the host, not the agent or evaluator container, owns Docker. An optional fixture `docker/Dockerfile` must begin with `ARG BASE_IMAGE` and `FROM ${BASE_IMAGE}`; it is built once per selected harness from the safe `docker/` context, which cannot include `eval/` or `workdir/`.

The runner writes `template-results/<fixture>/<agent>/workdir/`, sanitized logs, and a portable `result.json`. The result records UTC `started_at` and `ended_at`, elapsed prompt-to-agent-completion `elapsed_prompt_to_finish_seconds`, relative agent stdout/stderr paths, the agent exit code, deterministic evaluator outcome, and a relative `container_environment.json` reference. Root `run_metadata.json` freezes fixture/evaluator revisions, local image IDs and registry digests, pinned harness versions, model settings, trial policy, timeout, overwrite policy, and the result-generation commit. Root `outcomes.json` reports coding, research, and conversation fixtures separately without a cross-task average or overall rank. An evaluator may optionally write `/result/score.json` to its dedicated writable `evaluator-result/` mount. Its JSON must contain `categories`, `total`, `pass_threshold`, and `critical_categories`; each category contains bounded `points`, `max_points`, and string `evidence`. Optional finite numeric `metrics`, such as ROUGE-L F1, are reporting-only. The runner validates the score and embeds it under `score` in `result.json`. A scored pair passes only when the evaluator exits `0`, total meets the threshold, and every critical category earns its full points with evidence. Controlled fixtures use one binary `0/1` category per observable check, partial thresholds, and critical gates for non-compensable requirements. Mandatory coding behavior is always critical, making coding outcomes Pass@1 functional-correctness results. Fixtures without a score retain exit-code-only pass/fail behavior. Rubric categories are fixture-specific deterministic evidence, not a general capability measure. That environment snapshot redacts secret-bearing values; configured secret values and secret-looking assignments are also redacted from agent and evaluator output, including timeout diagnostics. Agent containers receive only that copied workdir and their named `/state` volume. Agent Compose and evaluator Docker containers use deterministic pair-specific names. Docker commands have a one-hour deadline by default; set `--timeout-seconds` to a positive value to override it. On timeout, the runner force-removes the named container before continuing, returns exit code `124`, retains sanitized timeout diagnostics, and writes `result.json`. Existing output is protected unless `--overwrite` is passed.

Inspect or reset a pair's persistent state explicitly:

```bash
docker volume inspect tinycua-template-6164642d6772656574696e67-74696e79637561
docker volume rm tinycua-template-6164642d6772656574696e67-74696e79637561
```

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
