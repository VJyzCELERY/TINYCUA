# Agent harness experiment

```bash
scripts/setup.sh
scripts/run.sh 1 "Make me a simple clock animation app in a single HTML file"
```

Results land under `results/<agent>/experiment-<num>/` with `prompt.txt`, `container.env`, `stdout.log`, `stderr.log`, and `metadata.json`.
Logs are written while each harness runs, and each harness is killed after `EXPERIMENT_TIMEOUT_SECONDS` (default `3600`).

If containers cannot reach a host LLM on `localhost`, set `EXPERIMENT_LLM_BASE_URL=http://host.docker.internal:1234/v1` in `.env`.

Batch runs:

```text
Experiment_1: Hello there
Experiment_2: Make a simple analog clock app in one HTML file
```

```bash
uv run python run_batch_experiments.py --manifest tmp/experiment_command.txt
```

The batch runner runs experiments sequentially, runs `judge.py` for each one, then moves judged outputs from `results/` to `archives/<timestamp>/`.

To avoid rerunning stable harnesses while iterating on TinyCUA, filter runs:

```bash
uv run python run_batch_experiments.py --manifest tmp/experiment_command.txt --agents opencode,hermes,openclaw
uv run python run_batch_experiments.py --manifest tmp/experiment_command.txt --agents tinycua
```

Hermes has a separate guard for stuck background-process polling: `EXPERIMENT_HERMES_PROCESS_POLL_TIMEOUT_SECONDS` (default `600`, `0` disables it). Failed or timed-out outputs are still judged and archived.

Web search uses the bundled SearXNG compose service where the harness supports it. Containers use `http://searxng:8080` (`/search` for TinyCUA), exposed on host port `18080` by default. Override `EXPERIMENT_SEARXNG_HOST_PORT`, `EXPERIMENT_SEARXNG_BASE_URL`, or `TINYCUA_SEARXNG_URL` in `.env` if needed. opencode currently has no native SearXNG websearch provider, so it just receives the env aliases for future/tool compatibility.

After each harness run, root-owned container outputs are repaired to the host user and known harness artifacts (`.openclaw/`, `.tinycua_context_cache/`, OpenClaw bootstrap files) are removed before judging.
