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

Hermes has a separate guard for stuck background-process polling: `EXPERIMENT_HERMES_PROCESS_POLL_TIMEOUT_SECONDS` (default `600`, `0` disables it). Failed or timed-out outputs are still judged and archived.
